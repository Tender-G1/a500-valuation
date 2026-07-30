"""
推送与备存模块：通过PushPlus发送文字+图片（Base64压缩版）
"""
import os
import requests
import logging
from datetime import datetime
import base64

logger = logging.getLogger(__name__)

def push_to_wechat(content: str, image_path: str = None) -> bool:
    """
    发送推送到微信（文字 + 压缩图片Base64嵌入）。
    若图片过大，自动降低质量。
    """
    token = os.environ.get("PUSH_TOKEN")
    if not token:
        logger.error("未设置PUSH_TOKEN环境变量")
        return False

    # 限制文字长度（防止超限）
    if len(content) > 500:
        content = content[:500] + "...（详见备份）"

    # 处理图片
    img_base64 = None
    if image_path and os.path.exists(image_path):
        try:
            from PIL import Image
            import io
            # 打开并压缩图片
            img = Image.open(image_path)
            # 缩放到合适尺寸（宽度800px，保持比例）
            img.thumbnail((800, 600), Image.Resampling.LANCZOS)
            # 保存为JPEG（更小）
            buffer = io.BytesIO()
            img.convert("RGB").save(buffer, format="JPEG", quality=60, optimize=True)
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            logger.info(f"图片压缩完成，大小: {len(img_base64)} 字符")
        except ImportError:
            logger.warning("PIL未安装，尝试直接读取原图")
            try:
                with open(image_path, "rb") as f:
                    img_base64 = base64.b64encode(f.read()).decode()
            except Exception as e:
                logger.warning(f"图片读取失败: {e}")
        except Exception as e:
            logger.warning(f"图片压缩失败: {e}")

    # 组装消息
    payload = {
        "token": token,
        "title": f"📊 中证A500 估值日报 ({datetime.now().strftime('%Y-%m-%d')})",
        "content": content,
        "channel": "wechat",
    }

    # 若图片Base64存在，嵌入content（使用Markdown图片语法）
    if img_base64:
        # 但PushPlus可能不支持Markdown图片，改用HTML img标签（部分支持）
        # 更稳妥：单独作为附件字段（如果API支持）
        # 尝试使用 file 字段（multipart）
        try:
            files = {
                "file": ("chart.jpg", base64.b64decode(img_base64), "image/jpeg")
            }
            # 使用multipart发送
            response = requests.post(
                "https://www.pushplus.plus/api/send",
                data={"token": token, "title": payload["title"], "content": content, "channel": "wechat"},
                files=files,
                timeout=30
            )
            if response.status_code == 200 and response.json().get("code") == 200:
                logger.info("推送成功（含图片附件）")
                return True
            else:
                logger.warning(f"图片附件上传失败，回退纯文本: {response.text}")
        except Exception as e:
            logger.warning(f"图片上传异常: {e}，回退纯文本")

        # 若以上失败，尝试将图片Base64嵌入content（但可能过大）
        # 若图片较小（<500KB），直接嵌入
        if len(img_base64) < 500000:
            payload["content"] += f"\n\n![chart](data:image/jpeg;base64,{img_base64})"
        else:
            logger.warning("图片过大，仅发送文字")

    # 纯文本/降级发送
    try:
        response = requests.post("https://www.pushplus.plus/api/send", json=payload, timeout=10)
        if response.status_code == 200 and response.json().get("code") == 200:
            logger.info("推送成功（纯文本）")
            return True
        else:
            logger.error(f"推送失败: {response.text}")
            return False
    except Exception as e:
        logger.error(f"推送异常: {e}")
        return False


def backup_artifacts(image_path: str, content: str):
    """备份文件到 backup/ 目录"""
    import os
    os.makedirs("backup", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(f"backup/conclusion_{timestamp}.txt", "w", encoding="utf-8") as f:
        f.write(content)
    if os.path.exists(image_path):
        import shutil
        shutil.copy(image_path, f"backup/chart_{timestamp}.png")
    logger.info("备份文件已保存至 backup/")
