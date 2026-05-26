"""
文件校验工具 —— 扩展名白名单 / 大小上限 / MD5 指纹
"""
import hashlib
import os
from werkzeug.datastructures import FileStorage
from src.config import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES
from src.exceptions import ParamError, FileError


def get_extension(filename: str) -> str:
    """取小写扩展名，无扩展名返回空串"""
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def validate_extension(filename: str) -> None:
    """校验扩展名是否在白名单内，不通过抛出 ParamError"""
    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ParamError(f"不支持的文件格式 .{ext}，仅允许 PDF")


def validate_file_size(file_storage: FileStorage) -> None:
    """校验文件大小 ≤ 10MB，不通过抛出 FileError"""
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    if size > MAX_FILE_SIZE_BYTES:
        max_mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise FileError(f"文件大小超过 {max_mb}MB 限制")


def calculate_md5(file_storage: FileStorage) -> str:
    """计算文件 MD5，用于缓存指纹去重"""
    file_storage.seek(0)
    digest = hashlib.md5()
    while chunk := file_storage.read(8192):
        digest.update(chunk)
    file_storage.seek(0)
    return digest.hexdigest()
