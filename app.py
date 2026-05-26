"""
AI 智能简历分析系统 — Flask 主入口
适配阿里云 FC HTTP 触发器，同时支持本地开发
"""
import os
import time
from flask import Flask, send_from_directory, abort, jsonify, request
from src.config import JSON_AS_ASCII, logger
from src.routes import upload_bp, extract_bp, match_bp, query_bp
from src.exceptions import register_error_handlers


def create_app() -> Flask:
    """Flask 应用工厂"""
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = JSON_AS_ASCII
    app.config["MAX_CONTENT_LENGTH"] = 11 * 1024 * 1024  # 11 MB（业务校验 10MB + 1MB 余量）

    # ── 注册蓝图 ──
    app.register_blueprint(upload_bp)
    app.register_blueprint(extract_bp)
    app.register_blueprint(match_bp)
    app.register_blueprint(query_bp)

    # ── 全局异常处理 ──
    register_error_handlers(app)

    # ── 请求计时 + CORS ──
    @app.before_request
    def _start_timer():
        request._start_time = time.time()

    @app.after_request
    def _add_cors_and_log(response):
        # CORS 头
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Max-Age"] = "86400"  # 预检缓存 24h

        # 请求日志
        elapsed = int((time.time() - getattr(request, "_start_time", time.time())) * 1000)
        logger.info("%s %s %s %dms", request.method, request.path, response.status_code, elapsed)
        return response

    # ── 健康检查 ──
    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "code": 0,
            "msg": "ok",
            "data": {"status": "healthy", "timestamp": int(time.time())},
        })

    # ── 本地开发：前端静态文件 ──
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")

    @app.route("/")
    def serve_index():
        return send_from_directory(frontend_dir, "index.html")

    @app.route("/<path:filename>")
    def serve_static(filename):
        file_path = os.path.join(frontend_dir, filename)
        if os.path.isfile(file_path):
            return send_from_directory(frontend_dir, filename)
        abort(404)

    return app


# FC 入口
app = create_app()
