"""
core/app_factory.py
Flask application factory — registers blueprints and initialises extensions.
"""

import logging
import os

from flask import Flask
from flask_cors import CORS

from core.config import config
from models.database import init_db


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(config.BASE_DIR, "templates"),
        static_folder=os.path.join(config.BASE_DIR, "static"),
    )

    @app.before_request
    def log_request():
        from flask import request

        logging.getLogger(__name__).info(f"{request.method} {request.path}")

    @app.errorhandler(413)
    def too_large(e):
        from flask import jsonify, request

        if request.path.startswith("/api/"):
            return jsonify({"error": "File too large (max 16MB)"}), 413
        return "File too large (max 16MB)", 413

    # ── Core config ────────────────────────────────────────────────────────
    app.secret_key = config.SECRET_KEY
    app.config["UPLOAD_FOLDER"] = config.UPLOAD_FOLDER
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH

    # ── CORS ───────────────────────────────────────────────────────────────
    CORS(app, resources={r"/api/*": {"origins": config.CORS_ORIGINS}})

    # ── Logging ────────────────────────────────────────────────────────────
    logging.basicConfig(
        level=logging.DEBUG if config.DEBUG else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    )

    # ── Upload folder ──────────────────────────────────────────────────────
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

    # ── Database ───────────────────────────────────────────────────────────
    init_db()
    from services.job_service import cleanup_stale_jobs

    cleanup_stale_jobs()

    # ── Blueprints ─────────────────────────────────────────────────────────
    from routes.api_routes import api_bp
    from routes.upload_routes import upload_bp

    app.register_blueprint(upload_bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")

    return app
