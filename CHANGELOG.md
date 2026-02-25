# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - Initial Release

### Added
- **Core Processing Pipeline**: Full extraction and validation logic for parsing Driver's Licenses and Auto Insurance Cards via PaddleOCR.
- **REST API**: Robust API endpoints (`/api/v1/upload` and `/api/v1/result`) protected via `X-API-Key` authentication.
- **Asynchronous Job Runner**: Replaced blocking operations with a bounded `ThreadPoolExecutor` and SQLite Write-Ahead Logging (WAL) for safe multi-threaded concurrency.
- **Fraud Detection Engine**: New heuristic checks for bounding-box height variance, text overlapping anomalies, and strict date validation (e.g., Expiry > Issue Date).
- **Synthetic Data & Evaluation**: Added `scripts/generate_synthetic_docs.py` to produce test fixtures and `scripts/evaluate.py` to benchmark OCR and validation accuracy.
- **Security Enhancements**: Magic-byte inspection added to prevent malicious file uploads that bypass standard MIME type checks.

### Changed
- Refactored OCR fallback engine to track field provenance (`ocr` vs `llm`).
- Replaced `PyMuPDF` with `pypdfium2` to comply with open-source licensing constraints.
- Updated database to use WAL mode, significantly reducing lock contention errors on high-throughput asynchronous writes.

### Fixed
- Stabilized OCR text coordinate mapping which previously falsely flagged legitimate close-proximity text blocks as fraudulent overlaps.
- Handled naive datetime comparisons by ensuring all timezone and format rules are consistently evaluated in UTC.
