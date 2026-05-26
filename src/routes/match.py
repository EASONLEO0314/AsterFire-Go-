"""
简历与岗位匹配评分接口 — POST /api/match
"""
import hashlib
from flask import Blueprint, request, jsonify
from src.config import logger
from src.ai_service import match_resume
from src.cache import get_by_resume_id, put_matched
from src.exceptions import ParamError

match_bp = Blueprint("match", __name__)


@match_bp.route("/api/match", methods=["POST"])
def match_job():
    """
    简历与岗位匹配评分
    Request:  {"resumeId": "uuid", "jobDescription": "岗位描述文本"}
    Response: {"code":0,"msg":"success","data":{totalScore,skillMatch,experienceMatch,educationMatch,strengths,missingKeywords,summary}}
    """
    body = request.get_json(silent=True) or {}

    # ── 1. 参数校验 ──
    resume_id = (body.get("resumeId") or "").strip()
    job_desc = (body.get("jobDescription") or "").strip()

    if not resume_id:
        raise ParamError("请提供 resumeId")
    if not job_desc:
        raise ParamError("请提供 jobDescription 岗位描述")

    # ── 2. 从缓存获取简历解析 + 提取结果 ──
    entry = get_by_resume_id(resume_id)
    if entry is None or entry.get("parsed") is None:
        raise ParamError("指定 resumeId 对应的简历不存在或已过期，请重新上传")
    if entry.get("extracted") is None:
        raise ParamError("请先完成简历信息提取（调用 /api/resume/extract）")

    resume_text = entry["parsed"].get("cleanedText", "")
    extracted = entry["extracted"]

    # ── 3. 缓存检查：同一岗位是否已评分 ──
    job_md5 = hashlib.md5(job_desc.encode("utf-8")).hexdigest()
    matched_cache = entry.get("matched") or {}
    if job_md5 in matched_cache:
        return jsonify({
            "code": 0,
            "msg": "success (cached)",
            "data": matched_cache[job_md5],
        })

    # ── 4. AI 匹配评分（异常由全局 errorhandler 处理） ──
    result = match_resume(resume_text, extracted, job_desc)

    # ── 5. 注入 resumeId + 写入缓存 ──
    result["resumeId"] = resume_id
    try:
        md5 = entry.get("md5", "")
        if md5:
            put_matched(md5, job_md5, result)
    except Exception as e:
        logger.warning("匹配结果缓存写入失败: %s", e)

    return jsonify({
        "code": 0,
        "msg": "success",
        "data": result,
    })
