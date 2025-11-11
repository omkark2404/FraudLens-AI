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

    Args:
        file_path: Absolute path to image or PDF.
        doc_type:  "license" | "insurance"

    Returns:
        Populated DocumentResult with fields, validation, and fraud.
    """
    # 1. OCR
    blocks = ocr_service.process_document(file_path)

    # 2. Hybrid extraction (with per-field confidence)
    if doc_type == "license":
        fields = extraction_service.extract_license_fields(blocks)
    else:
        fields = extraction_service.extract_insurance_fields(blocks)

    # 3. Validation score
    validation = validation_service.compute_validation_score(fields, blocks)

    # 4. Fraud detection
    fraud = validation_service.detect_fraud(blocks, fields)

    return DocumentResult(
        doc_type=doc_type,
        fields=fields,
        validation=validation,
        fraud=fraud,
        raw_blocks=[
            {"text": b.text, "confidence": b.confidence}
            for b in blocks
        ],
    )


def _cleanup_files(*paths: str) -> None:
    """Silently remove uploaded files after processing."""
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug("Cleaned up file: %s", path)
        except OSError as exc:
            logger.warning("Could not delete file %s: %s", path, exc)


def process_job(job_id: str, dl_path: str, ic_path: str) -> None:
    """
    Full async job runner — call this inside a daemon thread.

    Flow:
        pending → processing → done | error
        Files are deleted in the finally block regardless of outcome.

    Args:
        job_id:  UUID string matching the jobs table.
        dl_path: Absolute path to Driver's License file.
        ic_path: Absolute path to Insurance Card file.
    """
    try:
        logger.info("Job %s starting", job_id)
        update_job_status(job_id, "processing")

        license_result  = _process_one_document(dl_path, "license")
        insurance_result = _process_one_document(ic_path, "insurance")

        job = JobResult(
            job_id=job_id,
            status="done",
            license=license_result,
            insurance=insurance_result,
        )
        save_job_result(job_id, job.to_json())
        logger.info("Job %s completed successfully", job_id)

    except Exception as exc:
        logger.error("Job %s failed: %s", job_id, exc, exc_info=True)
        save_job_error(job_id, str(exc))

    finally:
        # Always clean up uploaded files to prevent disk accumulation
        _cleanup_files(dl_path, ic_path)
