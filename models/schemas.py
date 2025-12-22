"""
models/schemas.py
Data schemas (dataclasses) used across the application.
All date fields are stored as ISO-format strings for easy JSON serialisation.
"""

import json
from dataclasses import asdict, dataclass, field


@dataclass
class OCRBlock:
    """Raw OCR output block."""

    text: str
    bbox: list[float]  # [x1, y1, x2, y2]
    confidence: float


@dataclass
class ExtractedFields:
    """Structured extraction result for one document."""

    name: str | None = None
    dob: str | None = None
    license_number: str | None = None
    policy_number: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    # Per-field OCR confidence (0.0–1.0, None = extracted via regex / not available)
    field_confidence: dict = field(default_factory=dict)
    # Field sources: 'ocr' or 'llm'
    field_sources: dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Validation scoring output."""

    score: int = 0  # 0-100
    breakdown: dict = field(default_factory=dict)


@dataclass
class FinalVerdict:
    """Final verdict combining validation, fraud, and quality."""

    verdict: str = "needs_review"  # "no_anomalies_detected" | "needs_review" | "rejected" | "needs_better_image"
    reasons: list[str] = field(default_factory=list)


@dataclass
class DocumentResult:
    """Complete result for a single document (license or insurance)."""

    doc_type: str = ""  # "license" | "insurance"
    evaluated_at: str = ""  # UTC ISO-8601
    expired: bool = False
    fields: ExtractedFields = field(default_factory=ExtractedFields)
    validation: ValidationResult = field(default_factory=ValidationResult)
    verdict: FinalVerdict = field(default_factory=FinalVerdict)
    raw_blocks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        from core.config import config

        res = {
            "doc_type": self.doc_type,
            "evaluated_at": self.evaluated_at,
            "expired": self.expired,
            "fields": asdict(self.fields),
            "validation": asdict(self.validation),
            "verdict": asdict(self.verdict),
        }
        if config.DEBUG:
            res["raw_blocks"] = self.raw_blocks
        return res


@dataclass
class JobResult:
    """Full job result persisted in SQLite."""

    job_id: str = ""
    status: str = "pending"  # pending | processing | done | error
    license: DocumentResult | None = None
    insurance: DocumentResult | None = None
    cross_check: dict | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "license": self.license.to_dict() if self.license else None,
            "insurance": self.insurance.to_dict() if self.insurance else None,
            "cross_check": self.cross_check,
            "error": self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
