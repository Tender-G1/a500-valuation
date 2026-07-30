"""
生成静态网站文件：包含交互式图表、数据、指标卡片。
"""
import json
import pandas as pd
import os
from datetime import datetime
from pathlib import Path

# ─── 配置 ──────────────────────────────────────────────
CSV_PATH = "history_data.csv"
SITE_DIR = "site"
TEMPLATE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>中证A500 估值监控</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 中证A500 估值监控看板</h1>
            <p class="subtitle">数据更新于: {{ update_time }}</p>
            <div class="badges">
                <span class="badge">基准: {{ base_label }}</span>
                <span class="badge">数据点: {{ data_points }} 条</span>
            </div>
        </header>

        <!-- 指标卡片 -->
        <section class="cards">
            <div class="card pe">
                <div class="card-label">PE 分位</div>
                <div class="card-value" style="color: {{ pe_color }}">{{ pe_pct }}%</div>
                <div class="card-change">{{ pe_delta }}%</div>
                <div class="card-sub">自基日: {{ full_pe_pct }}%</div>
            </div>
            <div class="card pb">
                <div class="card-label">PB 分位</div>
                <div class="card-value" style="color: {{ pb_color }}">{{ pb_pct }}%</div>
                <div class="card-sub">自基日: {{ full_pb_pct }}%</div>
            </div>
            <div class="card erp">
                <div class="card-label">ERP 分位</div>
                <div class="card-value" style="color: {{ erp_color }}">{{ erp_pct }}%</div>
                <div class="card-sub">性价比: {{ erp_label }}</div>
            </div>
            <div class="card status">
                <div class="card-label">综合状态</div>
                <div class="card-value" style="font-size:1.2em;color:{{ status_color }}">{{ status_text }}</div>
                <div class="card-sub">{{ status_sub }}</div>
            </div>
        </section>

        <!-- 图表 -->
        <section class="chart-container">
            <div class="chart-toolbar">
                <button class="btn active" data-window="1y">近1年</button>
                <button class="btn" data-window="3y">近3年</button>
                <button class="btn" data-window="5y">近5年</button>
                <button class="btn" data-window="all">全部</button>
            </div>
            <canvas id="valuationChart" height="400"></canvas>
        </section>

        <!-- 结论 -->
        <section class="conclusion">
            <h3>📝 今日结论</h3>
            <div class="conclusion-text">{{ conclusion }}</div>
        </section>

        <!-- 数据表格 -->
        <section class="table-container">
            <h3>📋 历史数据（最近30天）</h3>
            <div style="overflow-x:auto">
                <table>
                    <thead>
                        <tr><th>日期</th><th>PE</th><th>PB</th><th>PE分位%</th><th>ERP分位%</th></tr>
                    </thead>
                    <tbody id="historyTable">
                    </tbody>
                </table>
            </div>
        </section>

        <footer>
            <p>数据来源：中证指数官网 · 系统自动更新于每个工作日 08:30</p>
        </footer>
    </div>

    <script src="data.js"></script>
    <script src="script.js"></script>
