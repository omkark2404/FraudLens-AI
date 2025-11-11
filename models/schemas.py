"""
models/schemas.py
Data schemas (dataclasses) used across the application.
All date fields are stored as ISO-format strings for easy JSON serialisation.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json


@dataclass
class OCRBlock:
    """Raw OCR output block."""
    text: str
    bbox: List[float]          # [x1, y1, x2, y2]
    confidence: float


@dataclass
class ExtractedFields:
    """Structured extraction result for one document."""
    name: Optional[str] = None
    dob: Optional[str] = None
    license_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    expired: Optional[bool] = None
    # Per-field OCR confidence (0.0–1.0, None = extracted via regex / not available)
    field_confidence: dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Validation scoring output."""
    score: int = 0                      # 0-100
    breakdown: dict = field(default_factory=dict)


@dataclass
class FraudResult:
    """Fraud detection output."""
    status: str = "Valid"               # "Valid" | "Suspicious"
    flags: List[str] = field(default_factory=list)


@dataclass
class DocumentResult:
    """Complete result for a single document (license or insurance)."""
    doc_type: str = ""                  # "license" | "insurance"
    fields: ExtractedFields = field(default_factory=ExtractedFields)
    validation: ValidationResult = field(default_factory=ValidationResult)
    fraud: FraudResult = field(default_factory=FraudResult)
    raw_blocks: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        from core.config import config
        res = {
            "doc_type": self.doc_type,
            "fields": asdict(self.fields),
            "validation": asdict(self.validation),
            "fraud": asdict(self.fraud),
        }
        if config.DEBUG:
            res["raw_blocks"] = self.raw_blocks
        return res


@dataclass
class JobResult:
    """Full job result persisted in SQLite."""
    job_id: str = ""
    status: str = "pending"             # pending | processing | done | error
    license: Optional[DocumentResult] = None
    insurance: Optional[DocumentResult] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "license": self.license.to_dict() if self.license else None,
            "insurance": self.insurance.to_dict() if self.insurance else None,
            "error": self.error,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
