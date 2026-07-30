"""
计算引擎：分位、ERP、熔断、多模态触发
（M3：此文件为 calc_percentile 的唯一实现，其他文件从此导入）
"""
import numpy as np
import pandas as pd
from typing import Tuple, Optional


def calc_percentile(current: float, series: list) -> float:
    """
    计算当前值在历史序列中的百分位（高于多少%的历史值）
    此函数为唯一实现，其他模块从本文件导入
    """
    arr = [x for x in series if x is not None and x > 0 and not np.isnan(x)]
    if not arr:
        return 50.0
    return round(sum(1 for x in arr if x < current) / len(arr) * 100, 1)


def calc_erp(pe: float, bond_yield: float) -> float:
    """计算股权风险溢价 ERP = 1/PE - 债券收益率（%）"""
    if pe <= 0:
        return 0.0
    return (1.0 / pe) * 100 - bond_yield


def check_circuit_breaker(today: dict, yesterday: dict, config: dict) -> bool:
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
    buy_pe = config["valuation"]["buy_pe"]
    buy_pb = config["valuation"]["buy_pb"]
    sell_pe = config["valuation"]["sell_pe"]
    sell_pb = config["valuation"]["sell_pb"]
    erp_buy = config["valuation"]["erp_buy"]
    erp_sell = config["valuation"]["erp_sell"]
    buy_cond = (pe_pct <= buy_pe or pb_pct <= buy_pb) and erp_pct >= erp_buy
    sell_cond = (pe_pct >= sell_pe or pb_pct >= sell_pb) and erp_pct <= erp_sell
    return buy_cond, sell_cond
