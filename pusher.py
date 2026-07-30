"""
推送模块：微信推送（含拆分推送 N5）
"""
import os
import requests
import logging
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"


def upload_to_imgbb(image_path: str, api_key: str) -> Optional[str]:
    """上传图片到ImgBB"""
    if not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as f:
            files = {"image": f}
            data = {"key": api_key}
            resp = requests.post(IMGBB_UPLOAD_URL, files=files, data=data, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            if result.get("success"):
                return result["data"]["url"]
        return None
    except Exception as e:
        logger.error(f"图片上传异常: {e}")
        return None


def _send_push(title: str, content: str, image_path: str = None) -> bool:
    """底层推送函数"""
    token = os.environ.get("PUSH_TOKEN")
    if not token:
        logger.error("未设置PUSH_TOKEN")
        return False

    imgbb_key = os.environ.get("IMGBB_API_KEY")
    full_content = content

    if image_path and os.path.exists(image_path) and imgbb_key:
        img_url = upload_to_imgbb(image_path, imgbb_key)
        if img_url:
            full_content += f"\n\n![估值走势图]({img_url})"

    payload = {
        "token": token,
        "title": title,
        "content": full_content,
        "channel": "wechat",
    }

    try:
        resp = requests.post("https://www.pushplus.plus/api/send", json=payload, timeout=10)
        if resp.status_code == 200:
            resp_json = resp.json()
            if resp_json.get("code") == 200:
                return True
            elif resp_json.get("code") == 999 and "频繁" in resp_json.get("msg", ""):
                logger.warning("内容重复，忽略")
                return True
        return False
    except Exception as e:
        logger.error(f"推送异常: {e}")
        return False


# ─── N5：各类型推送 ──────────────────────────────────

def push_valuation_report(pe_pct: float, pb_pct: float, erp_pct: float,
                          delta: float, base_label: str, conclusion: str) -> bool:
    """N5：估值速报（08:30）"""
    title = f"📊 估值速报 ({datetime.now().strftime('%Y-%m-%d')})"
    content = f"""
【中证A500】{base_label}
┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
PE分位：{pe_pct:.1f}%
PB分位：{pb_pct:.1f}%
ERP分位：{erp_pct:.1f}%

{conclusion}
较昨日：{delta:+.1f} 个百分点
"""
    return _send_push(title, content.strip())


def push_portfolio_report(summary: Dict) -> bool:
    """N5：组合日报（08:33）"""
    title = f"💰 组合日报 ({datetime.now().strftime('%Y-%m-%d')})"
    content = f"""
【持仓汇总】
总成本：¥{summary['total_cost']:,.0f}
市值：¥{summary['total_market_value']:,.0f}
收益：¥{summary['total_profit']:,.0f}
收益率：{summary['total_return']:+.2f}%

【各指数明细】
{chr(10).join([f"{h['index_name']}: 成本¥{h['cost']:,.0f} | 收益{h['return_pct']:+.2f}%" for h in summary.get('holdings', [])])}
"""
    return _send_push(title, content.strip())


def push_fund_report(fund_status: Dict) -> bool:
    """N5：资金管理（08:36）"""
    title = f"💵 资金速报 ({datetime.now().strftime('%Y-%m-%d')})"
    content = f"""
【等待买入资金】
总资金：¥{fund_status['total']:,.0f}
日收益估算：¥{fund_status['daily_income']:.2f}

【各层级】
{chr(10).join([f"{t['name']}: ¥{t['amount']:,.0f} ({t['ratio']:.0f}%) | 日收益{t['daily_income']:.2f} | {t['availability']}" for t in fund_status.get('tiers', [])])}
"""
    return _send_push(title, content.strip())


def push_alert(alert_type: str, content: str) -> bool:
    """N5：警报推送（触发时）"""
    title = f"🚨 {alert_type} ({datetime.now().strftime('%Y-%m-%d')})"
    return _send_push(title, content)


def push_weekly_report(week_summary: Dict) -> bool:
    """N5：周报（周五 08:40）"""
    title = f"📋 周报 ({datetime.now().strftime('%Y-%m-%d')})"
    content = f"""
【本周回顾】
初始PE分位：{week_summary.get('start_pe_pct', 0):.1f}%
最新PE分位：{week_summary.get('end_pe_pct', 0):.1f}%
变化：{week_summary.get('delta', 0):+.1f} 个百分点

【操作回顾】
{week_summary.get('actions', '本周无操作')}

【下周展望】
{week_summary.get('outlook', '根据周末估值调整策略')}
"""
    return _send_push(title, content.strip())


def backup_artifacts(image_path: str, content: str):
    """备份文件"""
    import os, shutil
    os.makedirs("backup", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"backup/conclusion_{timestamp}.txt", "w", encoding="utf-8") as f:
        f.write(content)
    if os.path.exists(image_path):
        shutil.copy(image_path, f"backup/chart_{timestamp}.png")
    logger.info("备份文件已保存至 backup/")
