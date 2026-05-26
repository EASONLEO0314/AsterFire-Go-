"""
综合查询 + 缓存管理接口
"""
from flask import Blueprint, jsonify
from src.config import logger
from src.cache import get_full_result, get_stats, clear_expired, redis_health
from src.exceptions import ParamError, ServerError

query_bp = Blueprint("query", __name__)


@query_bp.route("/api/resume/<resume_id>", methods=["GET"])
def get_resume_full(resume_id: str):
    """
    综合查询：按 resumeId 返回完整分析结果
    路径参数: resumeId (UUID)
    响应: {code, msg, data: {resumeId, status, fileInfo, cleanedText, extractedInfo, matchResults, cachedAt}}
    """
    if not resume_id or not resume_id.strip():
        raise ParamError("请提供有效的 resumeId")

    result = get_full_result(resume_id.strip())
    if result is None:
        raise ParamError("指定 resumeId 对应的简历不存在或已过期，请重新上传")

    return jsonify({
        "code": 0,
        "msg": "success",
        "data": result,
    })


@query_bp.route("/api/cache/stats", methods=["GET"])
def cache_stats():
    """
    缓存运行时统计
    响应: {code, msg, data: {memoryEntries, activeEntries, parsedCount, extractedCount, matchedCount, redis, ...}}
    """
    stats = get_stats()
    stats["redisHealth"] = redis_health()
    return jsonify({
        "code": 0,
        "msg": "success",
        "data": stats,
    })


@query_bp.route("/api/cache/cleanup", methods=["POST"])
def cache_cleanup():
    """手动触发过期条目清理"""
    try:
        removed = clear_expired()
        logger.info("缓存清理完成, 移除 %d 条", removed)
        return jsonify({
            "code": 0,
            "msg": f"清理完成，移除 {removed} 条过期缓存",
            "data": {"removed": removed},
        })
    except Exception as e:
        logger.exception("缓存清理异常")
        raise ServerError("缓存清理失败")
