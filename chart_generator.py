"""
图表生成：三合一子图（PE、PB、ERP分位走势），含阈值线、信息栏。
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
                      base_label: str, config: dict) -> str:
    """
    绘制三子图，保存为 chart.png。
    """
    fig, axes = plt.subplots(3, 1, figsize=(12, 14), sharex=True)
    fig.patch.set_facecolor('#1e1e2f')

    dates = base_df["date"]
    pe_vals = base_df["pe_ttm"]
    pb_vals = base_df["pb"].fillna(0)  # 将 NaN 填充为 0 用于绘图，但实际可能缺失
    erp_vals = [(1/p)*100 - b for p, b in zip(base_df["pe_ttm"], base_df["bond_yield_10y"])]

    # 阈值线计算（基于主基准）
    pe_sorted = sorted(pe_vals.dropna())
    pb_sorted = sorted(pb_vals.dropna())
    pe_20 = pe_sorted[int(0.2 * len(pe_sorted))] if len(pe_sorted) > 0 else None
    pe_80 = pe_sorted[int(0.8 * len(pe_sorted))] if len(pe_sorted) > 0 else None
    pb_20 = pb_sorted[int(0.2 * len(pb_sorted))] if len(pb_sorted) > 0 else None
    pb_80 = pb_sorted[int(0.8 * len(pb_sorted))] if len(pb_sorted) > 0 else None

    # 子图1: PE
    ax1 = axes[0]
    ax1.plot(dates, pe_vals, color='#60a5fa', linewidth=1.5, label='PE')
    if pe_20:
        ax1.axhline(y=pe_20, color='#22c55e', linestyle='--', linewidth=1, label=f'20%分位 ({pe_20:.2f})')
    if pe_80:
        ax1.axhline(y=pe_80, color='#ef4444', linestyle='--', linewidth=1, label=f'80%分位 ({pe_80:.2f})')
    ax1.scatter(today["date"], today["pe_ttm"], color='red', marker='*', s=200, zorder=5, label=f'今日 {today["pe_ttm"]:.2f}')
    ax1.set_ylabel('PE (TTM)', color='white')
    ax1.tick_params(colors='white')
    ax1.legend(loc='upper left', facecolor='#2d2d44', edgecolor='none', labelcolor='white')
    ax1.set_title(f'PE走势（基准：{base_label}）', color='white')

    # 子图2: PB（防御 None）
    ax2 = axes[1]
    pb_today = today["pb"]
    if pd.notna(pb_today) and pb_today is not None and pb_today > 0:
        ax2.plot(dates, pb_vals, color='#fbbf24', linewidth=1.5, label='PB')
        if pb_20:
            ax2.axhline(y=pb_20, color='#22c55e', linestyle='--', linewidth=1, label=f'20%分位 ({pb_20:.2f})')
        if pb_80:
            ax2.axhline(y=pb_80, color='#ef4444', linestyle='--', linewidth=1, label=f'80%分位 ({pb_80:.2f})')
        ax2.scatter(today["date"], pb_today, color='red', marker='*', s=200, zorder=5, label=f'今日 {pb_today:.2f}')
        ax2.set_ylabel('PB', color='white')
        ax2.legend(loc='upper left', facecolor='#2d2d44', edgecolor='none', labelcolor='white')
    else:
        ax2.text(0.5, 0.5, 'PB数据暂缺', transform=ax2.transAxes, ha='center', va='center', color='white', fontsize=14)
        ax2.set_ylabel('PB', color='white')
    ax2.tick_params(colors='white')
    ax2.set_title(f'PB走势（基准：{base_label}）', color='white')

    # 子图3: ERP分位
    erp_pct_series = [calc_percentile(v, erp_vals) for v in erp_vals]
    ax3 = axes[2]
    ax3.plot(dates, erp_pct_series, color='#a78bfa', linewidth=1.5, label='ERP分位')
    ax3.axhline(y=20, color='#22c55e', linestyle='--', linewidth=1, label='20%')
    ax3.axhline(y=80, color='#ef4444', linestyle='--', linewidth=1, label='80%')
    ax3.scatter(today["date"], erp_pct, color='red', marker='*', s=200, zorder=5, label=f'今日 {erp_pct:.1f}%')
    ax3.set_ylabel('ERP历史分位 (%)', color='white')
    ax3.tick_params(colors='white')
    ax3.legend(loc='upper left', facecolor='#2d2d44', edgecolor='none', labelcolor='white')
    ax3.set_title('ERP分位走势', color='white')
    ax3.set_ylim(0, 100)

    # x轴格式
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, color='white')

    # ─── 信息栏（包含自基日分位） ───────────────────
    info_text = (
        f"📊 中证A500 估值全景 ({today['date'].strftime('%Y-%m-%d')})\n"
        f"────────────────────────────────────────\n"
        f"【主基准 {base_label}】PE {pe_pct:.1f}%  |  PB {pb_pct:.1f}%  |  ERP {erp_pct:.1f}%\n"
        f"【自基日参考】PE {full_pe_pct:.1f}%  |  PB {full_pb_pct:.1f}%  |  ERP {full_erp_pct:.1f}%"
    )
    plt.figtext(0.02, 0.02, info_text, fontsize=10, color='white',
                bbox=dict(facecolor='#2d2d44', alpha=0.8, edgecolor='none'))

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.12)
    plt.savefig('chart.png', dpi=100, bbox_inches='tight', facecolor='#1e1e2f')
    plt.close()
    return 'chart.png'

def calc_percentile(current, series):
    arr = [x for x in series if x is not None and not np.isnan(x)]
    if not arr:
        return 50.0
    return round(sum(1 for x in arr if x < current) / len(arr) * 100, 1)
