"""
DashScope / 通义千问 统一调用客户端
- 超时控制 (30s)
- 自动重试 (最多2次, 指数退避)
- 全链路日志
"""
import time
import dashscope
from src.config import DASHSCOPE_API_KEY, AI_MODEL, AI_TIMEOUT, AI_MAX_RETRIES, VL_MODEL, logger
from src.exceptions import AITimeoutError, ServerError


def _do_call(messages: list[dict]) -> str:
    """单次调用 DashScope，成功返回文本，失败抛出异常"""
    t0 = time.time()
    resp = dashscope.Generation.call(
        api_key=DASHSCOPE_API_KEY,
        model=AI_MODEL,
        messages=messages,
        result_format="message",
        timeout=AI_TIMEOUT,
    )
    elapsed = int((time.time() - t0) * 1000)
    if resp.status_code == 200:
        try:
            content = resp.output.choices[0].message.content
            logger.info("AI 调用成功 model=%s elapsed=%dms", AI_MODEL, elapsed)
            return content
        except (AttributeError, IndexError, TypeError):
            raise ServerError("AI 返回格式异常，无法解析")
    # 错误分类
    code = getattr(resp, "status_code", 0)
    msg = getattr(resp, "message", "") or "未知错误"
    logger.warning("AI 调用失败 [%s] elapsed=%dms: %s", code, elapsed, msg)
    if code in (429, 503) or "Throttling" in msg or "Rate limit" in msg:
        raise AITimeoutError("AI 服务繁忙，请稍后重试")
    if code == 401 or code == 403:
        raise ServerError("AI 服务认证失败，请检查 API Key 配置")
    raise AITimeoutError(f"AI 调用失败 [{code}]: {msg}")


# ── VL OCR 模块 ──────────────────────────────────────

OCR_SYSTEM_PROMPT = (
    "你是一个专业的OCR文字识别助手。"
    "请准确识别以下简历图片中的所有文字内容，保持原有的格式和排版顺序。"
    "不要添加任何解释或额外评论，不要使用markdown格式，只输出识别到的文字。"
)


def _extract_vl_content(content) -> str:
    """从 MultiModalConversation 响应中提取纯文本。
    content 可能是 str（直接返回）或 list[dict]（遍历 text 块拼接）。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text", "")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content)


def _do_vl_call(image_paths: list[str]) -> str:
    """单次调用多模态 DashScope OCR，成功返回文本，失败抛出异常"""
    t0 = time.time()

    system_msg = {"role": "system", "content": [{"text": OCR_SYSTEM_PROMPT}]}

    user_content = []
    for i, path in enumerate(image_paths):
        user_content.append({"image": f"file://{path}"})
    user_content.append({"text": "请逐页识别以上简历图片中的所有文字内容，保持原有格式。"})
    user_msg = {"role": "user", "content": user_content}

    resp = dashscope.MultiModalConversation.call(
        api_key=DASHSCOPE_API_KEY,
        model=VL_MODEL,
        messages=[system_msg, user_msg],
        timeout=AI_TIMEOUT,
    )

    elapsed = int((time.time() - t0) * 1000)

    if resp.status_code == 200:
        try:
            content = resp.output.choices[0].message.content
            text = _extract_vl_content(content)
            logger.info("VL OCR 成功 model=%s elapsed=%dms pages=%d chars=%d",
                        VL_MODEL, elapsed, len(image_paths), len(text))
            return text
        except (AttributeError, IndexError, TypeError):
            raise ServerError("VL 模型返回格式异常，无法解析")

    code = getattr(resp, "status_code", 0)
    msg = getattr(resp, "message", "") or "未知错误"
    logger.warning("VL OCR 失败 [%s] elapsed=%dms: %s", code, elapsed, msg)
    if code in (429, 503) or "Throttling" in msg or "Rate limit" in msg:
        raise AITimeoutError("VL OCR 服务繁忙，请稍后重试")
    if code in (401, 403):
        raise ServerError("VL OCR 服务认证失败，请检查 API Key 配置")
    raise AITimeoutError(f"VL OCR 调用失败 [{code}]: {msg}")


def ocr_images(image_paths: list[str]) -> str:
    """带重试的 VL OCR 调用入口"""
    if not DASHSCOPE_API_KEY:
        raise ServerError("AI 服务未配置，请设置 DASHSCOPE_API_KEY 环境变量")
    if not image_paths:
        return ""

    last_error = None
    for attempt in range(AI_MAX_RETRIES + 1):
        try:
            return _do_vl_call(image_paths)
        except (AITimeoutError, ServerError):
            raise
        except Exception as e:
            last_error = e
            if attempt < AI_MAX_RETRIES:
                wait = 1 * (2 ** attempt)
                logger.warning("VL OCR 重试 %d/%d, 等待 %ds: %s",
                               attempt + 1, AI_MAX_RETRIES, wait, e)
                time.sleep(wait)
    logger.error("VL OCR 全部重试失败: %s", last_error)
    raise AITimeoutError("VL OCR 服务超时，已重试仍失败，请稍后重试")


def chat(messages: list[dict]) -> str:
    """带重试的 AI 调用入口"""
    if not DASHSCOPE_API_KEY:
        raise ServerError("AI 服务未配置，请设置 DASHSCOPE_API_KEY 环境变量")

    last_error = None
    for attempt in range(AI_MAX_RETRIES + 1):   # 1 次初始 + 2 次重试
        try:
            return _do_call(messages)
        except (AITimeoutError, ServerError):
            raise
        except Exception as e:
            last_error = e
            if attempt < AI_MAX_RETRIES:
                wait = 1 * (2 ** attempt)        # 1s → 2s 指数退避
                logger.warning("AI 调用重试 %d/%d, 等待 %ds: %s", attempt + 1, AI_MAX_RETRIES, wait, e)
                time.sleep(wait)
    logger.error("AI 调用全部重试失败: %s", last_error)
    raise AITimeoutError("AI 服务超时，已重试仍失败，请稍后重试")
