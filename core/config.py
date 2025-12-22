"""
core/config.py
Centralised configuration loaded from environment variables (.env).
"""

import os

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_BASE_DIR, ".env"))


class Config:
    # ── Flask ──────────────────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    DEBUG: bool = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    API_KEY: str = os.getenv("API_KEY", "")

    # ── File storage ───────────────────────────────────────────────────────
    BASE_DIR: str = _BASE_DIR
    UPLOAD_FOLDER: str = os.path.join(_BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH: int = int(os.getenv("MAX_UPLOAD_MB", "16")) * 1024 * 1024
    ALLOWED_EXTENSIONS: set = {"jpg", "jpeg", "png", "pdf"}

    # ── Database ───────────────────────────────────────────────────────────
    DB_PATH: str = os.path.join(_BASE_DIR, os.getenv("DB_NAME", "ocr_jobs.db"))

    # ── OCR thresholds ────────────────────────────────────────────────────
    OCR_CONFIDENCE_THRESHOLD: float = float(os.getenv("OCR_CONF_THRESHOLD", "0.6"))
    FRAUD_ANOMALY_THRESHOLD: int = int(os.getenv("FRAUD_THRESHOLD", "2"))
    HIGH_CONFIDENCE_THRESHOLD: float = float(os.getenv("HIGH_CONF_THRESHOLD", "0.75"))
    OVERLAP_THRESHOLD_BOXES: int = int(os.getenv("OVERLAP_THRESHOLD_BOXES", "5"))
    TEXT_SIZE_VARIANCE_THRESHOLD: float = float(
        os.getenv("TEXT_SIZE_VARIANCE_THRESHOLD", "2.5")
    )

    # ── Preprocessing ──────────────────────────────────────────────────────
    PREPROCESS_BINARIZE: bool = (
        os.getenv("PREPROCESS_BINARIZE", "true").lower() == "true"
    )
    PREPROCESS_BLUR: bool = os.getenv("PREPROCESS_BLUR", "true").lower() == "true"

    # ── LLM Integration ──────────────────────────────────────────────
    GEMINI_ENABLED: bool = os.getenv("GEMINI_ENABLED", "false").lower() == "true"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    GEMINI_TIMEOUT: int = int(os.getenv("GEMINI_TIMEOUT", "10"))
    GEMINI_RETRIES: int = int(os.getenv("GEMINI_RETRIES", "2"))


config = Config()
