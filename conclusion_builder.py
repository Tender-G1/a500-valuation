"""
结论生成：基于规则引擎生成文字日报，包含趋势描述和辅助提示。
"""
from typing import Optional

def build_conclusion(pe_pct: float, erp_pct: float,
                     delta: Optional[float],  # 较昨日分位变化（百分点），None表示无法计算
                     buy_alert: bool, sell_alert: bool,
                     momentum_hint: Optional[str],
                     base_label: str, data_fetched: bool) -> str:
    """
    构建日报正文，规则引擎覆盖所有PE分位区间，每个区间均根据ERP分位细分。
    """
    # ─── 1. PE分位 ≥ 80% ────────────────────────────────
    if pe_pct >= 80:
        if erp_pct < 20:
            main_text = "⚠️ 估值极度高企，且股债性价比极低（ERP分位<20%），风险较大，建议果断减仓。"
        elif erp_pct < 50:
            main_text = "⚠️ 估值处于历史高位，股债性价比偏低，注意止盈，谨慎追高。"
        else:
            main_text = "估值处于历史高位，但利率环境尚可，性价比一般，建议分批止盈。"

    # ─── 2. PE分位 60%~79% ──────────────────────────────
    elif pe_pct >= 60:
        if erp_pct > 70:
            main_text = "估值中等偏高，但利率下行使得股票相对债券仍有吸引力，中性偏乐观。"
        elif erp_pct >= 30:
            main_text = "估值处于历史中高水平，股债性价比一般，建议保持谨慎，控制仓位。"
        else:
            main_text = "⚠️ 估值处于历史中高水平，且股债性价比偏低（ERP分位<30%），风险需重视。"

    # ─── 3. PE分位 40%~59% ──────────────────────────────
    elif pe_pct >= 40:
        if erp_pct > 70:
            main_text = "估值处于历史中枢，且股债性价比偏高，可适度加仓。"
        elif erp_pct >= 30:
            main_text = "估值处于历史中枢，股债性价比均衡，建议维持现有仓位。"
        else:
            main_text = "估值处于历史中枢，但股债性价比偏低，建议观望等待更好时机。"

    # ─── 4. PE分位 20%~39% ──────────────────────────────
    elif pe_pct >= 20:
        if erp_pct > 80:
            main_text = "✅ 估值偏低且性价比凸显（ERP分位>80%），黄金坑概率较大，建议分批布局。"
        elif erp_pct >= 50:
            main_text = "估值处于历史偏低位置，性价比尚可，可适度关注，逐步建仓。"
        else:
            main_text = "估值处于历史偏低位置，但性价比一般，建议等待更佳时机或小量试仓。"

    # ─── 5. PE分位 < 20% ──────────────────────────────────
    else:
        if erp_pct > 80:
            main_text = "🚨 历史极低位 + 超高性价比（ERP分位>80%），恐慌中孕育大机会，建议大胆分批买入。"
        elif erp_pct >= 50:
            main_text = "🚨 历史极低位，性价比良好，建议积极布局，分批建仓。"
        else:
            main_text = "⚠️ 历史极低位，但性价比一般，需警惕估值陷阱，建议小量试探。"

    # ─── 趋势描述（较昨日分位变化）───────────────────────
    if delta is not None:
        direction = "上升" if delta > 0 else "下降"
        if abs(delta) > 0.1:
            trend_text = f"较昨日分位变化：{delta:+.1f} 个百分点（{direction}）。"
        else:
            trend_text = "较昨日分位基本持平。"
    else:
        # 数据未更新或无昨日数据时
        if not data_fetched:
            trend_text = "⚠️ 今日数据基于本地缓存，未联网更新，无法提供分位变化。"
        else:
            trend_text = "⚠️ 无法计算分位变化（可能数据不足）。"

    # ─── 警报附加 ───────────────────────────────────────
    alert_text = ""
    if buy_alert:
        alert_text = "🚨 触发买入警报：PE或PB处于极端低位，且ERP性价比极高，建议关注。"
    if sell_alert:
        alert_text = "🚨 触发卖出警报：PE或PB处于极端高位，且ERP性价比极低，注意风险。"

    # ─── 动量辅助提示（若触发买入且存在急跌）─────────────
    momentum_text = momentum_hint if momentum_hint else ""

    # ─── 组装 ──────────────────────────────────────────
    parts = [
        f"📊 中证A500 估值日报（基准：{base_label}）",
        f"当前PE分位：{pe_pct:.1f}%，ERP分位：{erp_pct:.1f}%",
        main_text,
        trend_text,
        alert_text,
        momentum_text
    ]
    # 过滤空字符串
    return "\n".join([p for p in parts if p])
