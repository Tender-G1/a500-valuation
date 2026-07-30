"""
图表生成：三合一子图（PE、PB、ERP分位走势），含阈值线、信息栏。
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib as mpl

# ─── 设置中文字体（支持GitHub Actions环境） ─────
try:
    # 尝试使用文泉驿字体（已安装）
    mpl.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'DejaVu Sans']
except:
    # 若不存在则回退
    mpl.rcParams['font.sans-serif'] = ['DejaVu Sans']
mpl.rcParams['axes.unicode_minus'] = False   # 正确显示负号

def draw_triple_chart(base_df: pd.DataFrame, today: pd.Series, 
                      pe_pct: float, pb_pct: float, erp_pct: float,
                      base_label: str, config: dict) -> str:
    """
    绘制三子图，保存为 chart.png，返回文件路径。
    base_df 为用于计算分位的基准数据集（近10年或全量）。
    today 为当日数据（含pe_ttm, pb, date）。
    base_label 为 "近10年" 或 "自基日"。
    """
    fig, axes = plt.subplots(3, 1, figsize=(12, 14), sharex=True)
    fig.patch.set_facecolor('#1e1e2f')
    
    # 提取数据
    dates = base_df["date"]
    pe_vals = base_df["pe_ttm"]
    pb_vals = base_df["pb"]
    # 计算ERP序列
    erp_vals = [(1/p)*100 - b for p, b in zip(base_df["pe_ttm"], base_df["bond_yield_10y"])]
    
    # 计算阈值线对应的PE/PB值（基于当前基准）
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
    # 当前日期标记
    ax1.scatter(today["date"], today["pe_ttm"], color='red', marker='*', s=200, zorder=5, label=f'今日 {today["pe_ttm"]:.2f}')
    ax1.set_ylabel('PE (TTM)', color='white')
    ax1.tick_params(colors='white')
    ax1.legend(loc='upper left', facecolor='#2d2d44', edgecolor='none', labelcolor='white')
    ax1.set_title(f'PE走势（基准：{base_label}）', color='white')
    
    # 子图2: PB
    ax2 = axes[1]
    ax2.plot(dates, pb_vals, color='#fbbf24', linewidth=1.5, label='PB')
    if pb_20:
        ax2.axhline(y=pb_20, color='#22c55e', linestyle='--', linewidth=1, label=f'20%分位 ({pb_20:.2f})')
    if pb_80:
        ax2.axhline(y=pb_80, color='#ef4444', linestyle='--', linewidth=1, label=f'80%分位 ({pb_80:.2f})')
    if today["pb"] is not None:
      ax2.scatter(today["date"], today["pb"], color='red', marker='*', s=200, zorder=5, label=f'今日 {today["pb"]:.2f}')
    else:
      ax2.scatter(today["date"], 0, color='red', marker='*', s=200, zorder=5, label='今日 PB: N/A')
    ax2.set_ylabel('PB', color='white')
    ax2.tick_params(colors='white')
    ax2.legend(loc='upper left', facecolor='#2d2d44', edgecolor='none', labelcolor='white')
    ax2.set_title(f'PB走势（基准：{base_label}）', color='white')
    
    # 子图3: ERP分位（ERP自身的历史分位，非ERP值）
    # 计算ERP的历史分位序列
    erp_pct_series = [calc_percentile(v, erp_vals) for v in erp_vals]
    ax3 = axes[2]
    ax3.plot(dates, erp_pct_series, color='#a78bfa', linewidth=1.5, label='ERP分位')
    ax3.axhline(y=20, color='#22c55e', linestyle='--', linewidth=1, label='20%')
    ax3.axhline(y=80, color='#ef4444', linestyle='--', linewidth=1, label='80%')
    # 当前ERP分位
    current_erp_pct = erp_pct
    ax3.scatter(today["date"], current_erp_pct, color='red', marker='*', s=200, zorder=5, label=f'今日 {current_erp_pct:.1f}%')
    ax3.set_ylabel('ERP历史分位 (%)', color='white')
    ax3.tick_params(colors='white')
    ax3.legend(loc='upper left', facecolor='#2d2d44', edgecolor='none', labelcolor='white')
    ax3.set_title('ERP分位走势', color='white')
    ax3.set_ylim(0, 100)
    
    # 设置x轴日期格式
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, color='white')
    
    # 添加汇总信息栏（在图表顶部或右上角）
    info_text = (
        f"📊 中证A500 估值全景 ({today['date'].strftime('%Y-%m-%d')})\n"
        f"────────────────────────────────────────\n"
        f"近10年分位： PE {pe_pct:.1f}%  |  PB {pb_pct:.1f}%  |  ERP {erp_pct:.1f}%\n"
        f"基准：{base_label}"
    )
    if config["chart"]["show_full_benchmark"] and base_label == "近10年":
        # 额外显示自基日分位（需要计算，但此处简化，由main传入）
        # 因main会传入，我们通过参数扩展，此处略。
        pass
    # 在图表左下角添加文本
    plt.figtext(0.02, 0.02, info_text, fontsize=10, color='white', 
                bbox=dict(facecolor='#2d2d44', alpha=0.8, edgecolor='none'))
    
    plt.tight_layout()
    plt.subplots_adjust(bottom=0.12)
    plt.savefig('chart.png', dpi=100, bbox_inches='tight', facecolor='#1e1e2f')
    plt.close()
    return 'chart.png'

# 辅助函数（用于计算ERP分位）
def calc_percentile(current, series):
    arr = [x for x in series if x is not None and not np.isnan(x)]
    if not arr:
        return 50.0
    return round(sum(1 for x in arr if x < current) / len(arr) * 100, 1)
