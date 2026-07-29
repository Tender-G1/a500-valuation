"""
数据管理模块：负责读取/写入CSV，调用中证官网API获取全量历史及增量更新。
"""
import requests
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# 中证指数官网API配置
CSINDEX_URL = "https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe"
HEADERS = {
    "Referer": "https://www.csindex.com.cn",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
}
INDEX_CODE = "000510"  # 中证A500

def fetch_full_history() -> pd.DataFrame:
    """
    全量拉取自指数基日（2004-12-31）至今的PE/PB数据。
    若失败则抛出异常。
    """
    logger.info("开始全量拉取历史数据（自2004年）...")
    try:
        resp = requests.get(CSINDEX_URL, params={"indexCode": INDEX_CODE}, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
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
                pb = row.get("pb")  # 中证API可能返回pb字段
                if pe and float(pe) > 0:
                    records.append({
                        "date": date,
                        "pe_ttm": float(pe),
                        "pb": float(pb) if pb and float(pb) > 0 else None,
                        "bond_yield_10y": None  # 国债收益率需单独获取，稍后填充
                    })
        df = pd.DataFrame(records)
        if df.empty:
            raise RuntimeError("解析后无有效数据")
        # 按日期升序
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
    """
    增量拉取最新一个交易日的数据（仅当有新数据时）。
    返回 (data_dict, fetched_flag)，其中 data_dict 包含 'date', 'pe_ttm', 'pb'。
    若拉取失败或已是最新，则返回 (None, False)。
    """
    logger.info("尝试增量拉取最新数据...")
    try:
        resp = requests.get(CSINDEX_URL, params={"indexCode": INDEX_CODE}, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
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

def fetch_bond_yield() -> Optional[float]:
    """
    获取最新10年期国债收益率（%）。
    使用 akshare 接口，若失败返回 None。
    """
    try:
        import akshare as ak
        df = ak.bond_zh_us_rate()
        if df.empty:
            return None
        # 取最新一行（日期最新）
        latest = df.iloc[-1]
        # 列名可能为 '10年期国债收益率' 或类似，尝试获取
        for col in df.columns:
            if '10年' in col and '国债' in col:
                return float(latest[col])
        # 若未找到，尝试通用
        for col in ['10年', '10Y']:
            if col in df.columns:
                return float(latest[col])
        return None
    except Exception as e:
        logger.error(f"获取国债收益率失败: {e}")
        return None

def load_or_init_csv(csv_path: str) -> pd.DataFrame:
    """
    加载CSV，若不存在则全量拉取并写入，同时补充国债收益率（用最新值填充所有记录）。
    """
    import os
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, parse_dates=["date"])
        logger.info(f"已加载CSV，共 {len(df)} 条记录，最新日期 {df['date'].max()}")
        return df
    else:
        logger.info("CSV不存在，执行全量初始化...")
        df = fetch_full_history()
        # 获取最新国债收益率
        bond = fetch_bond_yield()
        if bond is not None:
            df["bond_yield_10y"] = bond
        else:
            df["bond_yield_10y"] = 3.0  # 默认值（保守）
            logger.warning("未获取到国债收益率，使用默认值3.0%")
        # 保存
        df.to_csv(csv_path, index=False)
        logger.info(f"CSV初始化完成，保存至 {csv_path}")
        return df

def append_latest_data(df: pd.DataFrame, latest: dict, csv_path: str, bond_yield: float = None) -> pd.DataFrame:
    """
    将最新数据追加到DataFrame，若日期已存在则跳过，并更新国债收益率（如有）。
    返回更新后的DataFrame，并自动保存CSV。
    """
    new_date = latest["date"]
    if new_date <= df["date"].max():
        logger.info(f"数据已是最新（{new_date}），无需追加")
        return df
    # 创建新行
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