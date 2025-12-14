"""
services/job_service.py
Centralised async job processor.

Single source of truth for OCR → extraction → validation → fraud pipeline.
Imported by both routes/upload_routes.py and routes/api_routes.py so
the logic is never duplicated.

Post-processing: uploaded files are deleted after work completes (success or failure).
"""
import os
import logging

from models.database import update_job_status, save_job_result, save_job_error
from models.schemas import DocumentResult, JobResult
from services import ocr_service, extraction_service, validation_service

logger = logging.getLogger(__name__)


def _process_one_document(file_path: str, doc_type: str) -> DocumentResult:
    """
    Run the full pipeline for a single document file.
    """
    if not file_path or not os.path.exists(file_path):
        return None

    # 1. OCR
    blocks = ocr_service.process_document(file_path)

    # 2. Hybrid extraction (with per-field confidence)
    if doc_type == "license":
        fields = extraction_service.extract_license_fields(blocks)
    else:
        fields = extraction_service.extract_insurance_fields(blocks)

    # 3. Validation score
    validation = validation_service.compute_validation_score(fields, blocks, doc_type=doc_type)

    # 4. Fraud and Quality detection -> Verdict
    verdict = validation_service.evaluate_verdict(blocks, fields, validation, doc_type=doc_type)

    import datetime
    evaluated_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return DocumentResult(
        doc_type=doc_type,
        evaluated_at=evaluated_at,
        expired=validation_service._is_future_date(fields.expiry_date) is False if fields.expiry_date else False,
        fields=fields,
        validation=validation,
        verdict=verdict,
        raw_blocks=[
            {"text": b.text, "confidence": b.confidence}
            for b in blocks
        ],
    )


def _cleanup_files(*paths: str) -> None:
    """Silently remove uploaded files after processing."""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
                logger.debug("Cleaned up file: %s", path)
        except OSError as exc:
            logger.warning("Could not delete file %s: %s", path, exc)


def _cross_check(dl: DocumentResult, ic: DocumentResult) -> dict:
    if not dl or not ic:
        return None
    import difflib
    cross_check = {}
    dl_name = dl.fields.name or ""
    ic_name = ic.fields.name or ""
    
    if dl_name and ic_name:
        ratio = difflib.SequenceMatcher(None, dl_name.upper(), ic_name.upper()).ratio()
        cross_check["name_match_ratio"] = round(ratio, 2)
        cross_check["name_match"] = ratio > 0.8
    else:
        cross_check["name_match"] = None

    dl_dob = dl.fields.dob
    ic_dob = ic.fields.dob
    
    if dl_dob and ic_dob:
        cross_check["dob_match"] = dl_dob == ic_dob
    else:
        cross_check["dob_match"] = None
        
    return cross_check

def process_job(job_id: str, dl_path: str, ic_path: str) -> None:
    """
    Full async job runner.
    """
    try:
        logger.info("Job %s starting", job_id)
        update_job_status(job_id, "processing")

        license_result  = _process_one_document(dl_path, "license") if dl_path else None
        insurance_result = _process_one_document(ic_path, "insurance") if ic_path else None

        job = JobResult(
            job_id=job_id,
            status="done",
            license=license_result,
            insurance=insurance_result,
            cross_check=_cross_check(license_result, insurance_result)
        )
        save_job_result(job_id, job.to_json())
        logger.info("Job %s completed successfully", job_id)

    except Exception as exc:
        logger.error("Job %s failed: %s", job_id, exc, exc_info=True)
        save_job_error(job_id, str(exc))

    finally:
        # Always clean up uploaded files to prevent disk accumulation
        _cleanup_files(dl_path, ic_path)

import concurrent.futures

# Global ThreadPoolExecutor for jobs
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

def submit_job(job_id: str, dl_path: str, ic_path: str):
    """Submit a job to the ThreadPoolExecutor."""
    _executor.submit(process_job, job_id, dl_path, ic_path)

def cleanup_stale_jobs():
    """Mark jobs stuck in processing state as error on startup."""
    from models.database import _get_conn
    try:
        with _get_conn() as conn:
            conn.execute("UPDATE jobs SET status = 'error', result_json = '{\"error\": \"Job interrupted by server restart\"}' WHERE status = 'processing'")
            conn.commit()
            logger.info("Cleaned up stale processing jobs.")
    except Exception as e:
        logger.error(f"Failed to clean up stale jobs: {e}")
