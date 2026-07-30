"""
推送模块：通过PushPlus发送微信消息，图片上传至ImgBB图床后嵌入URL。
"""
import os
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── ImgBB 图床配置 ─────────────────────────────────
IMGBB_UPLOAD_URL = "https://api.imgbb.com/1/upload"


def upload_to_imgbb(image_path: str, api_key: str) -> str | None:
    """
    上传图片到 ImgBB，返回图片 URL，失败返回 None。
    """
    if not os.path.exists(image_path):
        logger.error(f"图片文件不存在: {image_path}")
        return None
    try:
        with open(image_path, "rb") as f:
            files = {"image": f}
            data = {"key": api_key}
            resp = requests.post(IMGBB_UPLOAD_URL, files=files, data=data, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            if result.get("success"):
                url = result["data"]["url"]
                logger.info(f"图片上传成功: {url}")
                return url
            else:
                logger.error(f"ImgBB上传失败: {result}")
                return None
    except Exception as e:
        logger.error(f"图片上传异常: {e}")
        return None


def push_to_wechat(content: str, image_path: str = None) -> bool:
    """
    推送文字 + 图片（若上传成功则插入Markdown图片）。
    """
    token = os.environ.get("PUSH_TOKEN")
    if not token:
        logger.error("未设置PUSH_TOKEN环境变量")
        return False

    imgbb_key = os.environ.get("IMGBB_API_KEY")
    if not imgbb_key:
        logger.warning("未设置IMGBB_API_KEY，将无法上传图片")

    full_content = content

    # 尝试上传图片
    img_url = None
    if image_path and os.path.exists(image_path) and imgbb_key:
        img_url = upload_to_imgbb(image_path, imgbb_key)
        if img_url:
            full_content += f"\n\n![估值走势图]({img_url})"
        else:
            logger.warning("图片上传失败，仅推送文字")
    else:
        if not imgbb_key:
            logger.warning("缺少ImgBB API Key，跳过图片上传")

    # 构建推送请求
    payload = {
        "token": token,
        "title": f"📊 中证A500 估值日报 ({datetime.now().strftime('%Y-%m-%d')})",
        "content": full_content,
        "channel": "wechat",
    }

    try:
        resp = requests.post("https://www.pushplus.plus/api/send", json=payload, timeout=10)
        if resp.status_code == 200:
            resp_json = resp.json()
            if resp_json.get("code") == 200:
                logger.info("推送成功")
                return True
            else:
                # 防重复机制（code=999）
                if resp_json.get("code") == 999 and "频繁" in resp_json.get("msg", ""):
                    logger.warning("内容重复，可能已推送成功，忽略此错误")
                    return True
                logger.error(f"推送失败: {resp_json}")
                return False
        else:
            logger.error(f"HTTP错误: {resp.status_code}, {resp.text}")
            return False
    except Exception as e:
        logger.error(f"推送异常: {e}")
        return False


def backup_artifacts(image_path: str, content: str):
    """备份文件到 backup/ 目录"""
    import os, shutil
    os.makedirs("backup", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"backup/conclusion_{timestamp}.txt", "w", encoding="utf-8") as f:
        f.write(content)
    if os.path.exists(image_path):
        shutil.copy(image_path, f"backup/chart_{timestamp}.png")
    logger.info("备份文件已保存至 backup/")
