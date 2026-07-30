"""
持仓管理模块（N3：持仓追踪 + N4：加密存储）
"""
import os
import json
import base64
import pandas as pd
import logging
from datetime import datetime, date
from typing import Optional, List, Dict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

PORTFOLIO_FILE = "portfolio.enc"  # 加密后的持仓文件
PORTFOLIO_CSV = "portfolio.csv"   # 临时明文（仅内存操作）


# ─── N4：加密/解密工具 ──────────────────────────────
def _derive_key(password: str, salt: bytes = None) -> tuple:
    """从密码派生Fernet密钥"""
    if salt is None:
        salt = b'a500_salt_2026'
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


def encrypt_portfolio(df: pd.DataFrame, password: str) -> bytes:
    """加密持仓DataFrame"""
    if df.empty:
        return b''
    json_str = df.to_json(orient='records', date_format='iso')
    key, _ = _derive_key(password)
    f = Fernet(key)
    return f.encrypt(json_str.encode())


def decrypt_portfolio(encrypted: bytes, password: str) -> pd.DataFrame:
    """解密持仓DataFrame"""
    if not encrypted:
        return pd.DataFrame()
    key, _ = _derive_key(password)
    f = Fernet(key)
    try:
        decrypted = f.decrypt(encrypted)
        df = pd.read_json(decrypted.decode(), orient='records')
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.date
        return df
    except Exception as e:
        logger.error(f"解密失败: {e}")
        return pd.DataFrame()


def load_portfolio(password: str) -> pd.DataFrame:
    """加载持仓数据（从加密文件解密）"""
    if not os.path.exists(PORTFOLIO_FILE):
        logger.info("持仓文件不存在，返回空DataFrame")
        return pd.DataFrame(columns=['date', 'index_code', 'index_name', 'action', 'amount', 'price', 'shares'])
    try:
        with open(PORTFOLIO_FILE, 'rb') as f:
            encrypted = f.read()
        return decrypt_portfolio(encrypted, password)
    except Exception as e:
        logger.error(f"加载持仓失败: {e}")
        return pd.DataFrame()


def save_portfolio(df: pd.DataFrame, password: str):
    """保存持仓数据（加密）"""
    encrypted = encrypt_portfolio(df, password)
    with open(PORTFOLIO_FILE, 'wb') as f:
        f.write(encrypted)
    logger.info(f"持仓数据已加密保存，共 {len(df)} 条记录")


def add_transaction(df: pd.DataFrame, index_code: str, index_name: str,
                    action: str, amount: float, price: float = None) -> pd.DataFrame:
    """
    添加交易记录
    action: 'buy' 或 'sell'
    amount: 交易金额（元）
    price: 成交价格（可选，用于计算份额）
    """
    new_row = {
        'date': date.today(),
        'index_code': index_code,
        'index_name': index_name,
        'action': action,
        'amount': amount,
        'price': price if price else 0,
        'shares': amount / price if price and price > 0 else 0
    }
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)


def calc_portfolio_summary(df: pd.DataFrame, current_prices: Dict[str, float]) -> Dict:
    """
    计算持仓汇总
    current_prices: {index_code: current_price} 当前价格（可用PE代替）
    """
    if df.empty:
        return {
            'total_cost': 0,
            'total_market_value': 0,
            'total_profit': 0,
            'total_return': 0,
            'holdings': []
        }

    # 按指数分组
    holdings = []
    for idx in df['index_code'].unique():
        idx_df = df[df['index_code'] == idx]
        buys = idx_df[idx_df['action'] == 'buy']
        sells = idx_df[idx_df['action'] == 'sell']

        cost = buys['amount'].sum() - sells['amount'].sum()
        shares = buys['shares'].sum() - sells['shares'].sum()
        current_price = current_prices.get(idx, 0)
        market_value = shares * current_price if shares > 0 else 0

        holdings.append({
            'index_code': idx,
            'index_name': idx_df.iloc[0]['index_name'],
            'cost': cost,
            'shares': shares,
            'current_price': current_price,
            'market_value': market_value,
            'profit': market_value - cost,
            'return_pct': (market_value - cost) / cost * 100 if cost > 0 else 0
        })

    total_cost = sum(h['cost'] for h in holdings)
    total_mv = sum(h['market_value'] for h in holdings)

    return {
        'total_cost': total_cost,
        'total_market_value': total_mv,
        'total_profit': total_mv - total_cost,
        'total_return': (total_mv - total_cost) / total_cost * 100 if total_cost > 0 else 0,
        'holdings': holdings
    }
