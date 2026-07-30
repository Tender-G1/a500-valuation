"""
多指数扩展模块（N6）
"""
import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from calculator import calc_percentile, calc_erp

logger = logging.getLogger(__name__)

# 指数代码到名称的映射（中证官网接口）
INDEX_INFO = {
    '000300': {'name': '沪深300', 'desc': 'A股压舱石，中国核心资产的温度计'},
    '000510': {'name': '中证A500', 'desc': 'A股新标杆，全面覆盖龙头与成长'},
    '399006': {'name': '创业板指', 'desc': '创新孵化器，硬科技的聚集地'},
    '000905': {'name': '中证500', 'desc': '中小盘精选，专精特新的风向标'},
    '000688': {'name': '科创50', 'desc': '硬核科技先锋，高弹性的进攻利器'},
}

CSINDEX_URL = "https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe"
HEADERS = {
    "Referer": "https://www.csindex.com.cn",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}


def fetch_index_data(code: str, days: int = 3650) -> Optional[pd.DataFrame]:
    """
    拉取单个指数的PE/PB历史数据
    """
    try:
        import time
        params = {"indexCode": code, "_t": int(time.time() * 1000)}
        resp = requests.get(CSINDEX_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if data.get('code') != '200':
            return None
        rows = data.get('data', [])
        if not rows:
            return None

        records = []
        for row in rows:
            date_str = str(row.get('tradeDate', ''))
            if len(date_str) == 8:
                date = datetime.strptime(date_str, '%Y%m%d').date()
                pe = row.get('peg')
                pb = row.get('pb')
                if pe and float(pe) > 0:
                    records.append({
                        'date': date,
                        'pe_ttm': float(pe),
                        'pb': float(pb) if pb and float(pb) > 0 else None,
                        'bond_yield_10y': None
                    })
        df = pd.DataFrame(records)
        if df.empty:
            return None
        df = df.sort_values('date').reset_index(drop=True)
        return df
    except Exception as e:
        logger.error(f"拉取指数 {code} 失败: {e}")
        return None


def scan_all_indices(config: Dict, bond_yield: float) -> List[Dict]:
    """
    扫描所有指数，计算估值分位
    """
    indices = config.get('multi_index', {}).get('indices', [])
    results = []

    for idx_info in indices:
        if not idx_info.get('enabled', False):
            continue
        code = idx_info['code']
        name = idx_info['name']

        df = fetch_index_data(code)
        if df is None or df.empty:
            continue

        # 填充国债收益率
        df['bond_yield_10y'] = bond_yield

        # 计算近10年分位
        today = df.iloc[-1]
        cutoff = today['date'] - timedelta(days=3650)
        df_10y = df[df['date'] >= cutoff]
        if len(df_10y) < 252:
            base_df = df
            base_label = "自基日"
        else:
            base_df = df_10y
            base_label = "近10年"

        pe_pct = calc_percentile(today['pe_ttm'], base_df['pe_ttm'].tolist())
        pb_pct = calc_percentile(today['pb'], base_df['pb'].dropna().tolist()) if today['pb'] else 50.0
        erp = calc_erp(today['pe_ttm'], bond_yield)
        erp_series = [calc_erp(p, b) for p, b in zip(base_df['pe_ttm'], base_df['bond_yield_10y'])]
        erp_pct = calc_percentile(erp, erp_series)

        # 状态判断
        if pe_pct < 30:
            status = "🟢 低估"
            advice = "值得关注，可分批布局"
        elif pe_pct < 70:
            status = "🟡 中性"
            advice = "维持现有仓位"
        else:
            status = "🔴 高估"
            advice = "注意风险，建议减仓"

        # 一句话画像
        desc = INDEX_INFO.get(code, {}).get('desc', f'{name}指数')

        results.append({
            'code': code,
            'name': name,
            'pe_pct': pe_pct,
            'pb_pct': pb_pct,
            'erp_pct': erp_pct,
            'pe': today['pe_ttm'],
            'pb': today['pb'] if today['pb'] else 0,
            'status': status,
            'advice': advice,
            'description': desc,
            'base_label': base_label
        })

    # 按PE分位排序（低估在前）
    results.sort(key=lambda x: x['pe_pct'])
    return results
