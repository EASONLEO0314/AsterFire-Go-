"""
内存缓存层 —— 字典 + 惰性淘汰，可选 Redis 二级缓存
- 主键: 文件 MD5
- 二级索引: resumeId → MD5
- TTL: 24 小时，读取时惰性淘汰
- 内存上限: 500 条，超出淘汰最旧条目
"""
import time
import json
import sys
import threading
from typing import Any, Optional

from src.config import CACHE_TTL_SECONDS, REDIS_URL, logger

# ── 可选 Redis 客户端（惰性初始化 + 连接池） ──
_redis_client: Optional[Any] = None
MAX_MEMORY_ENTRIES = 500           # 内存中最多缓存条目数


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if REDIS_URL:
        try:
            import redis
            _redis_client = redis.from_url(
                REDIS_URL,
                socket_connect_timeout=3,
                socket_keepalive=True,
                health_check_interval=30,
            )
            _redis_client.ping()
        except Exception as e:
            logger.warning("Redis 连接失败: %s", e)
            _redis_client = False
    else:
        _redis_client = False
    return _redis_client if _redis_client is not False else None


def redis_health() -> dict:
    """Redis 连接健康检查"""
    r = _get_redis()
    if r is None:
        return {"available": False, "reason": "未配置 REDIS_URL 或连接失败"}
    try:
        r.ping()
        return {"available": True, "url": REDIS_URL.split("@")[-1] if "@" in REDIS_URL else REDIS_URL}
    except Exception as e:
        return {"available": False, "reason": str(e)}


# ── 内存存储 ──
_store: dict[str, dict] = {}
_id_index: dict[str, str] = {}
_lock = threading.RLock()


def _now() -> float:
    return time.time()


def _is_expired(entry: dict) -> bool:
    return (_now() - entry.get("createdAt", 0)) > CACHE_TTL_SECONDS


def _evict_if_needed() -> None:
    """内存上限保护：超出 MAX_MEMORY_ENTRIES 时淘汰最旧条目"""
    if len(_store) <= MAX_MEMORY_ENTRIES:
        return
    # 按 createdAt 排序，淘汰最旧的超出部分
    sorted_items = sorted(_store.items(), key=lambda kv: kv[1].get("createdAt", 0))
    to_remove = len(_store) - MAX_MEMORY_ENTRIES
    for md5, _entry in sorted_items[:to_remove]:
        rid = _entry.get("resumeId", "")
        _store.pop(md5, None)
        _id_index.pop(rid, None)


def _save_to_redis(md5: str, entry: dict) -> None:
    r = _get_redis()
    if r is None:
        return
    try:
        r.setex(f"resume:{md5}", CACHE_TTL_SECONDS, json.dumps(entry, ensure_ascii=False))
    except Exception:
        pass


def _load_from_redis(md5: str) -> Optional[dict]:
    r = _get_redis()
    if r is None:
        return None
    try:
        raw = r.get(f"resume:{md5}")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def put_parsed(md5: str, resume_id: str, parsed: dict) -> None:
    """写入解析结果"""
    entry = {
        "md5": md5,
        "resumeId": resume_id,
        "parsed": parsed,
        "extracted": None,
        "matched": {},
        "createdAt": _now(),
    }
    with _lock:
        _store[md5] = entry
        _id_index[resume_id] = md5
        _evict_if_needed()
    _save_to_redis(md5, entry)


def put_extracted(md5: str, extracted: dict) -> None:
    """写入/更新 AI 提取结果"""
    with _lock:
        entry = _store.get(md5)
        if entry is None:
            entry = {
                "md5": md5,
                "resumeId": "",
                "parsed": None,
                "extracted": None,
                "matched": {},
                "createdAt": _now(),
            }
            _store[md5] = entry
        entry["extracted"] = extracted
    _save_to_redis(md5, entry)


def put_matched(md5: str, job_md5: str, match_result: dict) -> None:
    """写入/更新匹配评分结果"""
    with _lock:
        entry = _store.get(md5)
        if entry is None:
            return
        if entry.get("matched") is None:
            entry["matched"] = {}
        entry["matched"][job_md5] = match_result
    _save_to_redis(md5, entry)


