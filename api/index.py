# api/index.py
import os
import json
import pandas as pd
from flask import Flask, request, jsonify
from datetime import date
from portfolio_manager import load_portfolio, save_portfolio, add_transaction

app = Flask(__name__)

# 从环境变量读取加密密钥（需在 Vercel 中设置）
PORTFOLIO_KEY = os.environ.get("PORTFOLIO_KEY")
if not PORTFOLIO_KEY:
    raise RuntimeError("PORTFOLIO_KEY environment variable not set")

@app.route("/api/transaction", methods=["POST"])
def add_transaction_api():
    """接收交易记录并加密保存"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Missing JSON body"}), 400

        # 验证字段
        required = ["index_code", "index_name", "action", "amount"]
        for f in required:
            if f not in data:
                return jsonify({"success": False, "error": f"Missing field: {f}"}), 400

        # 加载现有持仓
        df = load_portfolio(PORTFOLIO_KEY)

        # 添加新交易
        price = data.get("price", 0)
        df = add_transaction(
            df,
            index_code=data["index_code"],
            index_name=data["index_name"],
            action=data["action"],
            amount=float(data["amount"]),
            price=float(price) if price else None
        )

        # 加密保存
        save_portfolio(df, PORTFOLIO_KEY)

        return jsonify({"success": True, "message": "Transaction saved"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    """返回当前持仓汇总（解密后）"""
    try:
        df = load_portfolio(PORTFOLIO_KEY)
        # 这里可以进一步计算汇总，但为了简单，返回原始数据（加密传输？实际已解密）
        # 由于返回给前端，需要确保数据不包含敏感信息（但前端本身需认证）
        records = df.to_dict(orient="records")
        # 日期转为字符串
        for r in records:
            if "date" in r and hasattr(r["date"], "isoformat"):
                r["date"] = r["date"].isoformat()
        return jsonify({"success": True, "data": records})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Vercel 需要导出一个名为 app 的变量
# 但 Vercel 的 Python 环境会自动识别 Flask 实例
# 如果使用 vercel dev，需要添加这个
if __name__ == "__main__":
    app.run(debug=True)
