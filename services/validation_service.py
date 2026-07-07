"""
services/validation_service.py
Validation scoring (0-100) and fraud detection engine.
"""
import re
import logging
import datetime
import statistics
from typing import List, Tuple

from models.schemas import OCRBlock, ExtractedFields, ValidationResult, FraudResult
from core.config import config

logger = logging.getLogger(__name__)

# ── Validation ────────────────────────────────────────────────────────────────

_LICENSE_RE = re.compile(r"^[A-Z0-9]{5,12}$")


def _valid_date_str(date_str) -> bool:
    if not date_str:
        return False
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            datetime.datetime.strptime(str(date_str), fmt)
            return True
        except ValueError:
            continue
    return False


def _is_future_date(date_str) -> bool:
    if not date_str:
        return False
    try:
        dt = datetime.datetime.strptime(str(date_str), "%Y-%m-%d").date()
        return dt > datetime.date.today()
    except ValueError:
        return False


def compute_validation_score(fields: ExtractedFields,
                             blocks: List[OCRBlock]) -> ValidationResult:
    """
    Score breakdown (max 100):
      + 20  name present
      + 15  DOB is a valid date
      + 15  issue_date is a valid date
      + 15  expiry_date is a valid date
      + 10  expiry_date is in the future (not expired)
      + 10  license_number matches pattern
      + 15  average OCR confidence ≥ HIGH_CONFIDENCE_THRESHOLD
    """
    score = 0
    breakdown: dict = {}

    # Name
    if fields.name:
        pts = 20
        score += pts
        breakdown["name_present"] = pts
    else:
        breakdown["name_present"] = 0

    # DOB
    if _valid_date_str(fields.dob):
        pts = 15
        score += pts
        breakdown["dob_valid"] = pts
    else:
        breakdown["dob_valid"] = 0

    # Issue date
    if _valid_date_str(fields.issue_date):
        pts = 15
        score += pts
        breakdown["issue_date_valid"] = pts
    else:
        breakdown["issue_date_valid"] = 0

    # Expiry date
    if _valid_date_str(fields.expiry_date):
        pts = 15
        score += pts
        breakdown["expiry_date_valid"] = pts
    else:
        breakdown["expiry_date_valid"] = 0

    # Not expired
    if _is_future_date(fields.expiry_date):
        pts = 10
        score += pts
        breakdown["not_expired"] = pts
    else:
        breakdown["not_expired"] = 0

    # License / policy number format
    if fields.license_number and _LICENSE_RE.match(fields.license_number.upper()):
        pts = 10
        score += pts
        breakdown["license_format_valid"] = pts
    else:
        breakdown["license_format_valid"] = 0

    # OCR confidence
    if blocks:
        avg_conf = sum(b.confidence for b in blocks) / len(blocks)
        if avg_conf >= config.HIGH_CONFIDENCE_THRESHOLD:
            pts = 15
            score += pts
            breakdown["high_ocr_confidence"] = pts
        else:
            breakdown["high_ocr_confidence"] = 0
        breakdown["avg_ocr_confidence"] = round(avg_conf, 4)
    else:
        breakdown["high_ocr_confidence"] = 0
        breakdown["avg_ocr_confidence"] = 0.0

    final = min(score, 100)
    logger.info("Validation score: %d  breakdown: %s", final, breakdown)
    return ValidationResult(score=final, breakdown=breakdown)


# ── Fraud Detection ───────────────────────────────────────────────────────────

def _box_area(bbox: List[float]) -> float:
    return max(0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))


def _boxes_overlap(b1: List[float], b2: List[float]) -> bool:
    return not (b1[2] <= b2[0] or b2[2] <= b1[0] or
                b1[3] <= b2[1] or b2[3] <= b1[1])


def detect_fraud(blocks: List[OCRBlock],
                 fields: ExtractedFields) -> FraudResult:
    """
    Fraud heuristics:
      1. High variance in bounding-box sizes  → inconsistent text sizing
      2. Overlapping text boxes               → tampered layout
      3. Missing critical fields              → suspicious document
      4. Low average OCR confidence           → poor scan quality / manipulation
    """
    anomalies: List[str] = []

    if not blocks:
        anomalies.append("no OCR content extracted")
        return FraudResult(status="Suspicious", flags=anomalies)

    # 1. Bounding-box size variance
    areas = [_box_area(b.bbox) for b in blocks if _box_area(b.bbox) > 0]
    if len(areas) >= 3:
        try:
            stdev = statistics.stdev(areas)
            mean_area = statistics.mean(areas)
            cv = stdev / mean_area if mean_area else 0   # coefficient of variation
            logger.debug("BBox size CV: %.3f", cv)
            if cv > 2.5:
                anomalies.append("inconsistent text sizing (high bbox variance)")
        except statistics.StatisticsError:
            pass

    # 2. Overlapping boxes
    overlap_count = 0
    for i, b1 in enumerate(blocks):
        for b2 in blocks[i + 1:]:
            if _boxes_overlap(b1.bbox, b2.bbox):
                overlap_count += 1
    if overlap_count > 5:
        anomalies.append(f"overlapping text detected ({overlap_count} pairs)")

    # 3. Missing critical fields
    missing = []
    if not fields.name:
        missing.append("name")
    if not fields.license_number:
        missing.append("license/policy number")
    if missing:
        anomalies.append(f"missing critical fields: {', '.join(missing)}")

    # 4. Low OCR confidence
    avg_conf = sum(b.confidence for b in blocks) / len(blocks)
    logger.debug("Avg OCR confidence: %.3f", avg_conf)
    if avg_conf < 0.5:
        anomalies.append(f"low OCR confidence (avg {avg_conf:.2f})")

    verdict = "Suspicious" if len(anomalies) >= config.FRAUD_ANOMALY_THRESHOLD else "Valid"
    logger.info("Fraud detection: %s  flags: %s", verdict, anomalies)
    return FraudResult(status=verdict, flags=anomalies)
