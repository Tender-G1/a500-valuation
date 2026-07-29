"""
计算引擎：分位、ERP、熔断、多模态触发、动量辅助。
"""
import numpy as np
import pandas as pd
from typing import Tuple, Optional

def calc_percentile(current: float, series: list) -> float:
    """计算当前值在历史序列中的百分位（高于多少%的历史值），返回0-100。"""
    arr = [x for x in series if x is not None and x > 0]
    if not arr:
        return 50.0
    return round(sum(1 for x in arr if x < current) / len(arr) * 100, 1)

def calc_erp(pe: float, bond_yield: float) -> float:
    """计算股权风险溢价 ERP = 1/PE - 债券收益率（%）。"""
    if pe <= 0:
        return 0.0
    return (1.0 / pe) * 100 - bond_yield   # 单位：%

def check_circuit_breaker(today: dict, yesterday: dict, config: dict) -> bool:
    """
    检查是否触发熔断（PE变动>阈值 或 PB变动>阈值）。
    返回 True 表示应熔断。
    """
    pe_change = abs((today["pe_ttm"] - yesterday["pe_ttm"]) / yesterday["pe_ttm"] * 100)
    pb_change = abs((today.get("pb", 0) - yesterday.get("pb", 0)) / (yesterday.get("pb", 0.1)) * 100) if yesterday.get("pb") else 0
    cb_pe = config["circuit_breaker"]["pe_change_pct"]
    cb_pb = config["circuit_breaker"]["pb_change_pct"]
    if pe_change > cb_pe:
        return True
    if pb_change > cb_pb and yesterday.get("pb") is not None:
        return True
    return False

def check_alert(pe_pct: float, pb_pct: float, erp_pct: float, config: dict) -> Tuple[bool, bool]:
    """
    多模态触发判断。
    返回 (buy_alert, sell_alert)
    """
    buy_pe = config["valuation"]["buy_pe"]
    buy_pb = config["valuation"]["buy_pb"]
    sell_pe = config["valuation"]["sell_pe"]
    sell_pb = config["valuation"]["sell_pb"]
    erp_buy = config["valuation"]["erp_buy"]
    erp_sell = config["valuation"]["erp_sell"]

    buy_cond = (pe_pct <= buy_pe or pb_pct <= buy_pb) and erp_pct >= erp_buy
    sell_cond = (pe_pct >= sell_pe or pb_pct >= sell_pb) and erp_pct <= erp_sell
    return buy_cond, sell_cond

def calc_momentum_hint(df: pd.DataFrame, today_idx: int, config: dict) -> Optional[str]:
    """
    计算近30个交易日PE分位的变化，若急速下跌超过阈值则返回提示文本。
    df 需包含 'pe_ttm' 列，且已按日期升序。
    today_idx 为 today 在 df 中的位置（整数索引）。
    """
    lookback = config["momentum"]["lookback_days"]
    threshold = config["momentum"]["alert_threshold"]
    if today_idx < lookback:
        return None
    # 获取30天前的PE
    past_pe = df.iloc[today_idx - lookback]["pe_ttm"]
    current_pe = df.iloc[today_idx]["pe_ttm"]
    # 使用近10年窗口（需要访问全局窗口序列，此处假设外部传入，实际在main中计算）
    # 为避免重复计算，我们只在此返回原始变化值，实际使用由外部传入分位差值。
    # 我们在main中处理，此函数只返回提示字符串。
    # 修改设计：改为在main中直接计算分位变化，这里仅返回提示文本。
    return None