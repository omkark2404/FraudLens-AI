"""
services/validation_service.py
Validation scoring (0-100), fraud heuristics, and final verdict engine.
"""
import re
import logging
import datetime
import statistics
from typing import List, Tuple, Dict, Any

from models.schemas import OCRBlock, ExtractedFields, ValidationResult, FinalVerdict
from core.config import config

logger = logging.getLogger(__name__)

_GENERIC_LICENSE_RE = re.compile(r"^[A-Z0-9]{5,15}$")


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

def _parse_date(date_str) -> datetime.date:
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(str(date_str), fmt).date()
        except ValueError:
            continue
    return None

def _is_future_date(date_str) -> bool:
    dt = _parse_date(date_str)
    if dt:
        return dt > datetime.date.today()
    return False

def _is_plausible_name(name: str) -> bool:
    if not name:
        return False
    # Only letters, spaces, hyphens, min 2 tokens, total length between 3 and 100
    if len(name) < 3 or len(name) > 100:
        return False
    tokens = name.split()
    if len(tokens) < 2:
        return False
    for char in name:
        if not (char.isalpha() or char.isspace() or char == '-'):
            return False
    return True

def compute_validation_score(fields: ExtractedFields,
                             blocks: List[OCRBlock],
                             doc_type: str = "license") -> ValidationResult:
    """
    Correctness-based scoring profiles. Max score 100.
    """
    score = 0
    breakdown: dict = {}

    # Name plausibility
    if _is_plausible_name(fields.name):
        pts = 20
        score += pts
        breakdown["name_plausible"] = pts
    else:
        breakdown["name_plausible"] = 0

    dob_dt = _parse_date(fields.dob)
    issue_dt = _parse_date(fields.issue_date)
    exp_dt = _parse_date(fields.expiry_date)

    if doc_type == "license":
        # License specific logic
        # DOB not in future, age >= 16
        if dob_dt and dob_dt <= datetime.date.today():
            age = (datetime.date.today() - dob_dt).days / 365.25
            if age >= 16:
                pts = 15
                score += pts
                breakdown["dob_valid_age"] = pts
            else:
                breakdown["dob_valid_age"] = 0
        else:
            breakdown["dob_valid_age"] = 0

        # Issue > DOB, Expiry > Issue
        if issue_dt and dob_dt and issue_dt > dob_dt:
            pts = 10
            score += pts
            breakdown["issue_after_dob"] = pts
        else:
            breakdown["issue_after_dob"] = 0

        if exp_dt and issue_dt and exp_dt > issue_dt:
            pts = 15
            score += pts
            breakdown["expiry_after_issue"] = pts
        else:
            breakdown["expiry_after_issue"] = 0

        if _is_future_date(fields.expiry_date):
            pts = 15
            score += pts
            breakdown["not_expired"] = pts
        else:
            breakdown["not_expired"] = 0

        if fields.license_number and _GENERIC_LICENSE_RE.match(fields.license_number.upper()):
            pts = 5
            score += pts
            breakdown["license_format_unverified"] = pts
        else:
            breakdown["license_format_unverified"] = 0
    else:
        # Insurance card profile
        # Insurance cards don't strictly require DOB
        pts = 20
        score += pts
        breakdown["insurance_no_dob_penalty_offset"] = pts

        if issue_dt and issue_dt <= datetime.date.today():
            pts = 10
            score += pts
            breakdown["issue_valid"] = pts
        else:
            breakdown["issue_valid"] = 0

        if exp_dt and issue_dt and exp_dt > issue_dt:
            pts = 15
            score += pts
            breakdown["expiry_after_issue"] = pts
        else:
            breakdown["expiry_after_issue"] = 0

        if _is_future_date(fields.expiry_date):
            pts = 15
            score += pts
            breakdown["not_expired"] = pts
        else:
            breakdown["not_expired"] = 0
            
        if fields.policy_number:
            pts = 15
            score += pts
            breakdown["policy_present"] = pts
        else:
            breakdown["policy_present"] = 0

    # OCR confidence
    if blocks:
        avg_conf = sum(b.confidence for b in blocks) / len(blocks)
        if avg_conf >= config.HIGH_CONFIDENCE_THRESHOLD:
            pts = 15 if doc_type == "license" else 20
            score += pts
            breakdown["high_ocr_confidence"] = pts
        else:
            breakdown["high_ocr_confidence"] = 0
        breakdown["avg_ocr_confidence"] = round(avg_conf, 4)
    else:
        breakdown["high_ocr_confidence"] = 0
        breakdown["avg_ocr_confidence"] = 0.0

    final = min(score, 100)
    logger.info("Validation score: %d breakdown: %s", final, breakdown)
    return ValidationResult(score=final, breakdown=breakdown)

