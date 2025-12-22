# Interview Notes

## Technical Approach
- Replaced the brittle and unmaintainable PyMuPDF implementation with a robust pipeline using `pypdfium2` (for MIT/AGPL compliance) and PaddleOCR for robust text extraction.
- Migrated out of `threading.Thread` to a `concurrent.futures.ThreadPoolExecutor` for bounded concurrency control.
- Decoupled fraud from quality errors. Fraud is now flagged for geometric discrepancies (overlapping bounding boxes or text size variance), while quality errors are flagged when OCR confidence is low or required fields are unreadable.
- The rule engine now awards a correctness score out of 100 based strictly on logically coherent document components (e.g. issue_date > DOB, expiry_date > issue_date).

## Compromises & Trade-offs
- Used synchronous PaddleOCR calls bounded within a ThreadPoolExecutor. A true production system would migrate to a distributed task queue (like Celery + Redis).
- SQLite is restricted by disk I/O, though WAL mode mitigates this significantly for this scope. Postgres would be needed for a production deployment.
- Gemini fallback relies on prompt engineering and JSON schema mode to prevent injection, but native structured OCR is preferred to avoid hallucination entirely.

## Future Recommendations
- Implement a true task queue (Celery, RabbitMQ/Redis).
- Replace SQLite with PostgreSQL for reliable concurrency at scale.
- Introduce `zxing-cpp` or similar robust barcode decoding library to extract the PDF417 format on the back of driver's licenses and use it to cross-validate the front.
- Implement computer vision models trained specifically to detect tampering artifacts or manipulated EXIF metadata.
