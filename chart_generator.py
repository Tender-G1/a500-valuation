"""
图表生成：三合一/二合一子图（根据数据可用性自适应），含阈值线、信息栏、文字结论。
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib as mpl
import pandas as pd
import numpy as np

# ─── 中文字体设置 ──────────────────────────────────────
try:
    mpl.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'DejaVu Sans']
except:
    mpl.rcParams['font.sans-serif'] = ['DejaVu Sans']
mpl.rcParams['axes.unicode_minus'] = False

def draw_triple_chart(base_df: pd.DataFrame, today: pd.Series,
                      pe_pct: float, pb_pct: float, erp_pct: float,
                      full_pe_pct: float, full_pb_pct: float, full_erp_pct: float,
                      base_label: str, config: dict, conclusion_text: str = "") -> str:
    """
    绘制自适应图表（PE必有，PB/ERP按数据可用性显示），
    并将文字结论嵌入图表底部。
    """
    # ─── 检测数据有效性 ──────────────────────────────
    has_pe = True  # PE总是有
    has_pb = today["pb"] is not None and pd.notna(today["pb"]) and today["pb"] > 0
    has_erp = erp_pct is not None and not np.isnan(erp_pct)

    # ─── 确定子图数量 ──────────────────────────────
    subplot_count = 1  # 至少PE
    if has_pb:
        subplot_count += 1
    if has_erp:
        subplot_count += 1

    fig, axes = plt.subplots(subplot_count, 1, figsize=(12, 6 * subplot_count + 2), sharex=True)
    fig.patch.set_facecolor('#1e1e2f')

    # 如果只有一个子图，axes不是列表，统一处理
    if subplot_count == 1:
        axes = [axes]
    ax_idx = 0

    # ─── 数据准备 ──────────────────────────────────
    dates = base_df["date"]
    pe_vals = base_df["pe_ttm"]
    erp_vals = [(1/p)*100 - b for p, b in zip(base_df["pe_ttm"], base_df["bond_yield_10y"])]

    # 阈值线计算
    pe_sorted = sorted(pe_vals.dropna())
    pe_20 = pe_sorted[int(0.2 * len(pe_sorted))] if len(pe_sorted) > 0 else None
    pe_80 = pe_sorted[int(0.8 * len(pe_sorted))] if len(pe_sorted) > 0 else None

    # ─── 子图1: PE（必有） ──────────────────────────
    ax = axes[ax_idx]
    ax.plot(dates, pe_vals, color='#60a5fa', linewidth=1.5, label='PE')
    if pe_20:
        ax.axhline(y=pe_20, color='#22c55e', linestyle='--', linewidth=1, label=f'20%分位 ({pe_20:.2f})')
    if pe_80:
        ax.axhline(y=pe_80, color='#ef4444', linestyle='--', linewidth=1, label=f'80%分位 ({pe_80:.2f})')
    ax.scatter(today["date"], today["pe_ttm"], color='red', marker='*', s=200, zorder=5, label=f'今日 {today["pe_ttm"]:.2f}')
    ax.set_ylabel('PE (TTM)', color='white')
    ax.tick_params(colors='white')
    ax.legend(loc='upper left', facecolor='#2d2d44', edgecolor='none', labelcolor='white')
    ax.set_title(f'PE走势（基准：{base_label}）', color='white')
    ax.grid(alpha=0.2, color='gray')
    ax_idx += 1

    # ─── 子图2: PB（仅当有数据） ────────────────────
    if has_pb:
        ax = axes[ax_idx]
        pb_vals = base_df["pb"].dropna()
        if len(pb_vals) > 0:
            pb_sorted = sorted(pb_vals)
            pb_20 = pb_sorted[int(0.2 * len(pb_sorted))] if len(pb_sorted) > 0 else None
            pb_80 = pb_sorted[int(0.8 * len(pb_sorted))] if len(pb_sorted) > 0 else None
            ax.plot(dates, pb_vals, color='#fbbf24', linewidth=1.5, label='PB')
            if pb_20:
                ax.axhline(y=pb_20, color='#22c55e', linestyle='--', linewidth=1, label=f'20%分位 ({pb_20:.2f})')
            if pb_80:
                ax.axhline(y=pb_80, color='#ef4444', linestyle='--', linewidth=1, label=f'80%分位 ({pb_80:.2f})')
            ax.scatter(today["date"], today["pb"], color='red', marker='*', s=200, zorder=5, label=f'今日 {today["pb"]:.2f}')
        else:
            ax.text(0.5, 0.5, 'PB历史数据暂缺', transform=ax.transAxes, ha='center', va='center', color='white', fontsize=14)
        ax.set_ylabel('PB', color='white')
        ax.tick_params(colors='white')
        ax.legend(loc='upper left', facecolor='#2d2d44', edgecolor='none', labelcolor='white')
        ax.set_title(f'PB走势（基准：{base_label}）', color='white')
        ax.grid(alpha=0.2, color='gray')
        ax_idx += 1

    # ─── 子图3: ERP分位（仅当有数据） ──────────────
    if has_erp:
        ax = axes[ax_idx]
        erp_pct_series = [calc_percentile(v, erp_vals) for v in erp_vals]
        ax.plot(dates, erp_pct_series, color='#a78bfa', linewidth=1.5, label='ERP分位')
        ax.axhline(y=20, color='#22c55e', linestyle='--', linewidth=1, label='20%')
        ax.axhline(y=80, color='#ef4444', linestyle='--', linewidth=1, label='80%')
        ax.scatter(today["date"], erp_pct, color='red', marker='*', s=200, zorder=5, label=f'今日 {erp_pct:.1f}%')
        ax.set_ylabel('ERP历史分位 (%)', color='white')
        ax.tick_params(colors='white')
        ax.legend(loc='upper left', facecolor='#2d2d44', edgecolor='none', labelcolor='white')
        ax.set_title('ERP分位走势', color='white')
        ax.set_ylim(0, 100)
        ax.grid(alpha=0.2, color='gray')

    # ─── x轴统一格式 ──────────────────────────────────
    for ax in axes:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.setp(axes[-1].xaxis.get_majorticklabels(), rotation=45, color='white')

    # ─── 信息栏（分位数据） ──────────────────────────
    info_text = (
        f"📊 中证A500 估值全景 ({today['date'].strftime('%Y-%m-%d')})\n"
        f"────────────────────────────────────────\n"
        f"【主基准 {base_label}】PE {pe_pct:.1f}%  |  PB {pb_pct:.1f}%  |  ERP {erp_pct:.1f}%\n"
        f"【自基日参考】PE {full_pe_pct:.1f}%  |  PB {full_pb_pct:.1f}%  |  ERP {full_erp_pct:.1f}%"
    )
    plt.figtext(0.02, 0.01, info_text, fontsize=9, color='white',
                bbox=dict(facecolor='#2d2d44', alpha=0.8, edgecolor='none'))

    # ─── 文字结论嵌入图表（底部区域） ──────────────
    if conclusion_text:
        # 将结论分行显示，每行不超过60字符
        lines = conclusion_text.split('\n')
        formatted_lines = []
        for line in lines:
            if len(line) > 60:
                # 简单折行
                for i in range(0, len(line), 60):
                    formatted_lines.append(line[i:i+60])
            else:
                formatted_lines.append(line)
        conclusion_display = '\n'.join(formatted_lines[:8])  # 最多显示8行
        plt.figtext(0.02, 0.07, f"【每日结论】\n{conclusion_display}", 
                    fontsize=8, color='#e0e0e0',
                    bbox=dict(facecolor='#1a1a2e', alpha=0.9, edgecolor='#444466', pad=8))

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.18)
    plt.savefig('chart.png', dpi=100, bbox_inches='tight', facecolor='#1e1e2f')
    plt.close()
    return 'chart.png'

def calc_percentile(current, series):
    arr = [x for x in series if x is not None and not np.isnan(x)]
    if not arr:
        return 50.0
    return round(sum(1 for x in arr if x < current) / len(arr) * 100, 1)