</body>
</html>
"""

def generate():
    """生成网站文件"""
    os.makedirs(SITE_DIR, exist_ok=True)
    
    # 读取CSV
    df = pd.read_csv(CSV_PATH, parse_dates=["date"])
    today = df.iloc[-1]
    
    # 计算近10年基准
    from datetime import timedelta
    cutoff = today["date"] - timedelta(days=3650)
    df_10y = df[df["date"] >= cutoff]
    use_rolling = len(df_10y) >= 252  # 1年最少数据点
    base_df = df_10y if use_rolling else df
    base_label = "近10年" if use_rolling else "自基日"
    
    # 分位计算
    from calculator import calc_percentile, calc_erp
    pe_pct = calc_percentile(today["pe_ttm"], base_df["pe_ttm"].tolist())
    pb_pct = calc_percentile(today["pb"], base_df["pb"].dropna().tolist()) if today["pb"] else 50.0
    erp = calc_erp(today["pe_ttm"], today["bond_yield_10y"])
    erp_series = [calc_erp(p, b) for p, b in zip(base_df["pe_ttm"], base_df["bond_yield_10y"])]
    erp_pct = calc_percentile(erp, erp_series)
    
    # 自基日分位
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
    
    # 颜色判断
    def color_from_pct(pct):
        if pct < 30: return "#22c55e"
        if pct < 70: return "#f59e0b"
        return "#ef4444"
    
    # 状态文字
    status_text = "🟢 低估" if pe_pct < 30 else ("🟡 适中" if pe_pct < 70 else "🔴 高估")
    status_sub = f"较昨日 {delta:+.1f} 个百分点"
    
    erp_label = "高性价比" if erp_pct > 70 else ("适中" if erp_pct > 30 else "偏低")
    
    # 生成结论（简化版，可复用conclusion_builder）
    if pe_pct >= 80:
        conclusion = "⚠️ 估值处于历史高位，需注意风险。"
    elif pe_pct >= 60:
        conclusion = "估值处于历史中高水平，建议保持谨慎。"
    elif pe_pct >= 40:
        conclusion = "估值处于历史中枢，可维持现有仓位。"
    elif pe_pct >= 20:
        conclusion = "估值偏低，可适度关注。"
    else:
        conclusion = "✅ 历史极低位，可分批布局。"
    conclusion += f" PE分位{pe_pct:.1f}%，较昨日{delta:+.1f}个百分点。"
    
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 生成 HTML
    from jinja2 import Template
    html = Template(TEMPLATE_HTML).render(
        update_time=update_time,
        base_label=base_label,
        data_points=len(df),
        pe_pct=pe_pct,
        pb_pct=pb_pct,
        erp_pct=erp_pct,
        full_pe_pct=full_pe_pct,
        full_pb_pct=full_pb_pct,
        full_erp_pct=full_erp_pct,
        pe_delta=delta,
        pe_color=color_from_pct(pe_pct),
        pb_color=color_from_pct(pb_pct),
        erp_color=color_from_pct(erp_pct),
        status_color=color_from_pct(pe_pct),
        status_text=status_text,
        status_sub=status_sub,
        erp_label=erp_label,
        conclusion=conclusion,
    )
    
    with open(f"{SITE_DIR}/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    # 生成数据文件 (data.js)
    # 准备图表数据（全部历史）
    chart_data = {
        "dates": [d.strftime("%Y-%m-%d") for d in df["date"]],
        "pe": [float(x) for x in df["pe_ttm"]],
        "pb": [float(x) if pd.notna(x) else None for x in df["pb"]],
        "pe_pct": [],
        "erp_pct": []
    }
    # 计算每个日期的分位值（用滚动窗口）
    for i in range(len(df)):
        window = df.iloc[:i+1]
        pe_series = window["pe_ttm"].tolist()
        chart_data["pe_pct"].append(calc_percentile(window["pe_ttm"].iloc[-1], pe_series))
        erp_series = [calc_erp(p, b) for p, b in zip(window["pe_ttm"], window["bond_yield_10y"])]
        if len(erp_series) > 0:
            chart_data["erp_pct"].append(calc_percentile(erp_series[-1], erp_series))
        else:
            chart_data["erp_pct"].append(50.0)
    
    # 阈值线
    pe_sorted = sorted(df["pe_ttm"].dropna())
    chart_data["pe_20"] = pe_sorted[int(0.2 * len(pe_sorted))] if len(pe_sorted) > 0 else None
    chart_data["pe_80"] = pe_sorted[int(0.8 * len(pe_sorted))] if len(pe_sorted) > 0 else None
    chart_data["pb_sorted"] = sorted(df["pb"].dropna()) if len(df["pb"].dropna()) > 0 else []
    chart_data["pb_20"] = chart_data["pb_sorted"][int(0.2 * len(chart_data["pb_sorted"]))] if len(chart_data["pb_sorted"]) > 0 else None
    chart_data["pb_80"] = chart_data["pb_sorted"][int(0.8 * len(chart_data["pb_sorted"]))] if len(chart_data["pb_sorted"]) > 0 else None
    
    js_content = f"// 自动生成，请勿手动编辑\nconst chartData = {json.dumps(chart_data, ensure_ascii=False)};\nconst latest = {json.dumps({'date': today['date'].strftime('%Y-%m-%d'), 'pe': float(today['pe_ttm']), 'pb': float(today['pb']) if pd.notna(today['pb']) else None}, ensure_ascii=False)};"
    
    with open(f"{SITE_DIR}/data.js", "w", encoding="utf-8") as f:
        f.write(js_content)
    
    print(f"✅ 网站文件已生成到 {SITE_DIR}/")
