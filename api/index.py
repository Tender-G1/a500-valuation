"""
Vercel Serverless API：持仓数据加密存储 + 读取
使用 GitHub API 持久化加密文件，避免 Vercel 临时存储丢失数据
"""
import os
import json
import base64
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import date
import requests

app = Flask(__name__)
CORS(app)

# ─── 环境变量 ──────────────────────────────────────────
PORTFOLIO_KEY = os.environ.get("PORTFOLIO_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO_OWNER = os.environ.get("REPO_OWNER")
REPO_NAME = os.environ.get("REPO_NAME")
GITHUB_API_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/portfolio.enc"

if not PORTFOLIO_KEY:
    raise RuntimeError("PORTFOLIO_KEY environment variable not set")


# ─── 加密/解密工具（与 portfolio_manager.py 保持一致） ──
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64 as b64


def _derive_key(password: str) -> bytes:
    salt = b'a500_salt_2026'
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = b64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key


def encrypt_data(data: str, password: str) -> bytes:
    key = _derive_key(password)
    f = Fernet(key)
    return f.encrypt(data.encode())


def decrypt_data(encrypted: bytes, password: str) -> str:
    key = _derive_key(password)
    f = Fernet(key)
    return f.decrypt(encrypted).decode()


# ─── GitHub API 读写 ──────────────────────────────────

def read_from_github() -> bytes:
    """从 GitHub 仓库读取 portfolio.enc 文件内容"""
    if not GITHUB_TOKEN:
        return b''
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    try:
        resp = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return base64.b64decode(data["content"])
        elif resp.status_code == 404:
            return b''
        else:
            app.logger.error(f"GitHub读取失败: {resp.status_code}")
            return b''
    except Exception as e:
        app.logger.error(f"GitHub读取异常: {e}")
        return b''


def write_to_github(content: bytes, commit_message: str = "Update portfolio") -> bool:
    """写入 portfolio.enc 到 GitHub 仓库"""
    if not GITHUB_TOKEN:
        app.logger.error("GITHUB_TOKEN 未设置")
        return False
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    # 先获取当前文件的 SHA（用于更新）
    try:
        resp = requests.get(GITHUB_API_URL, headers=headers, timeout=10)
        sha = resp.json().get("sha") if resp.status_code == 200 else None
    except:
        sha = None

    payload = {
        "message": commit_message,
        "content": base64.b64encode(content).decode("utf-8"),
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha

    try:
        resp = requests.put(GITHUB_API_URL, headers=headers, json=payload, timeout=15)
        if resp.status_code in [200, 201]:
            app.logger.info("GitHub写入成功")
            return True
        else:
            app.logger.error(f"GitHub写入失败: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        app.logger.error(f"GitHub写入异常: {e}")
        return False


# ─── 持仓数据操作 ─────────────────────────────────────

def load_portfolio() -> pd.DataFrame:
    """加载持仓数据（从GitHub解密）"""
    encrypted = read_from_github()
    if not encrypted:
        return pd.DataFrame(columns=['date', 'index_code', 'index_name', 'action', 'amount', 'price', 'shares'])
    try:
        decrypted = decrypt_data(encrypted, PORTFOLIO_KEY)
        df = pd.read_json(decrypted, orient='records')
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.date
        return df
    except Exception as e:
        app.logger.error(f"解密失败: {e}")
        return pd.DataFrame(columns=['date', 'index_code', 'index_name', 'action', 'amount', 'price', 'shares'])


def save_portfolio(df: pd.DataFrame) -> bool:
    """保存持仓数据（加密后写入GitHub）"""
    if df.empty:
        encrypted = encrypt_data("[]", PORTFOLIO_KEY)
    else:
        json_str = df.to_json(orient='records', date_format='iso', force_ascii=False)
        encrypted = encrypt_data(json_str, PORTFOLIO_KEY)
    return write_to_github(encrypted, f"Update portfolio {date.today()}")


def add_transaction(df: pd.DataFrame, index_code: str, index_name: str,
                    action: str, amount: float, price: float = None) -> pd.DataFrame:
    """添加交易记录"""
    shares = amount / price if price and price > 0 else 0
    new_row = {
        'date': date.today().isoformat(),
        'index_code': index_code,
        'index_name': index_name,
        'action': action,
        'amount': amount,
        'price': price if price else 0,
        'shares': shares
    }
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)


def calc_portfolio_summary(df: pd.DataFrame, current_prices: dict) -> dict:
    """计算持仓汇总"""
    if df.empty:
        return {
            'total_cost': 0,
            'total_market_value': 0,
            'total_profit': 0,
            'total_return': 0,
            'holdings': []
        }

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
            'cost': round(cost, 2),
            'shares': round(shares, 4),
            'current_price': round(current_price, 4),
            'market_value': round(market_value, 2),
            'profit': round(market_value - cost, 2),
            'return_pct': round((market_value - cost) / cost * 100, 2) if cost > 0 else 0
        })

    total_cost = sum(h['cost'] for h in holdings)
    total_mv = sum(h['market_value'] for h in holdings)

    return {
        'total_cost': round(total_cost, 2),
        'total_market_value': round(total_mv, 2),
        'total_profit': round(total_mv - total_cost, 2),
        'total_return': round((total_mv - total_cost) / total_cost * 100, 2) if total_cost > 0 else 0,
        'holdings': holdings
    }


# ─── Flask 路由 ──────────────────────────────────────

@app.route("/api/transaction", methods=["POST"])
def add_transaction_api():
    """录入交易记录"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Missing JSON body"}), 400

        required = ["index_code", "index_name", "action", "amount"]
        for f in required:
            if f not in data:
                return jsonify({"success": False, "error": f"Missing field: {f}"}), 400

        df = load_portfolio()
        price = data.get("price", 0)
        df = add_transaction(
            df,
            index_code=data["index_code"],
            index_name=data["index_name"],
            action=data["action"],
            amount=float(data["amount"]),
            price=float(price) if price else None
        )
        success = save_portfolio(df)
        if success:
            return jsonify({"success": True, "message": "Transaction saved"})
        else:
            return jsonify({"success": False, "error": "Failed to save to GitHub"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    """获取持仓数据（加密传输）"""
    try:
        df = load_portfolio()
        records = df.to_dict(orient="records")
        return jsonify({"success": True, "data": records})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/portfolio_summary", methods=["POST"])
def get_portfolio_summary():
    """计算持仓汇总（需要传入当前价格）"""
    try:
        data = request.get_json()
        current_prices = data.get("current_prices", {}) if data else {}
        df = load_portfolio()
        summary = calc_portfolio_summary(df, current_prices)
        return jsonify({"success": True, "data": summary})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({"status": "ok"})


# ─── Vercel 入口 ─────────────────────────────────────

def handler(event, context):
    """Vercel Serverless 入口"""
    return app(event, context)
