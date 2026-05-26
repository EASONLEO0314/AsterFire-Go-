"""
自定义异常类层次 —— 按业务错误码分层，Flask 全局 errorhandler 统一拦截
"""
from __future__ import annotations
from typing import Optional
from src.config import logger


class AppException(Exception):
    """业务异常基类，所有自定义异常由此派生"""
    code = 4
    message = "服务器内部错误"

    def __init__(self, message: Optional[str] = None):
        if message is not None:
            self.message = message
        super().__init__(self.message)


class ParamError(AppException):
    """参数错误 —— code=1"""
    code = 1
    message = "请求参数错误"


class FileError(AppException):
    """文件错误 —— code=2"""
    code = 2
    message = "文件处理失败"


class AITimeoutError(AppException):
    """AI 超时或调用失败 —— code=3"""
    code = 3
    message = "AI 服务超时，请稍后重试"


class ServerError(AppException):
    """服务器内部错误 —— code=4"""
    code = 4
    message = "服务器内部错误"


def register_error_handlers(app):
    """向 Flask app 注册全局异常拦截"""
    from flask import jsonify

    @app.errorhandler(AppException)
    def _handle_app_exception(error: AppException):
        return jsonify({"code": error.code, "msg": error.message, "data": None}), 200

    @app.errorhandler(413)
    def _handle_too_large(_error):
        return jsonify({"code": 2, "msg": "文件大小超过服务器限制", "data": None}), 200

    @app.errorhandler(404)
    def _handle_not_found(_error):
        return jsonify({"code": 1, "msg": "接口路径不存在", "data": None}), 200

    @app.errorhandler(500)
    def _handle_internal(_error):
        return jsonify({"code": 4, "msg": "服务器内部异常", "data": None}), 200

    @app.errorhandler(Exception)
    def _handle_unknown(error):
        # 兜底：非预期异常统一返回 code=4
        logger.exception("未捕获异常: %s", error)
        return jsonify({"code": 4, "msg": "服务器处理异常", "data": None}), 200
