"""
推送与备存模块：通过PushPlus文件上传接口发送图片，避免内容过大。
"""
import os
import requests
import logging
from datetime import datetime
import base64

logger = logging.getLogger(__name__)

def push_to_wechat(content: str, image_path: str = None) -> bool:
    """
    发送推送到微信（通过PushPlus文件上传接口）。
    若提供image_path，作为附件上传。
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

    files = None
    if image_path and os.path.exists(image_path):
        # 使用文件上传（multipart/form-data）
        files = {
            "file": (os.path.basename(image_path), open(image_path, "rb"), "image/png")
        }
        logger.info(f"附加图片: {image_path}")

    try:
        # 如果上传文件，使用 data + files；否则使用 json
        if files:
            response = requests.post(url, data=payload, files=files, timeout=30)
        else:
            response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            resp_json = response.json()
            if resp_json.get("code") == 200:
                logger.info("推送成功")
                return True
            else:
                logger.error(f"推送返回错误: {resp_json}")
                return False
        else:
            logger.error(f"HTTP错误: {response.status_code}, {response.text}")
            return False
    except Exception as e:
        logger.error(f"推送异常: {e}")
        return False
    finally:
        if files:
            files["file"][1].close()  # 关闭文件句柄

def backup_artifacts(image_path: str, content: str):
    """
    将图表和结论保存为HTML附件，存储在 backup/ 目录下。
    """
    import os
    os.makedirs("backup", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 保存结论
    with open(f"backup/conclusion_{timestamp}.txt", "w", encoding="utf-8") as f:
        f.write(content)
    # 复制图片到备份目录
    if os.path.exists(image_path):
        import shutil
        shutil.copy(image_path, f"backup/chart_{timestamp}.png")
    logger.info("备份文件已保存至 backup/")
