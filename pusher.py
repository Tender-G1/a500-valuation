"""
推送与备存模块：通过PushPlus发送微信消息，失败时生成HTML备份。
"""
import os
import requests
import logging
from datetime import datetime
import base64

logger = logging.getLogger(__name__)

def push_to_wechat(content: str, image_path: str = None) -> bool:
    """
    发送推送到微信（通过PushPlus）。
    若image_path提供，尝试作为图片发送。
    返回成功与否。
    """
    token = os.environ.get("PUSH_TOKEN")
    if not token:
        logger.error("未设置PUSH_TOKEN环境变量")
        return False
    url = "https://www.pushplus.plus/api/send"
    payload = {
        "token": token,
        "title": f"📊 中证A500 估值日报 ({datetime.now().strftime('%Y-%m-%d')})",
        "content": content,
        "channel": "wechat",
    }
    if image_path:
        # 读取图片转为base64
        try:
            with open(image_path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode()
            payload["content"] += f"\n\n![chart](data:image/png;base64,{img_base64})"
        except Exception as e:
            logger.warning(f"图片编码失败: {e}")
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200 and resp.json().get("code") == 200:
            logger.info("推送成功")
            return True
        else:
            logger.error(f"推送失败: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"推送异常: {e}")
        return False

def backup_artifacts(image_path: str, content: str):
    """
    将图表和结论保存为HTML附件，存储在 backup/ 目录下，供GitHub Actions上传。
    """
    import os
    os.makedirs("backup", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 保存结论
    with open(f"backup/conclusion_{timestamp}.txt", "w") as f:
        f.write(content)
    # 生成简单HTML
    html = f"""
    <html>
    <head><meta charset="UTF-8"><title>估值备份 {timestamp}</title></head>
    <body>
    <h2>中证A500估值日报备份</h2>
    <pre>{content}</pre>
    <img src="data:image/png;base64,{base64.b64encode(open(image_path,'rb').read()).decode()}" />
    </body>
    </html>
    """
    with open(f"backup/chart_{timestamp}.html", "w") as f:
        f.write(html)
    logger.info("备份文件已保存至 backup/")