"""
主控脚本：串联所有模块，实现完整流程。
"""
import os
import sys
import yaml
import pandas as pd
from datetime import datetime, timedelta
from logger_config import setup_logger
from data_manager import load_or_init_csv, fetch_latest_pe_pb, append_latest_data, fetch_bond_yield
from calculator import calc_percentile, calc_erp, check_circuit_breaker, check_alert
from chart_generator import draw_triple_chart
from conclusion_builder import build_conclusion
from pusher import push_to_wechat, backup_artifacts

logger = setup_logger()

def main():
    logger.info("=== 中证A500估值监控系统启动 ===")
    
    # 加载配置
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    csv_path = "history_data.csv"
    
    # 1. 加载或初始化CSV（若不存在则全量拉取）
    try:
        df = load_or_init_csv(csv_path)
    except Exception as e:
        logger.error(f"初始化CSV失败: {e}")
        # 推送错误告警
        push_to_wechat(f"❌ 系统初始化失败，无法获取历史数据。错误: {e}")
        sys.exit(1)
    
    # 2. 增量拉取最新数据
    latest, fetched = fetch_latest_pe_pb()
    data_updated = False
    if fetched and latest:
        # 检查是否已存在
        if latest["date"] > df["date"].max():
            # 获取国债收益率
            bond = fetch_bond_yield()
            if bond is None:
                bond = df["bond_yield_10y"].iloc[-1]  # 使用上一次值
                logger.warning("未获取到最新国债收益率，沿用上次值")
            df = append_latest_data(df, latest, csv_path, bond)
            data_updated = True
            logger.info(f"数据已更新至 {latest['date']}")
        else:
            logger.info("数据已是最新，无需追加")
    else:
        logger.warning("增量拉取失败或未获取到新数据，将使用缓存")
    
    # 3. 熔断检查（仅当有新数据时）
    if data_updated and len(df) >= 2:
        yesterday = df.iloc[-2]
        today = df.iloc[-1]
        if check_circuit_breaker(today.to_dict(), yesterday.to_dict(), config):
            alert_msg = f"⚠️ 数据异常熔断：PE变动 {abs((today['pe_ttm']-yesterday['pe_ttm'])/yesterday['pe_ttm']*100):.2f}%，PB变动 {abs((today['pb']-yesterday['pb'])/(yesterday['pb'] or 0.1)*100):.2f}%"
            logger.error(alert_msg)
            push_to_wechat("🚫 数据异常告警", alert_msg)
            sys.exit(0)
    
    # 4. 准备计算基准
    today = df.iloc[-1]
    cutoff = today["date"] - timedelta(days=3650)
    df_10y = df[df["date"] >= cutoff]
    min_days = config["rolling_window"]["min_days"]
    use_rolling = len(df_10y) >= min_days
    base_df = df_10y if use_rolling else df
    base_label = "近10年" if use_rolling else "自基日"
    logger.info(f"使用基准: {base_label}，数据点 {len(base_df)}")
    
    # 5. 计算分位（PE, PB, ERP）
    pe_pct = calc_percentile(today["pe_ttm"], base_df["pe_ttm"].tolist())
    pb_pct = calc_percentile(today["pb"], base_df["pb"].dropna().tolist()) if today["pb"] else 50.0
    # 计算ERP
    erp = calc_erp(today["pe_ttm"], today["bond_yield_10y"])
    # ERP历史分位（基于base_df）
    erp_series = [calc_erp(p, b) for p, b in zip(base_df["pe_ttm"], base_df["bond_yield_10y"])]
    erp_pct = calc_percentile(erp, erp_series)
    logger.info(f"PE分位: {pe_pct}%, PB分位: {pb_pct}%, ERP分位: {erp_pct}%")
    
    # 6. 触发检查
    buy_alert, sell_alert = check_alert(pe_pct, pb_pct, erp_pct, config)
    logger.info(f"买入警报: {buy_alert}, 卖出警报: {sell_alert}")
    
    # 7. 动量辅助（若触发买入）
    momentum_hint = None
    if buy_alert:
        # 计算30天前PE分位变化（需回溯30个交易日）
        lookback = config["momentum"]["lookback_days"]
        if len(df) >= lookback + 1:
            past_row = df.iloc[-lookback-1]  # 30天前
            # 使用相同的基准窗口计算过去分位
            past_pe_pct = calc_percentile(past_row["pe_ttm"], base_df["pe_ttm"].tolist())
            drop = pe_pct - past_pe_pct
            if drop <= -config["momentum"]["alert_threshold"]:
                momentum_hint = f"⚠️ 辅助提示：近一个月PE分位急速下降 {-drop:.1f} 个百分点，可能反映盈利预期恶化，建议结合基本面谨慎判断抄底时机。"
    
    # 8. 计算分位变化（仅当有新数据）
    delta = None
    if data_updated and len(df) >= 2:
        yesterday = df.iloc[-2]
        yesterday_pct = calc_percentile(yesterday["pe_ttm"], base_df["pe_ttm"].tolist())
        delta = pe_pct - yesterday_pct
        logger.info(f"分位变化: {delta:+.1f} 个百分点")
    
    # 9. 构建结论
    conclusion = build_conclusion(
        pe_pct, erp_pct, delta,
        buy_alert, sell_alert, momentum_hint,
        base_label, data_updated
    )
    logger.info("结论生成完成")
    
    # 10. 生成图表
    chart_path = draw_triple_chart(
        base_df, today, pe_pct, pb_pct, erp_pct,
        base_label, config
    )
    logger.info(f"图表已保存至 {chart_path}")
    
    # 11. 推送
    success = push_to_wechat(conclusion, chart_path)
    if not success:
        logger.warning("推送失败，执行备存")
        backup_artifacts(chart_path, conclusion)
    
    logger.info("=== 执行完成 ===")

if __name__ == "__main__":
    main()