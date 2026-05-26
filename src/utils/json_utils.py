"""
共享 JSON 解析工具 —— 消除 extractor / matcher 中的重复解析逻辑
"""
from __future__ import annotations
import json
import re
from src.exceptions import ServerError


def parse_ai_json(raw: str, label: str = "AI 返回") -> dict:
    """
    解析 AI 返回的 JSON 字符串，带多层容错:
      1. 去除 markdown 代码块包裹
      2. 直接 JSON 解析
      3. 正则提取第一个 {} 对象后解析
    失败抛出 ServerError
    """
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                raise ServerError(f"{label}内容无法解析为 JSON，请重试")
        else:
            raise ServerError(f"{label}内容无法解析为 JSON，请重试")

    if not isinstance(data, dict):
        raise ServerError(f"{label}格式异常，请重试")

    return data
