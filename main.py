"""
主控脚本（集成全部模块 V4.0）
"""
import os
import sys
import yaml
import pandas as pd
from datetime import datetime, timedelta
from logger_config import setup_logger
from data_manager import load_or_init_csv, fetch_latest_pe_pb, append_latest_data, fetch_bond_yield_fallback
from calculator import calc_percentile, calc_erp, check_circuit_breaker, check_alert
from chart_generator import draw_triple_chart
from conclusion_builder import build_conclusion
from pusher import (
    push_valuation_report, push_portfolio_report, push_fund_report,
    push_alert, push_weekly_report, backup_artifacts
)
from portfolio_manager import load_portfolio, calc_portfolio_summary, save_portfolio, add_transaction
from fund_manager import get_fund_status, suggest_fund_source
from strategy import get_buy_step, get_sell_step, get_next_buy_info, get_next_sell_info
from multi_index import scan_all_indices

logger = setup_logger()


def main():
    logger.info("=== 中证A500估值监控系统 V4.0 启动 ===")

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    csv_path = "history_data.csv"
    try:
        df = load_or_init_csv(csv_path)
    except Exception as e:
        logger.error(f"初始化CSV失败: {e}")
        sys.exit(1)

    # 获取数据
    latest, fetched = fetch_latest_pe_pb()
    data_updated = False
    if fetched and latest and latest["date"] > df["date"].max():
        bond = fetch_bond_yield_fallback()
        if bond is None:
            bond = df["bond_yield_10y"].iloc[-1]
        df = append_latest_data(df, latest, csv_path, bond)
        data_updated = True

    # 熔断检查
    if data_updated and len(df) >= 2:
        yesterday, today = df.iloc[-2], df.iloc[-1]
        if check_circuit_breaker(today.to_dict(), yesterday.to_dict(), config):
            pe_chg = abs((today["pe_ttm"] - yesterday["pe_ttm"]) / yesterday["pe_ttm"] * 100)
            pb_chg = abs((today.get("pb", 0) - yesterday.get("pb", 0)) / (yesterday.get("pb", 0.1)) * 100)
            alert_msg = f"数据异常熔断：PE变动{pe_chg:.2f}%，PB变动{pb_chg:.2f}%"
            push_alert("数据异常", alert_msg)
            sys.exit(0)

    today = df.iloc[-1]
    bond_yield = today["bond_yield_10y"]

    # 计算基准
    cutoff = today["date"] - timedelta(days=3650)
    df_10y = df[df["date"] >= cutoff]
    use_rolling = len(df_10y) >= config["rolling_window"]["min_days"]
    base_df = df_10y if use_rolling else df
    base_label = "近10年" if use_rolling else "自基日"

    # 分位计算
    pe_pct = calc_percentile(today["pe_ttm"], base_df["pe_ttm"].tolist())
    pb_pct = calc_percentile(today["pb"], base_df["pb"].dropna().tolist()) if today["pb"] else 50.0
    erp = calc_erp(today["pe_ttm"], bond_yield)
    erp_series = [calc_erp(p, b) for p, b in zip(base_df["pe_ttm"], base_df["bond_yield_10y"])]
    erp_pct = calc_percentile(erp, erp_series)

    # 自基日参考
    full_pe_pct = calc_percentile(today["pe_ttm"], df["pe_ttm"].tolist())
    full_pb_pct = calc_percentile(today["pb"], df["pb"].dropna().tolist()) if today["pb"] else 50.0
    full_erp_series = [calc_erp(p, b) for p, b in zip(df["pe_ttm"], df["bond_yield_10y"])]
    full_erp_pct = calc_percentile(erp, full_erp_series)

    # 分位变化
    delta = 0
    if len(df) >= 2:
        yesterday = df.iloc[-2]
        yesterday_pct = calc_percentile(yesterday["pe_ttm"], base_df["pe_ttm"].tolist())
        delta = pe_pct - yesterday_pct

    # 警报检查
    buy_alert, sell_alert = check_alert(pe_pct, pb_pct, erp_pct, config)

    # 动量辅助
    momentum_hint = None
    if buy_alert:
        lookback = config["momentum"]["lookback_days"]
        if len(df) >= lookback + 1:
            past_row = df.iloc[-lookback-1]
            past_pe_pct = calc_percentile(past_row["pe_ttm"], base_df["pe_ttm"].tolist())
            drop = pe_pct - past_pe_pct
            if drop <= -config["momentum"]["alert_threshold"]:
                momentum_hint = f"⚠️ 近一个月PE分位急速下降 {-drop:.1f}个百分点，建议结合基本面判断"

    # 构建结论
    conclusion = build_conclusion(pe_pct, erp_pct, delta, buy_alert, sell_alert, momentum_hint, base_label, data_updated)

    # ─── N2：分批策略 ──────────────────────────────────
    buy_step = get_buy_step(pe_pct, config['strategy'])
    sell_step = get_sell_step(pe_pct, config['strategy'])
    next_buy = get_next_buy_info(pe_pct, config['strategy'])
    next_sell = get_next_sell_info(pe_pct, config['strategy'])

    if buy_step:
        conclusion += f"\n\n【买入信号】触发{buy_step['label']}，建议买入比例：{buy_step['ratio']*100:.0f}%"
    if sell_step:
        conclusion += f"\n\n【卖出信号】触发{sell_step['label']}，建议卖出比例：{sell_step['ratio']*100:.0f}%"
    if next_buy['threshold'] is not None and pe_pct > next_buy['threshold']:
        conclusion += f"\n距离下一买入区间还差 {next_buy['gap']:.1f} 个百分点（{next_buy['label']}）"

    # ─── N1：资金管理 ──────────────────────────────────
    fund_status = get_fund_status(config['fund'])
    if buy_step:
        total_pool = config['fund']['total_pool']
        buy_amount = total_pool * buy_step['ratio']
        fund_suggestion = suggest_fund_source(fund_status, buy_amount)
        if fund_suggestion['can_cover']:
            suggestion_text = "建议从以下层级取用：\n" + "\n".join([
                f"  {s['tier_name']}: ¥{s['take_amount']:,.0f}"
                for s in fund_suggestion['suggestion']
            ])
            conclusion += f"\n\n【资金建议】\n{suggestion_text}"

    # ─── N3：持仓更新 ──────────────────────────────────
    portfolio_key = os.environ.get("PORTFOLIO_KEY")
    if portfolio_key and buy_step:
        df_portfolio = load_portfolio(portfolio_key)
        # 自动添加买入记录（如触发买入）
        # 注意：实际使用时需用户确认，这里仅为示例
        # 实际通过网站界面录入，此处跳过自动添加

    # ─── N6：多指数扫描 ──────────────────────────────
    multi_results = scan_all_indices(config, bond_yield)
    if multi_results:
        conclusion += "\n\n【多指数估值榜】\n"
        for r in multi_results[:5]:
            conclusion += f"{r['status']} {r['name']}: PE分位{r['pe_pct']:.1f}% | {r['advice']}\n"

    # ─── 生成图表 ──────────────────────────────────────
    chart_conclusion = f"📊 中证A500 估值日报（基准：{base_label}）\n当前PE分位：{pe_pct:.1f}%，ERP分位：{erp_pct:.1f}%\n{conclusion.split(chr(10))[2] if len(conclusion.split(chr(10))) > 2 else conclusion}"
    chart_path = draw_triple_chart(
        base_df, today, pe_pct, pb_pct, erp_pct,
        full_pe_pct, full_pb_pct, full_erp_pct,
        base_label, config, chart_conclusion
    )

    # ─── N5：推送拆分 ──────────────────────────────────
    # 估值速报
    push_valuation_report(pe_pct, pb_pct, erp_pct, delta, base_label, conclusion)

    # 组合日报
    if portfolio_key:
        df_portfolio = load_portfolio(portfolio_key)
        current_prices = {'000510': today['pe_ttm']}  # 可用PE替代价格
        summary = calc_portfolio_summary(df_portfolio, current_prices)
        if summary['total_cost'] > 0:
            push_portfolio_report(summary)

    # 资金报告
    push_fund_report(fund_status)

    # 警报推送（触发时）
    if buy_alert:
        push_alert("买入警报", f"PE分位{pe_pct:.1f}%，ERP分位{erp_pct:.1f}%，建议关注买入机会")
    if sell_alert:
        push_alert("卖出警报", f"PE分位{pe_pct:.1f}%，ERP分位{erp_pct:.1f}%，建议注意风险")

    # 周报（周五）
    if datetime.now().weekday() == 4:  # 周五
        # 计算本周变化
        week_start = datetime.now() - timedelta(days=7)
        week_df = df[df['date'] >= week_start.date()]
        if len(week_df) >= 2:
            week_summary = {
                'start_pe_pct': calc_percentile(week_df.iloc[0]['pe_ttm'], base_df['pe_ttm'].tolist()),
                'end_pe_pct': pe_pct,
                'delta': pe_pct - calc_percentile(week_df.iloc[0]['pe_ttm'], base_df['pe_ttm'].tolist()),
                'actions': '本周估值' + ('上升' if delta > 0 else '下降'),
                'outlook': '建议根据下周估值变化动态调整仓位'
            }
            push_weekly_report(week_summary)

    # ─── 备份 ──────────────────────────────────────────
    if not push_valuation_report:
        backup_artifacts(chart_path, conclusion)

    # ─── 生成网站（含M4） ──────────────────────────────
    try:
        from generate_site import generate
        generate(chart_path)  # M4：传入图表路径
        logger.info("网站文件生成成功")
    except Exception as e:
        logger.warning(f"网站生成失败: {e}")

    logger.info("=== 执行完成 ===")


if __name__ == "__main__":
    main()
