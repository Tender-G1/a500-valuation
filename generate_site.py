"""
生成静态网站文件（HTML + JS + CSS）
H2: 统一使用固定基准（与main.py一致）
M1: 图表中标记今日位置
M3: 从calculator导入calc_percentile
"""
import json
import pandas as pd
import os
from datetime import datetime, timedelta
from jinja2 import Template
from calculator import calc_percentile, calc_erp  # M3：从统一模块导入

CSV_PATH = "history_data.csv"
SITE_DIR = "site"


def get_base_df(df, today, config_min_days=252):
    """与main.py保持完全一致的基准选择逻辑"""
    cutoff = today["date"] - timedelta(days=3650)
    df_10y = df[df["date"] >= cutoff]
    use_rolling = len(df_10y) >= config_min_days
    base_df = df_10y if use_rolling else df
    base_label = "近10年" if use_rolling else "自基日"
    return base_df, base_label, use_rolling


def generate():
    os.makedirs(SITE_DIR, exist_ok=True)
    df = pd.read_csv(CSV_PATH, parse_dates=["date"])
    today = df.iloc[-1]

    # H2：使用与main.py完全一致的基准
    base_df, base_label, use_rolling = get_base_df(df, today)

    # 计算主基准分位
    pe_pct = calc_percentile(today["pe_ttm"], base_df["pe_ttm"].tolist())
    pb_pct = calc_percentile(today["pb"], base_df["pb"].dropna().tolist()) if today["pb"] else 50.0
    erp = calc_erp(today["pe_ttm"], today["bond_yield_10y"])
    erp_series = [calc_erp(p, b) for p, b in zip(base_df["pe_ttm"], base_df["bond_yield_10y"])]
    erp_pct = calc_percentile(erp, erp_series)

    # 自基日分位（参考显示）
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

    # ─── 网站图表数据（H2：使用固定基准计算全历史分位） ───
    chart_data = {
        "dates": [d.strftime("%Y-%m-%d") for d in df["date"]],
        "pe": [float(x) for x in df["pe_ttm"]],
        "pb": [float(x) if pd.notna(x) else None for x in df["pb"]],
        "pe_pct": [],
        "erp_pct": []
    }

    # H2：对每一天，使用相同的固定基准窗口计算分位
    for i in range(len(df)):
        current_date = df.iloc[i]["date"]
        # 用截至当天的数据计算基准窗口
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

    # 阈值线（基于主基准）
    pe_sorted = sorted(base_df["pe_ttm"].dropna())
    chart_data["pe_20"] = pe_sorted[int(0.2 * len(pe_sorted))] if len(pe_sorted) > 0 else None
    chart_data["pe_80"] = pe_sorted[int(0.8 * len(pe_sorted))] if len(pe_sorted) > 0 else None

    # 今日位置
    chart_data["today_index"] = len(df) - 1
    chart_data["today_pe_pct"] = pe_pct

    # 生成结论文字
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

    # 生成 data.js（M1：包含今日标记信息）
    js_content = f"""
// 自动生成，请勿手动编辑
const chartData = {json.dumps(chart_data, ensure_ascii=False)};
const latest = {json.dumps({'date': today['date'].strftime('%Y-%m-%d'), 'pe': float(today['pe_ttm']), 'pb': float(today['pb']) if pd.notna(today['pb']) else None, 'pe_pct': pe_pct}, ensure_ascii=False)};
const conclusionText = {json.dumps(conclusion, ensure_ascii=False)};
const baseLabel = {json.dumps(base_label, ensure_ascii=False)};
"""
    with open(f"{SITE_DIR}/data.js", "w", encoding="utf-8") as f:
        f.write(js_content)

    print(f"✅ 网站文件已生成到 {SITE_DIR}/")

"""
生成静态网站文件（M4：同步部署推送图）
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
    """生成网站文件，M4：同时复制推送图"""
    os.makedirs(SITE_DIR, exist_ok=True)

    # ─── M4：复制推送图到网站目录 ────────────────────
    if os.path.exists(chart_path):
        shutil.copy(chart_path, f"{SITE_DIR}/chart.png")
        logger.info("推送图已复制到网站目录")

    # 读取数据（后续代码同之前，略...）
    # 此处为完整实现，因长度限制省略重复代码
    # 实际使用请参考第一批次的 generate_site.py
// 🆕 持仓数据（从加密文件解密后传入）
const portfolioData = {{ portfolio_data_json }};

// 🆕 资金管理数据
const fundData = {{ fund_data_json }};

// 🆕 多指数数据
const multiIndexData = {{ multi_index_json }};

    # 写入 .site_generated 标记（M2）
    with open(f"{SITE_DIR}/.site_generated", "w") as f:
        f.write("generated at " + datetime.now().isoformat())
