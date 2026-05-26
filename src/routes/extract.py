"""
AI 关键信息提取接口 — POST /api/resume/extract
"""
import hashlib
from flask import Blueprint, request, jsonify
from src.config import logger
from src.ai_service import extract_info
from src.cache import get_by_resume_id, put_extracted
from src.exceptions import ParamError

extract_bp = Blueprint("extract", __name__)


@extract_bp.route("/api/resume/extract", methods=["POST"])
def extract_resume():
    """
    AI 提取简历关键信息
    Request:  {"resumeId": "uuid"}  或  {"text": "简历文本"}
    Response: {"code":0,"msg":"success","data":{name,phone,email,address,...}}
    """
    body = request.get_json(silent=True) or {}

    # ── 1. 参数校验 + 缓存一次查询 ──
    resume_id = (body.get("resumeId") or "").strip()
    direct_text = (body.get("text") or "").strip()

    entry = None
    if resume_id:
        entry = get_by_resume_id(resume_id)           # 仅一次缓存查询
        if entry is None or entry.get("parsed") is None:
            raise ParamError("指定 resumeId 对应的简历不存在或已过期，请重新上传")

        # 已有提取结果 → 直接返回缓存
        if entry.get("extracted"):
            return jsonify({
                "code": 0,
                "msg": "success (cached)",
                "data": entry["extracted"],
            })

        resume_text = entry["parsed"].get("cleanedText", "")
        md5 = entry.get("md5", "")
    elif direct_text:
        resume_text = direct_text
        md5 = hashlib.md5(direct_text.encode("utf-8")).hexdigest()
    else:
        raise ParamError("请提供 resumeId 或 text 参数")

    # ── 2. AI 提取（异常由全局 errorhandler 统一处理） ──
    extracted = extract_info(resume_text)

    # ── 3. 注入 resumeId + 写入缓存 ──
    extracted["resumeId"] = resume_id or ""
    try:
        put_extracted(md5, extracted)
    except Exception as e:
        logger.warning("提取结果缓存写入失败: %s", e)

    return jsonify({
        "code": 0,
        "msg": "success",
        "data": extracted,
    })