# ── Fraud and Quality ─────────────────────────────────────────────────────────

def _box_height(bbox: List[float]) -> float:
    return max(0, bbox[3] - bbox[1])

def _boxes_overlap(b1: List[float], b2: List[float]) -> bool:
    return not (b1[2] <= b2[0] or b2[2] <= b1[0] or
                b1[3] <= b2[1] or b2[3] <= b1[1])

def evaluate_verdict(blocks: List[OCRBlock],
                     fields: ExtractedFields,
                     validation: ValidationResult,
                     doc_type: str = "license") -> FinalVerdict:
    """
    Evaluates fraud vs quality and outputs a FinalVerdict.
    Missing fields and low OCR confidence -> needs_better_image (Quality)
    Geometric anomalies -> needs_review / rejected (Fraud)
    """
    quality_issues = []
    fraud_flags = []
    
    if not blocks:
        quality_issues.append("no OCR content extracted")
    else:
        # Height variance check
        heights = [_box_height(b.bbox) for b in blocks if _box_height(b.bbox) > 0]
        if len(heights) >= 3:
            try:
                stdev = statistics.stdev(heights)
                mean_h = statistics.mean(heights)
                cv = stdev / mean_h if mean_h else 0
                if cv > config.TEXT_SIZE_VARIANCE_THRESHOLD:
                    fraud_flags.append("inconsistent text sizing (high bbox height variance)")
            except statistics.StatisticsError:
                pass

        # Overlap check ignoring low confidence
        high_conf_blocks = [b for b in blocks if b.confidence >= config.OCR_CONFIDENCE_THRESHOLD]
        overlap_count = 0
        for i, b1 in enumerate(high_conf_blocks):
            for b2 in high_conf_blocks[i + 1:]:
                if _boxes_overlap(b1.bbox, b2.bbox):
                    overlap_count += 1
        if overlap_count > config.OVERLAP_THRESHOLD_BOXES:
            fraud_flags.append(f"overlapping text detected ({overlap_count} pairs)")

        avg_conf = sum(b.confidence for b in blocks) / len(blocks)
        if avg_conf < 0.5:
            quality_issues.append(f"low OCR confidence (avg {avg_conf:.2f})")

    missing = []
    if not fields.name:
        missing.append("name")
    if doc_type == "license" and not fields.license_number:
        missing.append("license number")
    if doc_type == "insurance" and not fields.policy_number:
        missing.append("policy number")
        
    if missing:
        quality_issues.append(f"missing critical fields: {', '.join(missing)}")
        
    expired = False
    if fields.expiry_date and not _is_future_date(fields.expiry_date):
        expired = True

    reasons = quality_issues + fraud_flags
    
    # Determine verdict
    if len(fraud_flags) >= config.FRAUD_ANOMALY_THRESHOLD:
        verdict = "rejected"
    elif expired or validation.score < 50:
        verdict = "rejected"
        reasons.append("document is expired or validation score too low")
    elif len(fraud_flags) > 0:
        verdict = "needs_review"
    elif len(quality_issues) > 0:
        verdict = "needs_better_image"
    else:
        verdict = "no_anomalies_detected"

    logger.info("Verdict: %s, Reasons: %s", verdict, reasons)
    return FinalVerdict(verdict=verdict, reasons=reasons)
