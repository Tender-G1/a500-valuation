# 在 main.py 中，生成图表前添加：
# 构建用于图表的简短结论（不含推送专用标记）
chart_conclusion = f"""📊 中证A500 估值日报（基准：{base_label}）
当前PE分位：{pe_pct:.1f}%，ERP分位：{erp_pct:.1f}%
{main_text}
较昨日分位变化：{delta:+.1f} 个百分点（{'上升' if delta > 0 else '下降'}）。"""

# 然后调用 draw_triple_chart 时传入
chart_path = draw_triple_chart(
    base_df, today,
    pe_pct, pb_pct, erp_pct,
    full_pe_pct, full_pb_pct, full_erp_pct,
    base_label, config,
    conclusion_text=chart_conclusion  # ← 新增参数
)
# ─── 生成网站 ──────────────────────────────────────
try:
    from generate_site import generate
    generate()
    logger.info("网站文件生成成功")
except Exception as e:
    logger.warning(f"网站生成失败（不影响推送）: {e}")
