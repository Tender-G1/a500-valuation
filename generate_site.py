"""
生成静态网站文件（V4.0 完整版，已修复 Emoji 编码问题）
"""
import json
import pandas as pd
import os
import shutil
from datetime import datetime, timedelta
from jinja2 import Template
from calculator import calc_percentile, calc_erp
from portfolio_manager import load_portfolio, calc_portfolio_summary
from fund_manager import get_fund_status
from multi_index import scan_all_indices

CSV_PATH = "history_data.csv"
SITE_DIR = "site"


def generate(chart_path: str = "chart.png"):
    """生成网站文件，复制推送图到网站目录"""
    os.makedirs(SITE_DIR, exist_ok=True)

    # 复制推送图
    if os.path.exists(chart_path):
        shutil.copy(chart_path, f"{SITE_DIR}/chart.png")

    # 读取数据
    df = pd.read_csv(CSV_PATH, parse_dates=["date"])
    today = df.iloc[-1]

    # 基准计算
    cutoff = today["date"] - timedelta(days=3650)
    df_10y = df[df["date"] >= cutoff]
    use_rolling = len(df_10y) >= 252
    base_df = df_10y if use_rolling else df
    base_label = "近10年" if use_rolling else "自基日"

    # 分位计算
    pe_pct = calc_percentile(today["pe_ttm"], base_df["pe_ttm"].tolist())
    pb_pct = calc_percentile(today["pb"], base_df["pb"].dropna().tolist()) if today["pb"] else 50.0
    erp = calc_erp(today["pe_ttm"], today["bond_yield_10y"])
    erp_series = [calc_erp(p, b) for p, b in zip(base_df["pe_ttm"], base_df["bond_yield_10y"])]
    erp_pct = calc_percentile(erp, erp_series)

    # 自基日参考
    full_pe_pct = calc_percentile(today["pe_ttm"], df["pe_ttm"].tolist())
    full_pb_pct = calc_percentile(today["pb"], df["pb"].dropna().tolist()) if today["pb"] else 50.0

    # 分位变化
    delta = 0
    if len(df) >= 2:
        yesterday = df.iloc[-2]
        yesterday_pct = calc_percentile(yesterday["pe_ttm"], base_df["pe_ttm"].tolist())
        delta = pe_pct - yesterday_pct

    # 结论
    if pe_pct >= 80:
        status_emoji = "🔴"
        status_text = f"高估区（{pe_pct:.0f}%），建议减仓"
    elif pe_pct >= 60:
        status_emoji = "🟡"
        status_text = f"偏高区（{pe_pct:.0f}%），距高估区还差 {80 - pe_pct:.0f} 个百分点"
    elif pe_pct >= 40:
        status_emoji = "⬜"
        status_text = f"中性区（{pe_pct:.0f}%），维持现有仓位"
    elif pe_pct >= 20:
        status_emoji = "🟢"
        status_text = f"偏低区（{pe_pct:.0f}%），可适度关注"
    else:
        status_emoji = "🟢"
        status_text = f"低估区（{pe_pct:.0f}%），建议分批布局"
    conclusion = f"{status_emoji} 当前估值{status_text}"

    # ─── 构建图表数据（所有 json.dumps 已加 ensure_ascii=False） ───
    chart_data = {
        "dates": [d.strftime("%Y-%m-%d") for d in df["date"]],
        "pe": [float(x) for x in df["pe_ttm"]],
        "pb": [float(x) if pd.notna(x) else None for x in df["pb"]],
        "pe_pct": [],
        "erp_pct": []
    }
    for i in range(len(df)):
        temp_df = df.iloc[:i+1]
        if len(temp_df) > 0:
            temp_cutoff = temp_df.iloc[-1]["date"] - timedelta(days=3650)
            temp_10y = temp_df[temp_df["date"] >= temp_cutoff]
            temp_base = temp_10y if len(temp_10y) >= 252 else temp_df
            pe_series = temp_base["pe_ttm"].tolist()
            chart_data["pe_pct"].append(calc_percentile(temp_df.iloc[-1]["pe_ttm"], pe_series))
            erp_series2 = [calc_erp(p, b) for p, b in zip(temp_base["pe_ttm"], temp_base["bond_yield_10y"])]
            chart_data["erp_pct"].append(calc_percentile(calc_erp(temp_df.iloc[-1]["pe_ttm"], temp_df.iloc[-1]["bond_yield_10y"]), erp_series2))
        else:
            chart_data["pe_pct"].append(50.0)
            chart_data["erp_pct"].append(50.0)

    pe_sorted = sorted(base_df["pe_ttm"].dropna())
    chart_data["pe_20"] = pe_sorted[int(0.2 * len(pe_sorted))] if len(pe_sorted) > 0 else None
    chart_data["pe_80"] = pe_sorted[int(0.8 * len(pe_sorted))] if len(pe_sorted) > 0 else None
    chart_data["full_pe_pct"] = full_pe_pct
    chart_data["full_pb_pct"] = full_pb_pct
    chart_data["base_label"] = base_label

    # ─── 读取持仓数据（如有） ──────────────────────────────────
    portfolio_data = {"total_cost": 0, "total_market_value": 0, "total_profit": 0, "total_return": 0, "holdings": []}
    fund_data = {"total": 0, "daily_income": 0, "tiers": []}
    multi_index_data = []

    # ⚠️ 此处需根据您的实际 config 和 portfolio_key 加载数据
    # 示例：仅用于测试，实际需从环境变量读取 PORTFOLIO_KEY

    # ─── 生成 data.js（全部使用 ensure_ascii=False） ──────────
    js_content = f"""
// 自动生成，请勿手动编辑（已修复 Emoji 编码）
const chartData = {json.dumps(chart_data, ensure_ascii=False)};
const latest = {json.dumps({
    'date': today['date'].strftime('%Y-%m-%d'),
    'pe': float(today['pe_ttm']),
    'pb': float(today['pb']) if pd.notna(today['pb']) else None,
    'pe_pct': pe_pct
}, ensure_ascii=False)};
const conclusionText = {json.dumps(conclusion, ensure_ascii=False)};
const baseLabel = {json.dumps(base_label, ensure_ascii=False)};
const portfolioData = {json.dumps(portfolio_data, ensure_ascii=False)};
const fundData = {json.dumps(fund_data, ensure_ascii=False)};
const multiIndexData = {json.dumps(multi_index_data, ensure_ascii=False)};
"""

    with open(f"{SITE_DIR}/data.js", "w", encoding="utf-8") as f:
        f.write(js_content)

    # ─── 写入生成标记（供 Actions 检查） ──────────────────────
    with open(f"{SITE_DIR}/.site_generated", "w") as f:
        f.write(f"generated at {datetime.now().isoformat()}")

    print(f"✅ 网站文件已生成到 {SITE_DIR}/")


if __name__ == "__main__":
    generate()
