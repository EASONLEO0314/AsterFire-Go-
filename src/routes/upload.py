"""
简历上传与解析接口 — POST /api/resume/upload
"""
from flask import Blueprint, request, jsonify
from src.config import logger
from src.utils import validate_extension, validate_file_size, calculate_md5
from src.parser import parse_pdf
from src.cache import put_parsed
from src.exceptions import ParamError, FileError

upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/api/resume/upload", methods=["POST"])
def upload_resume():
    """
    上传并解析 PDF 简历
    Request:  multipart/form-data, field: file
    Response: {"code":0,"msg":"success","data":{"resumeId","fileName","pages","cleanedText","md5"}}
    """
    # ── 1. 参数校验 ──
    if "file" not in request.files:
        raise ParamError("请上传 PDF 文件")

    file = request.files["file"]
    if file.filename is None or file.filename.strip() == "":
        raise ParamError("请选择要上传的文件")

    # ── 2. 扩展名白名单 ──
    validate_extension(file.filename)

    # ── 3. 文件大小校验 ──
    try:
        validate_file_size(file)
    except FileError:
        raise
    except Exception:
        raise FileError("文件读取失败，请重试")

    # ── 4. PDF 解析 + 文本清洗 ──
    try:
        result = parse_pdf(file)
    except FileError:
        raise
    except Exception as e:
        logger.exception("PDF 解析异常")
        raise FileError("PDF 解析过程中发生未知错误")

    # ── 5. 计算 MD5 + 写入缓存 ──
    try:
        md5 = calculate_md5(file)
        put_parsed(md5, result["resumeId"], result)
    except Exception as e:
        logger.warning("MD5/缓存写入失败: %s", e)
        md5 = ""

    return jsonify({
        "code": 0,
        "msg": "success",
        "data": {
            **result,
            "md5": md5,
        },
    })
