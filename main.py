"""
主控脚本
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
from pusher import push_to_wechat, backup_artifacts

logger = setup_logger()

def main():
    logger.info("=== 中证A500估值监控系统启动 ===")
    
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    csv_path = "history_data.csv"
    try:
        df = load_or_init_csv(csv_path)
    except Exception as e:
        logger.error(f"初始化CSV失败: {e}")
        push_to_wechat(f"❌ 系统初始化失败: {e}")
        sys.exit(1)
    
    latest, fetched = fetch_latest_pe_pb()
    data_updated = False
    if fetched and latest and latest["date"] > df["date"].max():
        # H3：获取国债收益率，失败时使用上一交易日值
        bond = fetch_bond_yield_fallback()
        if bond is None:
            bond = df["bond_yield_10y"].iloc[-1]
            logger.warning("使用上一交易日国债收益率")
        df = append_latest_data(df, latest, csv_path, bond)
        data_updated = True
        logger.info(f"数据已更新至 {latest['date']}")
    else:
        logger.warning("增量拉取失败或数据已最新")
    
    # ─── H4：修复熔断告警推送 ────────────────────────
    if data_updated and len(df) >= 2:
        yesterday, today = df.iloc[-2], df.iloc[-1]
        pe_change = abs((today["pe_ttm"] - yesterday["pe_ttm"]) / yesterday["pe_ttm"] * 100)
        pb_change = abs((today.get("pb", 0) - yesterday.get("pb", 0)) / (yesterday.get("pb", 0.1)) * 100) if yesterday.get("pb") else 0
        if check_circuit_breaker(today.to_dict(), yesterday.to_dict(), config):
            alert_msg = f"🚫 数据异常告警\n\nPE变动: {pe_change:.2f}%\nPB变动: {pb_change:.2f}%\n\n已触发熔断，请检查数据源（中证API或国债利率接口）"
            logger.error(alert_msg)
            push_to_wechat(alert_msg)  # 只传一个参数，作为content
            sys.exit(0)
    
    today = df.iloc[-1]
    cutoff = today["date"] - timedelta(days=3650)
    df_10y = df[df["date"] >= cutoff]
    use_rolling = len(df_10y) >= config["rolling_window"]["min_days"]
    base_df = df_10y if use_rolling else df
    base_label = "近10年" if use_rolling else "自基日"
    
    pe_pct = calc_percentile(today["pe_ttm"], base_df["pe_ttm"].tolist())
    pb_pct = calc_percentile(today["pb"], base_df["pb"].dropna().tolist()) if today["pb"] else 50.0
    erp = calc_erp(today["pe_ttm"], today["bond_yield_10y"])
    erp_series = [calc_erp(p, b) for p, b in zip(base_df["pe_ttm"], base_df["bond_yield_10y"])]
    erp_pct = calc_percentile(erp, erp_series)
    
    full_pe_pct = calc_percentile(today["pe_ttm"], df["pe_ttm"].tolist())
    full_pb_pct = calc_percentile(today["pb"], df["pb"].dropna().tolist()) if today["pb"] else 50.0
    full_erp_series = [calc_erp(p, b) for p, b in zip(df["pe_ttm"], df["bond_yield_10y"])]
    full_erp_pct = calc_percentile(erp, full_erp_series)
    
    buy_alert, sell_alert = check_alert(pe_pct, pb_pct, erp_pct, config)
    
    momentum_hint = None
    if buy_alert:
        lookback = config["momentum"]["lookback_days"]
        if len(df) >= lookback + 1:
            past_row = df.iloc[-lookback-1]
            past_pe_pct = calc_percentile(past_row["pe_ttm"], base_df["pe_ttm"].tolist())
            drop = pe_pct - past_pe_pct
            if drop <= -config["momentum"]["alert_threshold"]:
                momentum_hint = f"⚠️ 近一个月PE分位急速下降 {-drop:.1f} 个百分点，建议结合基本面判断。"
    
    delta = None
    if len(df) >= 2:
        yesterday = df.iloc[-2]
        yesterday_pct = calc_percentile(yesterday["pe_ttm"], base_df["pe_ttm"].tolist())
        delta = pe_pct - yesterday_pct
    
    conclusion = build_conclusion(pe_pct, erp_pct, delta, buy_alert, sell_alert, momentum_hint, base_label, data_updated)
    
    chart_conclusion = f"📊 中证A500 估值日报（基准：{base_label}）\n当前PE分位：{pe_pct:.1f}%，ERP分位：{erp_pct:.1f}%\n{conclusion.split(chr(10))[2] if len(conclusion.split(chr(10))) > 2 else conclusion}"
    chart_path = draw_triple_chart(base_df, today, pe_pct, pb_pct, erp_pct, full_pe_pct, full_pb_pct, full_erp_pct, base_label, config, chart_conclusion)
    
    success = push_to_wechat(conclusion, chart_path)
    if not success:
        backup_artifacts(chart_path, conclusion)
    
    try:
        from generate_site import generate
        generate()
        logger.info("网站文件生成成功")
    except Exception as e:
        logger.warning(f"网站生成失败: {e}")
    
    logger.info("=== 执行完成 ===")

if __name__ == "__main__":
    main()
