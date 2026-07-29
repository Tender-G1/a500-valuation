"""
结论生成：基于规则引擎生成文字日报，包含趋势描述和辅助提示。
"""
from typing import Optional, Tuple

def build_conclusion(pe_pct: float, erp_pct: float, 
                     delta: Optional[float],  # 较昨日分位变化（百分点），None表示不显示
                     buy_alert: bool, sell_alert: bool,
                     momentum_hint: Optional[str],
                     base_label: str, data_fetched: bool) -> str:
    """
    构建日报正文。
    """
    # 基础结论（基于PE分位）
    if pe_pct >= 80:
        if erp_pct < 30:
            main_text = "⚠️ 估值极度高企，股债性价比极低，风险较大，建议谨慎。"
        else:
            main_text = "估值处于历史高位，但利率环境尚可，性价比一般，注意止盈。"
    elif pe_pct >= 60:
        if erp_pct > 70:
            main_text = "估值中等偏高，但利率下行使得股票相对债券仍有吸引力，中性偏乐观。"
        else:
            main_text = "估值处于历史中高水平，但远未泡沫化，且考虑利率后的性价比仍属合理。"
    elif pe_pct >= 40:
        main_text = "估值处于历史中枢，股债性价比均衡，建议维持现有仓位。"
    elif pe_pct >= 20:
        if erp_pct > 80:
            main_text = "估值偏低且性价比凸显，黄金坑概率较大，建议分批布局。"
        else:
            main_text = "估值处于历史偏低位置，向下空间有限，可适度关注。"
    else:
        main_text = "⚠️ 历史极低位，恐慌中孕育机会，请考虑分批买入。"
    
    # 添加趋势描述
    if delta is not None:
        direction = "上升" if delta > 0 else "下降"
        trend_text = f"较昨日分位变化：{delta:+.1f} 个百分点（{direction}）。"
    else:
        trend_text = "⚠️ 今日数据基于本地缓存，未联网更新，无法提供分位变化。"
    
    # 警报附加
    alert_text = ""
    if buy_alert:
        alert_text = "🚨 触发买入警报：PE或PB处于极端低位，且ERP性价比极高，建议关注。"
    if sell_alert:
        alert_text = "🚨 触发卖出警报：PE或PB处于极端高位，且ERP性价比极低，注意风险。"
    
    # 动量辅助提示（若触发买入且存在急跌）
    momentum_text = momentum_hint if momentum_hint else ""
    
    # 组装
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