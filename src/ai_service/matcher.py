"""
AI 岗位匹配与评分模块
- Prompt: 招聘评估专家角色，要求分维度打分 + 结构化输出
- 解析: JSON 反序列化 + 分值范围裁剪 + 缺失字段填充
"""
from __future__ import annotations
import json
from src.ai_service.client import chat
from src.utils.json_utils import parse_ai_json
from src.exceptions import ServerError

# ── 匹配 System Prompt ──
MATCH_SYSTEM_PROMPT = """你是一位资深招聘评估专家。你需要根据简历信息和岗位需求，进行精确的匹配度评估。

## 评分规则
- 技能匹配率(skillMatch): 简历技能栈与岗位要求的重合程度，0-100 整数
- 工作经验相关性(experienceMatch): 工作年限、项目经验与岗位的匹配度，0-100 整数
- 学历匹配度(educationMatch): 学历层次、专业与岗位要求的一致性，0-100 整数
- 综合评分(totalScore): 综合上述三维度的加权评分，计算公式为 skillMatch*0.4 + experienceMatch*0.35 + educationMatch*0.25，四舍五入取整

## 输出要求
1. 只返回合法 JSON，不要包含 markdown 代码块标记，不要有任何解释文字
2. strengths 列出候选人的 2-4 个核心优势点
3. missingKeywords 列出岗位要求但简历中缺失的 2-5 个关键技能或经验
4. summary 用 2-3 句话总结匹配结论，给出面试建议

## 输出 JSON 结构
{
  "totalScore": 85,
  "skillMatch": 90,
  "experienceMatch": 80,
  "educationMatch": 100,
  "strengths": ["优势1", "优势2"],
  "missingKeywords": ["缺失技能1", "缺失技能2"],
  "summary": "综合评价文本"
}"""


def _clamp_score(val) -> int:
    """确保分值在 0-100 范围内"""
    try:
        v = int(val)
    except (ValueError, TypeError):
        return 0
    return max(0, min(100, v))


def _build_match_result(data: dict) -> dict:
    """从 AI 返回的字典构建标准化匹配结果"""
    return {
        "totalScore": _clamp_score(data.get("totalScore", 0)),
        "skillMatch": _clamp_score(data.get("skillMatch", 0)),
        "experienceMatch": _clamp_score(data.get("experienceMatch", 0)),
        "educationMatch": _clamp_score(data.get("educationMatch", 0)),
        "strengths": _normalize_string_list(data.get("strengths")),
        "missingKeywords": _normalize_string_list(data.get("missingKeywords")),
        "summary": (data.get("summary") or "").strip(),
    }


def _normalize_string_list(raw) -> list[str]:
    """规范化字符串列表"""
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if s and str(s).strip()]
    if isinstance(raw, str) and raw.strip():
        return [s.strip() for s in raw.split("\n") if s.strip()]
    return []


def match_resume(resume_text: str, extracted_info: dict, job_description: str) -> dict:
    """对简历与岗位进行匹配评分"""
    if not job_description or not job_description.strip():
        raise ServerError("岗位描述为空，无法进行匹配")

    # 构建用户 prompt：同时提供清洗文本 + 已提取的结构化信息
    info_json = json.dumps(extracted_info, ensure_ascii=False, indent=2)
    user_prompt = (
        "请对以下候选人简历与岗位需求进行匹配评估。\n\n"
        "=== 岗位需求 ===\n"
        f"{job_description.strip()}\n\n"
        "=== 候选人简历（结构化提取） ===\n"
        f"{info_json}\n\n"
        "=== 候选人简历（原文） ===\n"
        f"{resume_text[:3000]}\n"
    )

    messages = [
        {"role": "system", "content": MATCH_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    raw_response = chat(messages)
    data = parse_ai_json(raw_response, "匹配评分")
    return _build_match_result(data)
