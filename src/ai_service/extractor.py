"""
AI 关键信息提取器
- Prompt 模板: 结构化抽取姓名/电话/邮箱/地址 + 加分字段
- 结果解析: JSON 反序列化 + 缺失字段 null 填充
- 降级策略: AI 失败时使用正则快速提取
"""
from __future__ import annotations
import re
from src.config import logger, AI_FALLBACK_ENABLED
from src.ai_service.client import chat
from src.utils.json_utils import parse_ai_json
from src.exceptions import ServerError

# ── 提取 System Prompt ──
EXTRACT_SYSTEM_PROMPT = """你是一个专业的简历信息提取工具。你的任务是从简历文本中提取结构化字段。

## 规则
1. 只返回合法 JSON，不要包含 markdown 代码块标记，不要有任何解释文字
2. 字段缺失时明确设为 null，不要返回空字符串
3. 电话号码只提取中国大陆手机号或座机号
4. 邮箱只提取标准格式的邮箱地址
5. 工作年限为数字，如果文本未明确提及则填 null
6. 项目经历为数组，每个项目包含 name(项目名称)、role(担任角色)、techStack(技术栈列表)

## 输出 JSON 结构
{
  "name": "姓名或null",
  "phone": "电话或null",
  "email": "邮箱或null",
  "address": "地址或null",
  "jobIntention": "求职意向或null",
  "expectedSalary": "期望薪资或null",
  "workYears": 数字或null,
  "education": {
    "degree": "学历或null",
    "school": "学校或null",
    "major": "专业或null",
    "graduationYear": 毕业年份数字或null
  },
  "projects": [
    {
      "name": "项目名称",
      "role": "担任角色",
      "techStack": ["技术1", "技术2"]
    }
  ]
}"""


def _build_extract_result(data: dict) -> dict:
    """从 AI 返回的字典构建标准化提取结果"""
    return {
        "name": _str_or_none(data.get("name")),
        "phone": _str_or_none(data.get("phone")),
        "email": _str_or_none(data.get("email")),
        "address": _str_or_none(data.get("address")),
        "jobIntention": _str_or_none(data.get("jobIntention")),
        "expectedSalary": _str_or_none(data.get("expectedSalary")),
        "workYears": _int_or_none(data.get("workYears")),
        "education": {
            "degree": _str_or_none((data.get("education") or {}).get("degree")),
            "school": _str_or_none((data.get("education") or {}).get("school")),
            "major": _str_or_none((data.get("education") or {}).get("major")),
            "graduationYear": _int_or_none((data.get("education") or {}).get("graduationYear")),
        },
        "projects": _normalize_projects(data.get("projects")),
    }


# ── 正则降级提取（AI 不可用时的兜底方案） ──
_RE_PHONE = re.compile(r"1[3-9]\d{9}")
_RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_RE_NAME_LINE = re.compile(r"姓\s*名[：:]\s*(\S+)")
_RE_YEARS = re.compile(r"(\d+)\s*年.*?(?:工作|经验)")


def _regex_fallback(text: str) -> dict:
    """正则快速提取，AI 不可用时的降级方案"""
    lines = text.split("\n")
    first_line = lines[0].strip() if lines else ""

    phone = _RE_PHONE.search(text)
    email = _RE_EMAIL.search(text)
    name_match = _RE_NAME_LINE.search(text)
    years_match = _RE_YEARS.search(text)

    return {
        "name": name_match.group(1) if name_match else (first_line[:20] if first_line else None),
        "phone": phone.group(0) if phone else None,
        "email": email.group(0) if email else None,
        "address": None,
        "jobIntention": None,
        "expectedSalary": None,
        "workYears": int(years_match.group(1)) if years_match else None,
        "education": {"degree": None, "school": None, "major": None, "graduationYear": None},
        "projects": [],
    }


def _str_or_none(val) -> str | None:
    """非空字符串，否则 None"""
    if isinstance(val, str) and val.strip():
        return val.strip()
    return None


def _int_or_none(val) -> int | None:
    """有效整数，否则 None"""
    if isinstance(val, int) and not isinstance(val, bool):
        return val
    if isinstance(val, float) and val == int(val):
        return int(val)
    if isinstance(val, str) and val.strip().isdigit():
        return int(val.strip())
    return None


def _normalize_projects(raw) -> list[dict]:
    """规范化项目经历列表"""
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        proj = {
            "name": _str_or_none(item.get("name")) or "",
            "role": _str_or_none(item.get("role")) or "",
            "techStack": _normalize_tech_stack(item.get("techStack")),
        }
        if proj["name"] or proj["role"]:
            result.append(proj)
    return result


def _normalize_tech_stack(raw) -> list[str]:
    """规范化技术栈为字符串列表"""
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if s and str(s).strip()]
    if isinstance(raw, str) and raw.strip():
        return [s.strip() for s in raw.split(",") if s.strip()]
    return []


def extract_info(resume_text: str) -> dict:
    """从简历文本中提取结构化信息，AI 失败时降级为正则提取"""
    if not resume_text or not resume_text.strip():
        raise ServerError("简历文本为空，无法提取信息")

    # 尝试 AI 提取
    try:
        user_prompt = f"请从以下简历文本中提取关键信息：\n\n{resume_text}"
        messages = [
            {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
        raw_response = chat(messages)
        data = parse_ai_json(raw_response, "简历提取")
        return _build_extract_result(data)
    except Exception as e:
        if not AI_FALLBACK_ENABLED:
            raise
        logger.warning("AI 提取失败，降级为正则提取: %s", e)
        return _regex_fallback(resume_text)
