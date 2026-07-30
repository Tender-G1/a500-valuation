"""
分批买入/卖出策略模块（N2）
"""
from typing import Dict, List, Optional


def get_buy_step(pe_pct: float, config: Dict) -> Optional[Dict]:
    """
    根据当前PE分位判断触发哪个买入批次
    返回触发批次信息或None
    """
    steps = config.get('buy_steps', [])
    # 按阈值从高到低排序
    sorted_steps = sorted(steps, key=lambda x: x['threshold'], reverse=True)

    triggered = []
    for step in sorted_steps:
        if pe_pct <= step['threshold']:
            triggered.append(step)

    if not triggered:
        return None

    # 返回最低阈值的那一批（最激进）
    return triggered[-1]


def get_sell_step(pe_pct: float, config: Dict) -> Optional[Dict]:
    """
    根据当前PE分位判断触发哪个卖出批次
    """
    steps = config.get('sell_steps', [])
    sorted_steps = sorted(steps, key=lambda x: x['threshold'])

    triggered = []
    for step in sorted_steps:
        if pe_pct >= step['threshold']:
            triggered.append(step)

    if not triggered:
        return None

    # 返回最高阈值的那一批（最激进）
    return triggered[-1]


def get_next_buy_info(pe_pct: float, config: Dict) -> Dict:
    """
    获取距离下一买入区间的信息
    """
    steps = config.get('buy_steps', [])
    sorted_steps = sorted(steps, key=lambda x: x['threshold'], reverse=True)

    # 找到第一个当前未触发的批次
    for step in sorted_steps:
        if pe_pct > step['threshold']:
            return {
                'threshold': step['threshold'],
                'gap': pe_pct - step['threshold'],
                'label': step['label'],
                'ratio': step['ratio'] * 100
            }

    return {
        'threshold': None,
        'gap': 0,
        'label': '已全部触发',
        'ratio': 100
    }


def get_next_sell_info(pe_pct: float, config: Dict) -> Dict:
    """
    获取距离下一卖出区间的信息
    """
    steps = config.get('sell_steps', [])
    sorted_steps = sorted(steps, key=lambda x: x['threshold'])

    for step in sorted_steps:
        if pe_pct < step['threshold']:
            return {
                'threshold': step['threshold'],
                'gap': step['threshold'] - pe_pct,
                'label': step['label'],
                'ratio': step['ratio'] * 100
            }

    return {
        'threshold': None,
        'gap': 0,
        'label': '已全部触发',
        'ratio': 100
    }
