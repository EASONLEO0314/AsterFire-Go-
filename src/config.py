"""
全局配置模块 —— 集中管理环境变量、服务常量和业务阈值
"""
import os
import logging

# ── 日志 ────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("resume_ai")

# ── AI 服务 ──────────────────────────────────────
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "qwen-plus")
AI_TIMEOUT = 30                         # 请求超时秒数
AI_MAX_RETRIES = 2                      # 最大重试次数
AI_FALLBACK_ENABLED = os.getenv("AI_FALLBACK_ENABLED", "1") == "1"  # AI 失败时启用正则降级

# ── VL OCR 降级 ────────────────────────────────────
VL_MODEL = os.getenv("VL_MODEL", "qwen-vl-plus")       # 多模态模型，扫描 PDF 时 OCR 使用
OCR_DPI = int(os.getenv("OCR_DPI", "200"))              # PDF → 图片渲染 DPI
OCR_ENABLED = os.getenv("OCR_ENABLED", "1") == "1"      # 是否启用 VL OCR 降级

# ── 文件校验 ─────────────────────────────────────
ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_PAGE_COUNT = 10                     # 最多解析页数

# ── 缓存 ────────────────────────────────────────
CACHE_TTL_SECONDS = 24 * 60 * 60        # 24 小时
REDIS_URL = os.getenv("REDIS_URL", "")

# ── 服务 ────────────────────────────────────────
JSON_AS_ASCII = False                   # Flask JSON 中文不转义
