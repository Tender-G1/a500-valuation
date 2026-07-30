"""
资金仓位管理模块（N1）
"""
import pandas as pd
from datetime import datetime
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


def get_fund_status(config: Dict) -> Dict:
    """
    计算资金池状态
    返回：各层级金额、日收益、可用状态
    """
    total = config.get('total_pool', 100000)
    tiers = config.get('tiers', [])

    result = {
        'total': total,
        'daily_income': 0,
        'tiers': []
    }

    for tier in tiers:
        amount = total * tier.get('ratio', 0)
        daily_income = amount * (tier.get('annual_yield', 2.0) / 100) / 365
        result['daily_income'] += daily_income
        result['tiers'].append({
            'name': tier.get('name', ''),
            'amount': amount,
            'ratio': tier.get('ratio', 0) * 100,
            'annual_yield': tier.get('annual_yield', 0),
            'daily_income': daily_income,
            'availability': tier.get('availability', 'T+0'),
            'available_now': tier.get('availability') in ['T+0', 'T+1']
        })

    return result


def suggest_fund_source(fund_status: Dict, buy_amount: float) -> Dict:
    """
    建议从哪一层级取用资金
    优先使用T+0可用且收益率最低的层级
    """
    available = [t for t in fund_status['tiers'] if t['available_now'] and t['amount'] > 0]
    if not available:
        return {'suggestion': '无可用资金，请等待或调整配置'}

    # 按收益率升序排列（先花掉收益最低的）
    available.sort(key=lambda x: x['annual_yield'])

    suggestion = []
    remaining = buy_amount
    for tier in available:
        if remaining <= 0:
            break
        take = min(tier['amount'], remaining)
        if take > 0:
            suggestion.append({
                'tier_name': tier['name'],
                'take_amount': take,
                'remaining_after': tier['amount'] - take
            })
            remaining -= take

    return {
        'suggestion': suggestion,
        'can_cover': remaining <= 0,
        'shortfall': max(0, remaining)
    }
