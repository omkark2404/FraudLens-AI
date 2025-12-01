# FraudLens-AI

[![Live Demo](https://img.shields.io/badge/Live_Demo-fraudlens--ai.onrender.com-success?style=for-the-badge)](https://fraudlens-ai-6wu4.onrender.com)

FraudLens-AI is a web application that processes uploaded identity and insurance documents to extract structured data, validate their contents, and flag potential anomalies. It uses PaddleOCR for text extraction and applies a rule-based engine to compute validation scores and detect signs of tampering or poor document quality.

## Overview

FraudLens-AI addresses the challenge of manually verifying documents like driver's licenses and insurance cards. Users upload document images or PDFs, which are processed asynchronously. The application extracts key fields (name, dates, license/policy numbers), validates the extracted information to generate a confidence score, and runs heuristic checks to flag suspicious documents. The output is a structured JSON result or a visual report indicating the document's validity and any detected anomalies.

## Key Features

- **Document Processing**: Supports Driver's Licenses and Insurance Cards in JPG, PNG, and PDF formats.
- **Image Preprocessing**: Enhances contrast, removes noise, and deskews images before OCR to improve accuracy.
- **Hybrid Data Extraction**: Uses spatial proximity, regex, and an optional LLM fallback to extract fields from OCR blocks.
- **Validation Scoring**: Computes a 0-100 score based on field presence, date validity, and OCR confidence.
- **Heuristic Fraud Detection**: Flags documents as "Suspicious" based on bounding box variance, overlapping text, missing critical fields, or low OCR confidence.
- **Asynchronous Processing**: Uses background threads to process documents without blocking the main web request.
- **REST API**: Provides endpoints for uploading documents and polling job status.

## How It Works

1. **Document Upload**: Users upload files via the web interface or API.
2. **Async Job Creation**: A job is created in the SQLite database, and processing begins in a background daemon thread.
3. **Image Preprocessing**: Files are resized, converted to grayscale, enhanced with CLAHE, thresholded, denoised, and deskewed.
4. **OCR Extraction**: PaddleOCR extracts text blocks, bounding boxes, and confidence scores.
5. **Field Extraction**: The engine identifies the document type, then extracts fields using keyword proximity, regex, and an optional Gemini LLM fallback if multiple fields are missing.
6. **Validation & Fraud Checks**: The extracted data is scored for validity, and bounding boxes/text are analyzed for fraud heuristics.
7. **Result Delivery**: The job is marked as done, uploaded files are securely deleted, and the user can view the extracted JSON data.

## Architecture

- **Frontend**: HTML/JS templates rendered with Jinja2 (`templates/`, `static/`). Uses polling to check job status.
- **Flask Backend**: Blueprints route web traffic (`upload_routes.py`) and API traffic (`api_routes.py`).
- **Services**: Business logic is separated into single-responsibility modules (`job_service.py`, `ocr_service.py`, `extraction_service.py`, `validation_service.py`).
- **Database**: SQLite stores job states (`pending`, `processing`, `done`, `error`) and final JSON results.
- **Async Workers**: Built-in Python `threading.Thread(daemon=True)` handles long-running OCR tasks in the background.

## OCR Pipeline

The OCR pipeline in `ocr_service.py` is designed to maximize extraction accuracy from varied real-world uploads:
- **PDF Rendering**: PyMuPDF converts PDFs to images.
- **Resizing**: Caps image dimensions to 2400 pixels to optimize OCR speed and memory usage.
- **Preprocessing**: OpenCV applies grayscale conversion, CLAHE contrast enhancement, adaptive Gaussian thresholding, and median blur.
- **Deskewing**: Canny edge detection and Hough line transforms identify and correct image rotation.
- **PaddleOCR**: Extracts text and bounding boxes. Low-confidence blocks (<0.6) are discarded.

## Document / Field Extraction

Field extraction in `extraction_service.py` is primarily rule-based and spatial:
- **Document Detection**: Infers "license" or "insurance" based on the presence of specific keywords in the aggregated text.
- **Keyword + Proximity**: Searches for anchor words (e.g., "DOB", "EXP") and finds the nearest valid text block strictly to the right or below the anchor. Supports multi-line extraction for addresses and names.
- **Global Regex**: Scans the entire text for date formats and license number patterns.
- **LLM Fallback**: If two or more critical fields (name, license, dates) are missing after rules are applied, it falls back to the Gemini API (`gemini-1.5-flash`) passing the raw text to fill in the gaps.

## Validation

The validation engine computes a score out of 100 based on the presence and logical correctness of fields:
- Name present: +20
- DOB valid: +15
- Issue date valid: +15
- Expiry date valid: +15
- Expiry date is in the future: +10
- License/Policy number matches expected format: +10
- Average OCR confidence is high (≥ 0.75): +15

## Fraud / Anomaly Detection

Fraud detection relies on geometric and logical heuristics, **not** a trained machine-learning classifier. A document is flagged as "Suspicious" if 2 or more of the following anomalies are detected:
- **Inconsistent Text Sizing**: High variance (Coefficient of Variation > 2.5) in OCR bounding box areas, suggesting pasted text.
- **Overlapping Text**: More than 5 overlapping bounding boxes, indicating layout tampering.
- **Missing Critical Fields**: The name or license number could not be extracted at all.
- **Low OCR Confidence**: The average confidence of all text blocks is below 0.5.

## Tech Stack

| Category | Technology |
|---|---|
| Backend | Flask, Werkzeug, Gunicorn |
| OCR | PaddleOCR, PaddlePaddle |
| Image Processing | OpenCV (cv2), Pillow, Numpy |
| PDF Processing | PyMuPDF (fitz) |
| Database | SQLite |
| Async Processing | Python `threading` |
| LLM Fallback | Google Generative AI (Gemini) |

## Project Structure

```text
FraudLens-AI/
├── app.py                     # Application entry point
├── core/
│   ├── app_factory.py         # Flask app initialization
│   └── config.py              # Configuration and environment variables
├── models/
│   ├── database.py            # SQLite CRUD operations
│   └── schemas.py             # Data structures and type hints
├── routes/
│   ├── api_routes.py          # JSON API endpoints
│   └── upload_routes.py       # HTML template endpoints
├── services/
│   ├── extraction_service.py  # Regex, spatial, and LLM extraction logic
│   ├── job_service.py         # Async job orchestrator
│   ├── ocr_service.py         # Image preprocessing and PaddleOCR
│   └── validation_service.py  # Scoring and fraud heuristics
├── templates/                 # Jinja2 HTML templates
├── static/                    # CSS, JS, and static assets
├── requirements.txt           # Python dependencies
└── .env.example               # Example environment variables
```

## API Reference

### Upload Documents
- **Endpoint**: `POST /api/upload`
- **Purpose**: Submits documents for processing and starts a background job.
- **Request**: `multipart/form-data` containing `license_file` and `insurance_file`.
- **Response**: `202 Accepted`
```json
{
  "job_id": "uuid-string",
  "status": "pending"
}
```

### Get Job Result
- **Endpoint**: `GET /api/result/<job_id>`
- **Purpose**: Polls for job completion and retrieves the final extracted data.
- **Response (Processing)**: `202 Accepted`
```json
{
  "status": "processing"
}
```
- **Response (Done)**: `200 OK`
```json
{
  "status": "done",
  "data": {
    "license": { ... },
    "insurance": { ... }
  }
}
```

### List Recent Jobs
- **Endpoint**: `GET /api/jobs`
- **Purpose**: Returns the 20 most recent jobs.
- **Response**: `200 OK`
```json
[
  {
    "id": "uuid-string",
    "status": "done",
    "created_at": "YYYY-MM-DD HH:MM:SS"
  }
]
```

## Installation & Local Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/omkark2404/FraudLens-AI.git
   cd FraudLens-AI
   ```

2. **Create and activate a virtual environment** (recommended):
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   Copy `.env.example` to `.env` and adjust the values as needed.
   ```bash
   # On macOS/Linux:
   cp .env.example .env
   # On Windows:
   copy .env.example .env
   ```

5. **Start the application**:
   ```bash
   python app.py
   ```
   The application will be available locally at `http://localhost:5000`.

## Environment Variables

Configure these in your `.env` file based on `.env.example`:

- `SECRET_KEY`: Random string for Flask sessions (Required).
- `FLASK_DEBUG`: Enables Flask debug mode if set to `true`.
- `MAX_UPLOAD_MB`: Maximum file upload size in megabytes.
- `DB_NAME`: Filename for the SQLite database.
- `OCR_CONF_THRESHOLD`: Minimum confidence (0.0 - 1.0) for accepting PaddleOCR blocks.
- `HIGH_CONF_THRESHOLD`: Threshold for earning the high-confidence validation bonus.
- `FRAUD_THRESHOLD`: Number of anomalies required to flag a document as suspicious.
- `GEMINI_API_KEY`: API key for Gemini LLM fallback (Optional).

## Database

FraudLens-AI currently uses **SQLite** for data persistence (`models/database.py`).
- **Why SQLite**: It allows for a zero-configuration local setup, making it easy to run and test the application without spinning up a separate database server.
- **Data Stored**: A single `jobs` table tracks the `job_id`, `status` (pending, processing, done, error), timestamps, and a `result_json` column storing the final processed output.
- **Concurrency**: Thread safety is managed by explicitly opening a new database connection per call (`check_same_thread=False`).

## Async Processing

Document OCR is computationally intensive. To prevent the web server from blocking during document uploads:
- **What is asynchronous**: The entire document pipeline (OCR, extraction, validation) runs asynchronously in `services/job_service.py`.
- **How it works**: The backend responds immediately to the upload request with a `job_id` and `status=pending`. A background thread (`threading.Thread`) is spawned to handle the heavy lifting.
- **Job Status**: The frontend uses Javascript to poll the `/api/result/<job_id>` endpoint until the background thread marks the job as `done` or `error` in the SQLite database.

## Limitations

- **Heuristic-Based Fraud**: Fraud detection relies on layout heuristics (e.g., bounding box variance). It is not a trained ML classification model and cannot detect deepfakes or sophisticated pixel-level tampering.
- **OCR Dependency**: The accuracy of field extraction is heavily dependent on the quality of the uploaded image and the capabilities of PaddleOCR.
- **Thread Scaling**: Using Python's built-in `threading` works for small-scale deployments but is not suitable for high-traffic production environments, as it lacks task persistence, queuing, and distributed worker capabilities.
- **Database Scaling**: SQLite is sufficient for development and light usage but will encounter concurrency limitations under heavy concurrent writes.

## Future Improvements

- **Production Task Queue**: Migrate async processing from built-in threads to Celery with a Redis broker for scalable, distributed job processing.
- **PostgreSQL Migration**: Replace SQLite with PostgreSQL to handle concurrent database operations reliably in a production environment.
- **Advanced Tampering Detection**: Integrate computer vision models trained specifically to detect digital forgery, metadata manipulation, or inconsistent EXIF data.
- **More Document Templates**: Expand the rule-based extraction to reliably support passports, ID cards from various countries, and specialized insurance forms.
