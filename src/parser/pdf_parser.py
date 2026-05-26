"""
PDF 解析与文本清洗模块
依赖: PyPDF2 — 轻量级 PDF 文本提取
"""
import re
import os
import shutil
import tempfile
import uuid
import unicodedata
from PyPDF2 import PdfReader
from werkzeug.datastructures import FileStorage
from src.config import MAX_PAGE_COUNT, OCR_ENABLED, OCR_DPI, logger
from src.exceptions import FileError


def _clean_text(raw: str) -> str:
    """
    全链路文本清洗管道:
      1. 移除 BOM / 零宽字符
      2. 移除控制字符 (保留 \\n \\r \\t)
      3. Unicode NFC 规范化
      4. 按行清洗: 去首尾空白, 滤纯乱码行
      5. 压缩多余空行 (最多保留 2 个连续空行)
    """
    if not raw:
        return ""

    # 1. 移除常见不可见字符 (BOM, 零宽空格, 软连字符等)
    raw = raw.replace("﻿", "")
    raw = re.sub(r"[​-‏  ­]", "", raw)

    # 2. 按 Unicode 类别过滤控制/格式字符 (保留 \\n \\r \\t)
    cleaned_chars: list[str] = []
    for ch in raw:
        cat = unicodedata.category(ch)
        if cat == "Cc":
            if ch in ("\n", "\r", "\t"):
                cleaned_chars.append(ch)
            # 其余控制字符丢弃
            continue
        if cat in ("Cs", "Co", "Cn"):
            # 代理对、私有区、未分配 — 丢弃
            continue
        cleaned_chars.append(ch)
    raw = "".join(cleaned_chars)

    # 3. Unicode NFC 规范化 (统一全角/半角等价字符)
    raw = unicodedata.normalize("NFC", raw)

    # 4. 逐行清洗
    lines = raw.splitlines()
    clean_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            clean_lines.append("")
            continue
        # 过滤纯乱码行: 有效可见字符占比 < 30% 则丢弃
        visible = sum(1 for ch in stripped if ch != " " and unicodedata.category(ch) not in ("Cc", "Cs", "Co", "Cn", "Cf"))
        if visible / len(stripped) < 0.3:
            continue
        clean_lines.append(stripped)

    # 5. 压缩多余空行: 连续 ≥3 空行 → 保留 2 个
    result_lines: list[str] = []
    blank_streak = 0
    for line in clean_lines:
        if line == "":
            blank_streak += 1
            if blank_streak <= 2:
                result_lines.append("")
        else:
            blank_streak = 0
            result_lines.append(line)

    return "\n".join(result_lines).strip()


def _ocr_fallback(file_storage: FileStorage) -> str:
    """OCR 降级: PyMuPDF 渲染 PDF 页面 → 临时 PNG → VL 模型 OCR → 文本清洗

    返回清洗后的文本。任何异常均向上层抛出，由 parse_pdf 统一处理。
    """
    import fitz  # pymupdf，延迟导入，非 OCR 路径零开销

    from src.ai_service.client import ocr_images  # 延迟导入，避免循环依赖

    file_storage.seek(0)
    pdf_bytes = file_storage.read()

    temp_dir = tempfile.mkdtemp(prefix="ocr_pages_")
    image_paths: list[str] = []

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = doc.page_count

        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=OCR_DPI)
            img_path = os.path.join(temp_dir, f"page_{i + 1}.png")
            pix.save(img_path)
            image_paths.append(img_path)
            logger.info(
                "OCR 预处理 [%d/%d]: 页面 %d 渲染完成 size=%dx%d",
                i + 1, page_count, i + 1, pix.width, pix.height,
            )

        if not image_paths:
            return ""

        ocr_text = ocr_images(image_paths)
        return _clean_text(ocr_text)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        logger.info("OCR 临时文件清理完成: %s", temp_dir)


def parse_pdf(file_storage: FileStorage) -> dict:
    """
    解析 PDF 文件，返回:
      {
        "resumeId": str (UUID v4),
        "fileName": str,
        "pages": int,
        "cleanedText": str,
      }
    raise FileError: 解析失败 / 页数超限 / 文本为空
    """
    file_storage.seek(0)

    try:
        reader = PdfReader(file_storage.stream)
    except Exception:
        raise FileError("PDF 文件解析失败，文件可能已损坏或不是有效 PDF")

    page_count = len(reader.pages)
    if page_count == 0:
        raise FileError("PDF 文件无有效页面")
    if page_count > MAX_PAGE_COUNT:
        raise FileError(f"PDF 页数超过 {MAX_PAGE_COUNT} 页限制，当前 {page_count} 页")

    # 逐页提取文本
    raw_parts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text()
            if text:
                raw_parts.append(text)
        except Exception:
            # 单页提取失败不阻塞整体，记录警告后继续
            continue

    raw_text = "\n".join(raw_parts)
    cleaned = _clean_text(raw_text)

    if not cleaned:
        if OCR_ENABLED:
            logger.info("PyPDF2 文本提取为空 (疑似扫描版 PDF)，启动 VL OCR 降级方案")
            try:
                cleaned = _ocr_fallback(file_storage)
            except FileError:
                raise
            except Exception as e:
                logger.exception("VL OCR 降级方案执行异常")
                raise FileError(f"PDF OCR 识别失败: {e}")
            if not cleaned:
                raise FileError(
                    "PDF 文本提取为空，OCR 识别亦未能提取到文字，"
                    "请确认简历内容可读或为文字型 PDF"
                )
        else:
            raise FileError("PDF 文本提取为空，请确认简历为文字型 PDF（非扫描图片型）")

    resume_id = str(uuid.uuid4())

    return {
        "resumeId": resume_id,
        "fileName": file_storage.filename or "unknown.pdf",
        "pages": page_count,
        "cleanedText": cleaned,
    }
