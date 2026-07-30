"""
数据管理：CSV读写 + 中证API全量/增量拉取（含timestamp参数）
"""
import requests
import pandas as pd
import logging
from datetime import datetime
from typing import Tuple, Optional
import time

logger = logging.getLogger(__name__)

CSINDEX_URL = "https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe"
HEADERS = {
    "Referer": "https://www.csindex.com.cn",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}
INDEX_CODE = "000510"

# ─── H1：带timestamp的请求函数 ─────────────────────
def _request_with_timestamp(params: dict) -> dict:
    """统一请求函数，自动添加 _t 时间戳参数"""
    params_with_ts = {**params, "_t": int(time.time() * 1000)}
    resp = requests.get(CSINDEX_URL, params=params_with_ts, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_full_history() -> pd.DataFrame:
    """全量拉取自2004年至今"""
    logger.info("开始全量拉取历史数据（自2004年）...")
    try:
        data = _request_with_timestamp({"indexCode": INDEX_CODE})
        if data.get("code") != "200":
            raise RuntimeError(f"API返回错误: {data.get('msg')}")
        rows = data.get("data", [])
        if not rows:
            raise RuntimeError("API返回空数据")
        records = []
        for row in rows:
            date_str = str(row.get("tradeDate", ""))
            if len(date_str) == 8:
                date = datetime.strptime(date_str, "%Y%m%d").date()
                pe = row.get("peg")
                pb = row.get("pb")
                if pe and float(pe) > 0:
                    records.append({
                        "date": date,
                        "pe_ttm": float(pe),
                        "pb": float(pb) if pb and float(pb) > 0 else None,
                        "bond_yield_10y": None
                    })
        df = pd.DataFrame(records)
        if df.empty:
            raise RuntimeError("解析后无有效数据")
        df = df.sort_values("date").reset_index(drop=True)
        logger.info(f"全量拉取完成，共 {len(df)} 条记录")
        return df
    except requests.exceptions.Timeout:
        logger.error("API请求超时")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"网络请求异常: {e}")
        raise
    except Exception as e:
        logger.error(f"全量拉取失败: {e}")
        raise


def fetch_latest_pe_pb() -> Tuple[Optional[dict], bool]:
    """增量拉取最新交易日数据（带timestamp）"""
    logger.info("尝试增量拉取最新数据...")
    try:
        data = _request_with_timestamp({"indexCode": INDEX_CODE})
        if data.get("code") != "200":
            logger.warning(f"API返回非200: {data.get('msg')}")
            return None, False
        rows = data.get("data", [])
        if not rows:
            return None, False
        latest = rows[-1]
        date_str = str(latest.get("tradeDate", ""))
        if len(date_str) != 8:
            return None, False
        pe = latest.get("peg")
        pb = latest.get("pb")
        if not pe or float(pe) <= 0:
            return None, False
        return {
            "date": datetime.strptime(date_str, "%Y%m%d").date(),
            "pe_ttm": float(pe),
            "pb": float(pb) if pb and float(pb) > 0 else None
        }, True
    except requests.exceptions.Timeout:
        logger.error("增量拉取超时")
        return None, False
    except KeyError as e:
        logger.error(f"接口数据结构异常（可能改版）: {e}")
        return None, False
    except Exception as e:
        logger.error(f"增量拉取未知异常: {e}")
        return None, False


# ─── H3：国债收益率容灾方案 ──────────────────────────
def fetch_bond_yield_fallback() -> Optional[float]:
    """
    获取10年期国债收益率，含多层容灾：
    方案A: akshare
    方案B: 东方财富备用接口
    方案C: 返回None，由调用方使用上一交易日值
    """
    # 方案A：akshare（主）
    try:
        import akshare as ak
        df = ak.bond_zh_us_rate()
        if not df.empty:
            latest = df.iloc[-1]
            for col in df.columns:
                if '10年' in col and '国债' in col:
                    return float(latest[col])
            for col in ['10年', '10Y']:
                if col in df.columns:
                    return float(latest[col])
    except Exception as e:
        logger.warning(f"akshare获取国债收益率失败: {e}")

    # 方案B：东方财富备用接口
    try:
        url = "https://datacenter-web.eastmoney.com/api/data/get"
        params = {
            "type": "RPTA_WEB_TREASURYYIELD",
            "sty": "ALL",
            "st": "TRADE_DATE",
            "sr": "-1",
            "p": "1",
            "ps": "1",
            "token": "894905c73af8cb03c5bd327b33f70cd9"
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("result", {}).get("data", [])
        if rows:
            latest = rows[0]
            # 尝试获取10年期
            for key in ["EMM00566204", "EMM00566205", "EMM00566206"]:
                if key in latest and latest[key]:
                    return float(latest[key])
            # 尝试任意列名包含"10"
            for k, v in latest.items():
                if "10" in k and v and isinstance(v, (int, float, str)):
                    try:
                        return float(v)
                    except:
                        continue
    except Exception as e:
        logger.warning(f"东方财富备用接口获取国债收益率失败: {e}")

    # 方案C：返回None，由调用方使用上一交易日值
    logger.warning("所有国债收益率接口均失败，将使用上一交易日值")
    return None


# ─── 数据加载与写入 ──────────────────────────────────
def load_or_init_csv(csv_path: str) -> pd.DataFrame:
    import os
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, parse_dates=["date"])
        logger.info(f"已加载CSV，共 {len(df)} 条记录")
        return df
    else:
        logger.info("CSV不存在，执行全量初始化...")
        df = fetch_full_history()
        bond = fetch_bond_yield_fallback()
        if bond is not None:
            df["bond_yield_10y"] = bond
        else:
            # H3：仅首次运行且完全无数据时才使用默认值
            df["bond_yield_10y"] = 3.0
            logger.warning("首次运行无历史数据，使用默认值3.0%（建议后续手动更新）")
        df.to_csv(csv_path, index=False)
        logger.info(f"CSV初始化完成，保存至 {csv_path}")
        return df


def append_latest_data(df: pd.DataFrame, latest: dict, csv_path: str, bond_yield: float = None) -> pd.DataFrame:
    new_date = latest["date"]
    if new_date <= df["date"].max():
        logger.info(f"数据已是最新（{new_date}），无需追加")
        return df
    new_row = {
        "date": new_date,
        "pe_ttm": latest["pe_ttm"],
        "pb": latest.get("pb"),
        "bond_yield_10y": bond_yield if bond_yield is not None else df["bond_yield_10y"].iloc[-1]
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(csv_path, index=False)
    logger.info(f"追加数据成功，新日期 {new_date}")
    return df
