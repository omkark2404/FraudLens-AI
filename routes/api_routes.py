"""
routes/api_routes.py
REST API — thin controller, no processing logic.

  POST /api/upload           → { job_id, status }
  GET  /api/result/<job_id>  → { status, data }
  GET  /api/jobs             → list of 20 most recent jobs
"""
import os
import uuid
import json
import logging
import threading
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify

from core.config import config
from models.database import create_job, get_job
from services.job_service import process_job

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__)

ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Endpoints ─────────────────────────────────────────────────────────────────

@api_bp.before_request
def require_api_key():
    """Require X-API-Key header if API_KEY is configured."""
    if request.path == "/api/health" or request.method == "OPTIONS":
        return
    if config.API_KEY:
        key = request.headers.get("X-API-Key")
        if key != config.API_KEY:
            return jsonify({"error": "Unauthorized"}), 401

@api_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint for load balancers and deployments."""
    return jsonify({"status": "ok"}), 200


@api_bp.route("/upload", methods=["POST"])
def api_upload():
    """
    POST /api/upload
    multipart/form-data: license_file, insurance_file
    Returns: { "job_id": "...", "status": "pending" }
    """
    license_file  = request.files.get("license_file")
    insurance_file = request.files.get("insurance_file")

    errors = []
    has_file = False
    
    from core.security import is_safe_file
    
    if license_file and license_file.filename != "":
        has_file = True
        if not _allowed(license_file.filename):
            errors.append("license_file: unsupported type — use jpg, png, or pdf")
        elif not is_safe_file(license_file):
            errors.append("license_file: invalid file content")
            
    if insurance_file and insurance_file.filename != "":
        has_file = True
        if not _allowed(insurance_file.filename):
            errors.append("insurance_file: unsupported type — use jpg, png, or pdf")
        elif not is_safe_file(insurance_file):
            errors.append("insurance_file: invalid file content")

    if not has_file:
        errors.append("at least one of license_file or insurance_file is required")

    if errors:
        return jsonify({"error": errors}), 422

    job_id      = str(uuid.uuid4())
    dl_filename = None
    ic_filename = None
    dl_path     = None
    ic_path     = None

    if license_file and license_file.filename != "":
        dl_filename = f"{job_id}_dl_{secure_filename(license_file.filename)}"
        dl_path = os.path.join(config.UPLOAD_FOLDER, dl_filename)
        license_file.save(dl_path)
        
    if insurance_file and insurance_file.filename != "":
        ic_filename = f"{job_id}_ic_{secure_filename(insurance_file.filename)}"
        ic_path = os.path.join(config.UPLOAD_FOLDER, ic_filename)
        insurance_file.save(ic_path)

    create_job(job_id, dl_filename, ic_filename)
    from services.job_service import submit_job
    submit_job(job_id, dl_path, ic_path)

    return jsonify({"job_id": job_id, "status": "pending"}), 202


@api_bp.route("/result/<job_id>", methods=["GET"])
def api_result(job_id: str):
    """
    GET /api/result/<job_id>

    Returns:
        202  { "status": "pending" | "processing" }
        200  { "status": "done",  "data": { ... } }
        500  { "status": "error", "error": "..." }
        404  { "error": "job not found" }
    """
    job = get_job(job_id)
    if job is None:
        return jsonify({"error": "job not found"}), 404

    status = job["status"]

    if status in ("pending", "processing"):
        return jsonify({"status": status}), 202

    if status == "error":
        payload = json.loads(job["result_json"] or "{}")
        return jsonify({"status": "error", "error": payload.get("error", "unknown")}), 500

    # done — wrap in data envelope (industry standard)
    data = json.loads(job["result_json"])
    return jsonify({"status": "done", "data": data}), 200


@api_bp.route("/jobs", methods=["GET"])
def api_jobs():
    """
    GET /api/jobs
    Returns the 20 most recent jobs (id, status, created_at).
    """
    import sqlite3
    from core.config import config as cfg
    with sqlite3.connect(cfg.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, status, created_at FROM jobs ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    return jsonify([dict(r) for r in rows]), 200
