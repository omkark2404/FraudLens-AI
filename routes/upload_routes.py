"""
routes/upload_routes.py
HTML-serving routes — thin controller, no processing logic.

  GET  /              → upload page
  POST /upload        → validate, save files, create job, dispatch thread
  GET  /status/<id>   → polling page (JS drives /api/result/<id>)
  GET  /result/<id>   → server-rendered final result page
"""
import os
import uuid
import json
import logging
import threading
from werkzeug.utils import secure_filename
from flask import (Blueprint, render_template, request,
                   redirect, url_for, flash, abort)

from core.config import config
from models.database import create_job, get_job
from services.job_service import process_job

logger = logging.getLogger(__name__)
upload_bp = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Routes ────────────────────────────────────────────────────────────────────

@upload_bp.route("/")
def index():
    return render_template("index.html")


@upload_bp.route("/upload", methods=["POST"])
def upload():
    try:
        license_file  = request.files.get("license_file")
        insurance_file = request.files.get("insurance_file")

        errors = []
        has_file = False

        if license_file and license_file.filename != "":
            has_file = True
            if not _allowed(license_file.filename):
                errors.append("Driver's License: invalid file type (JPG, PNG, PDF only).")

        if insurance_file and insurance_file.filename != "":
            has_file = True
            if not _allowed(insurance_file.filename):
                errors.append("Insurance Card: invalid file type (JPG, PNG, PDF only).")

        if not has_file:
            errors.append("At least one document (Driver's License or Insurance Card) is required.")

        if errors:
            for e in errors:
                flash(e, "warning")
            return redirect(url_for("upload.index"))

        # Save files with unique prefix to avoid collisions
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

        logger.info("Files saved for job %s", job_id)

        create_job(job_id, dl_filename, ic_filename)

        # Dispatch background worker (daemon=True prevents zombie threads on shutdown)
        threading.Thread(
            target=process_job,
            args=(job_id, dl_path, ic_path),
            daemon=True,
        ).start()

        return redirect(url_for("upload.status", job_id=job_id))

    except Exception as exc:
        logger.error("Upload error: %s", exc, exc_info=True)
        flash("An unexpected error occurred during upload.", "danger")
        return redirect(url_for("upload.index"))


@upload_bp.route("/status/<job_id>")
def status(job_id: str):
    """Render the status/polling page; poll.js calls /api/result/<job_id>."""
    if get_job(job_id) is None:
        abort(404)
    return render_template("status.html", job_id=job_id)


@upload_bp.route("/result/<job_id>")
def result(job_id: str):
    """Server-rendered result page (navigated to once job is done)."""
    job = get_job(job_id)
    if job is None:
        abort(404)
    if job["status"] != "done":
        return redirect(url_for("upload.status", job_id=job_id))

    data = json.loads(job["result_json"])
    return render_template("result.html", data=data, job_id=job_id)
