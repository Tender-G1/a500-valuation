import os
import json
import pandas as pd
from flask import Flask, request, jsonify
from flask_cors import CORS  # 允许跨域请求
from datetime import date
from portfolio_manager import load_portfolio, save_portfolio, add_transaction

app = Flask(__name__)
CORS(app)  # 允许前端域名跨域访问

# 从环境变量读取加密密钥（需在 Vercel 中设置）
PORTFOLIO_KEY = os.environ.get("PORTFOLIO_KEY")
if not PORTFOLIO_KEY:
    raise RuntimeError("PORTFOLIO_KEY environment variable not set")

@app.route("/api/transaction", methods=["POST"])
def add_transaction_api():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Missing JSON body"}), 400

        required = ["index_code", "index_name", "action", "amount"]
        for f in required:
            if f not in data:
                return jsonify({"success": False, "error": f"Missing field: {f}"}), 400

        df = load_portfolio(PORTFOLIO_KEY)
        price = data.get("price", 0)
        df = add_transaction(
            df,
            index_code=data["index_code"],
            index_name=data["index_name"],
            action=data["action"],
            amount=float(data["amount"]),
            price=float(price) if price else None
        )
        save_portfolio(df, PORTFOLIO_KEY)
        return jsonify({"success": True, "message": "Transaction saved"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    try:
        df = load_portfolio(PORTFOLIO_KEY)
        records = df.to_dict(orient="records")
        for r in records:
            if "date" in r and hasattr(r["date"], "isoformat"):
                r["date"] = r["date"].isoformat()
        return jsonify({"success": True, "data": records})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
