"""
生成静态网站文件（M4：同步部署推送图 + 注入多指数/资金/持仓数据）
"""
import json
import os
import shutil
import pandas as pd
from datetime import datetime, timedelta
from jinja2 import Template
from calculator import calc_percentile, calc_erp
from multi_index import scan_all_indices
from fund_manager import get_fund_status
from portfolio_manager import load_portfolio, calc_portfolio_summary

CSV_PATH = "history_data.csv"
SITE_DIR = "site"


def get_base_df(df, today, config_min_days=252):
    cutoff = today["date"] - timedelta(days=3650)
    df_10y = df[df["date"] >= cutoff]
    use_rolling = len(df_10y) >= config_min_days
    base_df = df_10y if use_rolling else df
    base_label = "近10年" if use_rolling else "自基日"
    return base_df, base_label, use_rolling


def generate(chart_path: str = "chart.png", config: dict = None, bond_yield: float = None):
    """生成网站文件"""
    os.makedirs(SITE_DIR, exist_ok=True)

    # M4：复制推送图到网站目录
    if os.path.exists(chart_path):
        shutil.copy(chart_path, f"{SITE_DIR}/chart.png")
        print("✅ 推送图已复制到网站目录")

    # 读取数据
    df = pd.read_csv(CSV_PATH, parse_dates=["date"])
    today = df.iloc[-1]
    bond = bond_yield if bond_yield else df["bond_yield_10y"].iloc[-1]

    # 计算主基准
    base_df, base_label, use_rolling = get_base_df(df, today)
    pe_pct = calc_percentile(today["pe_ttm"], base_df["pe_ttm"].tolist())
    pb_pct = calc_percentile(today["pb"], base_df["pb"].dropna().tolist()) if today["pb"] else 50.0
    erp = calc_erp(today["pe_ttm"], bond)
    erp_series = [calc_erp(p, b) for p, b in zip(base_df["pe_ttm"], base_df["bond_yield_10y"])]
    erp_pct = calc_percentile(erp, erp_series)

    # 自基日参考
    full_pe_pct = calc_percentile(today["pe_ttm"], df["pe_ttm"].tolist())
    full_pb_pct = calc_percentile(today["pb"], df["pb"].dropna().tolist()) if today["pb"] else 50.0
    full_erp_series = [calc_erp(p, b) for p, b in zip(df["pe_ttm"], df["bond_yield_10y"])]
    full_erp_pct = calc_percentile(erp, full_erp_series)

    # 分位变化
    delta = 0
    if len(df) >= 2:
        yesterday = df.iloc[-2]
        yesterday_pct = calc_percentile(yesterday["pe_ttm"], base_df["pe_ttm"].tolist())
        delta = pe_pct - yesterday_pct

    # ─── 网站图表数据（全历史，使用固定基准） ───
    chart_data = {
        "dates": [d.strftime("%Y-%m-%d") for d in df["date"]],
        "pe": [float(x) for x in df["pe_ttm"]],
        "pb": [float(x) if pd.notna(x) else None for x in df["pb"]],
        "pe_pct": [],
        "erp_pct": []
    }
    for i in range(len(df)):
        temp_df = df.iloc[:i+1]
        temp_base, _, _ = get_base_df(temp_df, temp_df.iloc[-1])
        if len(temp_base) > 0:
            pe_series = temp_base["pe_ttm"].tolist()
            chart_data["pe_pct"].append(calc_percentile(temp_df.iloc[-1]["pe_ttm"], pe_series))
            erp_series = [calc_erp(p, b) for p, b in zip(temp_base["pe_ttm"], temp_base["bond_yield_10y"])]
            chart_data["erp_pct"].append(calc_percentile(calc_erp(temp_df.iloc[-1]["pe_ttm"], temp_df.iloc[-1]["bond_yield_10y"]), erp_series))
        else:
            chart_data["pe_pct"].append(50.0)
            chart_data["erp_pct"].append(50.0)

    # 阈值线
    pe_sorted = sorted(base_df["pe_ttm"].dropna())
    chart_data["pe_20"] = pe_sorted[int(0.2 * len(pe_sorted))] if len(pe_sorted) > 0 else None
    chart_data["pe_80"] = pe_sorted[int(0.8 * len(pe_sorted))] if len(pe_sorted) > 0 else None

    # ─── 多指数数据 ──────────────────────────────
    multi_results = []
    if config:
        multi_results = scan_all_indices(config, bond)

    # ─── 资金数据 ────────────────────────────────
    fund_status = {}
    if config:
        fund_status = get_fund_status(config.get('fund', {}))

    # ─── 持仓数据 ────────────────────────────────
    portfolio_key = os.environ.get("PORTFOLIO_KEY")
    portfolio_summary = {'total_cost': 0, 'total_market_value': 0,
                         'total_profit': 0, 'total_return': 0, 'holdings': []}
    if portfolio_key:
        try:
            df_portfolio = load_portfolio(portfolio_key)
            current_prices = {'000510': float(today['pe_ttm'])}
            for r in multi_results:
                if r.get('pe'):
                    current_prices[r['code']] = float(r['pe'])
            portfolio_summary = calc_portfolio_summary(df_portfolio, current_prices)
        except Exception as e:
            print(f"持仓加载失败: {e}")

    # ─── 生成 data.js ──────────────────────────────
    js_content = f"""
const chartData = {json.dumps(chart_data, ensure_ascii=False)};
const latestData = {{
    date: {json.dumps(today['date'].strftime('%Y-%m-%d'), ensure_ascii=False)},
    pe_pct: {pe_pct},
    erp_pct: {erp_pct},
    delta: {delta}
}};
const baseLabel = {json.dumps(base_label, ensure_ascii=False)};
const multiIndexData = {json.dumps(multi_results, ensure_ascii=False, default=str)};
const fundData = {json.dumps(fund_status, ensure_ascii=False, default=str)};
const portfolioData = {json.dumps(portfolio_summary, ensure_ascii=False, default=str)};
"""
    with open(f"{SITE_DIR}/data.js", "w", encoding="utf-8") as f:
        f.write(js_content)

    # 复制静态文件（index.html, style.css, script.js）
    # 这些文件已存在，无需生成

    # 写入 .site_generated 标记
    with open(f"{SITE_DIR}/.site_generated", "w") as f:
        f.write(f"generated at {datetime.now().isoformat()}")

    print(f"✅ 网站文件已生成到 {SITE_DIR}/")