def get_by_md5(md5: str) -> Optional[dict]:
    """按 MD5 查询，自动惰性淘汰过期数据"""
    with _lock:
        entry = _store.get(md5)
        if entry is None:
            redis_entry = _load_from_redis(md5)
            if redis_entry:
                _store[md5] = redis_entry
                _id_index[redis_entry.get("resumeId", "")] = md5
                entry = redis_entry

        if entry and _is_expired(entry):
            _store.pop(md5, None)
            return None
        return entry


def get_by_resume_id(resume_id: str) -> Optional[dict]:
    """按 resumeId 查询"""
    with _lock:
        md5 = _id_index.get(resume_id)
        if md5 is None:
            return None
        return get_by_md5(md5)


# ── 综合查询 / 统计 / 管理 ──

def get_full_result(resume_id: str) -> Optional[dict]:
    """
    按 resumeId 聚合全部处理结果，返回统一综合视图
    返回 None 表示简历不存在或已过期
    """
    entry = get_by_resume_id(resume_id)
    if entry is None:
        return None

    parsed = entry.get("parsed") or {}
    extracted = entry.get("extracted")
    matched_map = entry.get("matched") or {}

    # 确定处理状态
    if extracted and matched_map:
        status = "matched"
    elif extracted:
        status = "extracted"
    elif parsed:
        status = "parsed"
    else:
        status = "unknown"

    return {
        "resumeId": resume_id,
        "status": status,
        "fileInfo": {
            "fileName": parsed.get("fileName", ""),
            "pages": parsed.get("pages", 0),
        },
        "cleanedText": parsed.get("cleanedText", ""),
        "extractedInfo": extracted,
        "matchResults": [
            {"jobDigest": k[:16], "result": v} for k, v in matched_map.items()
        ] if matched_map else None,
        "cachedAt": entry.get("createdAt", 0),
        "ttlSeconds": CACHE_TTL_SECONDS,
    }


def get_stats() -> dict:
    """缓存运行时统计"""
    with _lock:
        now = _now()
        total = len(_store)
        expired = sum(1 for e in _store.values() if _is_expired(e))
        active = total - expired
        parsed_count = sum(1 for e in _store.values() if e.get("parsed"))
        extracted_count = sum(1 for e in _store.values() if e.get("extracted"))
        matched_count = sum(
            len(e.get("matched") or {}) for e in _store.values()
        )

        # 估算内存占用
        try:
            mem_bytes = sys.getsizeof(_store) + sys.getsizeof(_id_index)
            for k, v in _store.items():
                mem_bytes += sys.getsizeof(k) + sys.getsizeof(str(v))
        except Exception:
            mem_bytes = 0

    r = _get_redis()
    redis_ok = False
    redis_keys = 0
    if r is not None:
        try:
            redis_keys = r.dbsize()
            redis_ok = True
        except Exception:
            pass

    return {
        "memoryEntries": total,
        "activeEntries": active,
        "expiredEntries": expired,
        "parsedCount": parsed_count,
        "extractedCount": extracted_count,
        "matchedCount": matched_count,
        "estimatedMemoryBytes": mem_bytes,
        "maxEntries": MAX_MEMORY_ENTRIES,
        "ttlSeconds": CACHE_TTL_SECONDS,
        "redis": {
            "available": redis_ok,
            "keys": redis_keys,
            "configured": bool(REDIS_URL),
        },
    }


def clear_expired() -> int:
    """主动清理所有过期条目，返回清理数量"""
    removed = 0
    with _lock:
        expired_md5s = [md5 for md5, e in _store.items() if _is_expired(e)]
        for md5 in expired_md5s:
            rid = _store[md5].get("resumeId", "")
            _store.pop(md5, None)
            _id_index.pop(rid, None)
            removed += 1
    return removed


def delete_entry(resume_id: str) -> bool:
    """按 resumeId 删除缓存条目，返回是否成功"""
    with _lock:
        md5 = _id_index.get(resume_id)
        if md5 is None:
            return False
        _store.pop(md5, None)
        _id_index.pop(resume_id, None)
    # 同步删除 Redis
    r = _get_redis()
    if r is not None:
        try:
            r.delete(f"resume:{md5}")
        except Exception:
            pass
    return True
