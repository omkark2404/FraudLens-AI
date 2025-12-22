# Changes Manifest

This document maps all original project requirements and feedback to their corresponding fixes in the codebase.

## FIXED
- **Phase 1 (Repo Hygiene)**: Dockerized the app, replaced PyMuPDF with `pypdfium2` (MIT/AGPL fix), added `.gitignore`, pinned requirements, and enforced CI (ruff, mypy, pytest) via GitHub Actions and Pre-commit.
- **Phase 2 (Fraud Logic)**: Replaced boolean `Valid`/`Suspicious` with a `FinalVerdict` schema that segregates Fraud (`rejected`, `needs_review`) from Quality (`needs_better_image`).
- **Phase 2 (Scoring Rules)**: Refactored `validation_service.py` to award points based on correctness (age >= 16, expiry > issue date) instead of simple field presence. Added distinct scoring profiles for licenses vs. insurance cards.
- **Phase 2 (Geometric Analytics)**: Fraud checks now use bounding-box heights (not area) to measure variance, and overlapping bounding box detection correctly handles false positives.
- **Phase 2 (Field Provenance)**: Separated `license_number` from `policy_number`. Added `field_sources` dictionary to explicitly log whether a field was extracted via `ocr` or `llm`.
- **Phase 2 (Cross Check)**: Uploading both a License and Insurance Card triggers an explicit name and DOB cross-check.
- **Phase 3 (Architecture)**: Replaced `threading.Thread` with a bounded `ThreadPoolExecutor`. Added a startup hook to mark stale `processing` jobs as `error`.
- **Phase 3 (Database)**: Enabled WAL mode on SQLite to prevent "database is locked" concurrency errors.
- **Phase 3 (API Hardening)**: Enabled file magic-byte validation (bypassing simple MIME headers) and added an `API_KEY` header for programmatic access. Fixed HTTP response codes (422 for bad input, 400 for upload errors).
- **Phase 5 (Evidence)**: Authored `scripts/generate_synthetic_docs.py` to generate 20 fixtures and `scripts/evaluate.py` to output a Precision/Recall/Accuracy benchmark report to `docs/EVALUATION.md`.
- **Phase 6 (README)**: Completely rewrote the `README.md` to be accurate, sober, and reflect the actual capabilities and rule tables of the system without inventing metrics.
- **Phase 7 (Quality)**: Achieved 100% green builds on `ruff` linting, `mypy` strict typing, and `pytest`.

## MANUAL (Deferred)
- **PDF417 Barcode Decoding**: Decoding the PDF417 format on the back of driver's licenses was pushed to `MANUAL_TODO.md` because installing `zxing-cpp` natively across environments is non-trivial for this prototype.

## PARTIAL
- N/A - All other issues were fully resolved.
