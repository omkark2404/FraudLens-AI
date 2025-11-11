# Interview Notes: FraudLens-AI

This document is for personal preparation to confidently discuss the architecture, engineering decisions, and codebase logic during a technical interview.

## 1. Project Overview & Architecture
- **What it is:** A Flask-based web app that asynchronously processes ID documents (Driver's Licenses and Insurance Cards) using PaddleOCR and heuristics-based validation/fraud-detection.
- **Why Flask?** Lightweight, simple routing, easy to serve HTML templates and JSON APIs together, and low overhead. Perfect for an MVP.
- **Why SQLite?** Provides zero-configuration local storage. Safe for light concurrent use via `check_same_thread=False` and single-use connections per request, avoiding locking issues during prototyping.
- **Async Processing:** Done via Python's built-in `threading.Thread(daemon=True)`. *Why?* Prevents the HTTP request from hanging while PaddleOCR runs. *Limitation:* If the app restarts, running threads die. For production, I would use Celery + Redis for reliable queuing.

## 2. OCR Pipeline (Computer Vision)
- **Why PaddleOCR?** It supports angle classification (detects upside-down text) and is highly accurate on structured tables/IDs out-of-the-box compared to Tesseract.
- **Why preprocess before OCR?** OCR struggles with shadows, noise, and tilted scans.
- **The exact pipeline:**
  1. *Resize*: Cap at 2400px to prevent OOM errors and speed up processing.
  2. *Grayscale*: Discard color data to simplify edge detection.
  3. *CLAHE*: Contrast Limited Adaptive Histogram Equalization. Enhances text contrast against complex ID backgrounds.
  4. *Adaptive Thresholding*: Converts image to pure binary (black/white text), handling uneven lighting better than global thresholding.
  5. *Median Blur*: Removes salt-and-pepper noise.
  6. *Deskewing*: Uses Canny Edge Detection and Hough Line Transform to calculate median rotation angle and rotate image straight.

## 3. Extraction Engine
- **How it works:** A 4-stage hybrid approach.
  1. *Document Inference:* Searches the raw aggregated text for keywords like "driver", "dl", "policy" to decide the type.
  2. *Spatial Proximity Matching:* Instead of assuming layout, it finds "anchor" words (e.g., "DOB:") and looks for the nearest bounding box *to the right or below*.
  3. *Global Regex:* A backup step to find dates and license numbers globally if proximity matching fails.
  4. *LLM Fallback (Gemini):* Only triggers if ≥2 critical fields are missing. Saves API costs and latency by treating the LLM strictly as a fallback mechanism, not the primary parser.

## 4. Validation vs. Fraud Detection
- **Validation (0-100 Score):** Checks logical correctness. Are the dates valid? Is it expired? Does the license format match a regex? Is the OCR confidence high?
- **Fraud Detection (Heuristics):** Checks physical layout anomalies.
  - *Inconsistent text sizing:* If bounding box areas have a Coefficient of Variation > 2.5, it flags potential "pasted" text (forgery).
  - *Overlapping text:* Flags if >5 text blocks overlap (tampered layout).
  - *Missing critical fields / Low confidence:* Flags if name/license are entirely missing or if average OCR confidence is < 0.5 (bad scan/manipulation).
  - *Is it Machine Learning?* **No**. It is entirely rule-based/heuristic. (Be honest here, it shows engineering pragmatism!).

## 5. Security & File Uploads
- **File Security:** Uses Werkzeug's `secure_filename()` to prevent Path Traversal attacks (e.g., uploading `../../../etc/passwd`).
- **File Cleanup:** Uploads are immediately cleaned up in a `finally` block in `job_service.py` to prevent disk overflow.
- **Size Limits:** Enforced via Flask's `MAX_CONTENT_LENGTH` (16MB).
- **CORS:** Configured for `*` on `/api/*` to allow cross-origin requests, acceptable for stateless public endpoints relying on unguessable UUIDs for job retrieval.

## 6. Likely Interview Questions & Answers

**Q: Why use Python threading instead of Celery for async tasks?**
*A:* For this MVP, I wanted a self-contained application with zero external infrastructure dependencies. Threading allows background execution without requiring a Redis broker. In a production environment, I would migrate to Celery to ensure task persistence and distributed scaling.

**Q: Is your fraud detection an AI model?**
*A:* No, it uses layout-based heuristics. I compute the variance of OCR bounding box sizes and check for overlapping text geometries. If someone pastes text over an ID, the sizing and spacing anomalies will trigger the threshold. A true ML model would require thousands of annotated fake IDs, which was outside the scope.

**Q: What happens if the Gemini API goes down?**
*A:* The app continues to function. Gemini is strictly a fallback layer in `extraction_service.py`. If it fails, the app catches the exception and returns whatever fields it successfully extracted via spatial proximity and regex.

**Q: How do you handle poor-quality documents?**
*A:* The preprocessing pipeline tries to salvage it using CLAHE and deskewing. If it's still unreadable, PaddleOCR returns low confidence scores. Blocks with <0.6 confidence are filtered out. If critical fields are missing, the validation score drops, and the fraud heuristic flags the document as "Suspicious" due to low confidence.

**Q: How would you scale this to 10,000 requests per minute?**
*A:* 
1. Move the SQLite DB to PostgreSQL.
2. Replace Python `threading` with a Celery worker pool and a message broker like RabbitMQ or Redis.
3. Decouple the web tier from the OCR tier so they scale independently (OCR is CPU/GPU heavy).
4. Store uploaded documents in an S3 bucket instead of the local filesystem.
