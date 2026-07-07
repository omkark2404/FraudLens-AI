# FraudLens AI ⚡ — Intelligent Document Processing System

> FraudLens AI is an intelligent document verification system focused on fraud detection, featuring an AI-powered OCR pipeline for Driver's Licenses and Insurance Cards with **validation scoring**, **fraud detection**, **async job processing**, and a full **REST API**.

---

## 🧠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.9+ · Flask 2.3 |
| OCR Engine | PaddleOCR 2.7 (PaddlePaddle 2.6) |
| Image Processing | OpenCV 4.8 · Pillow 10 |
| PDF Rendering | PyMuPDF (fitz) |
| Database | SQLite (stdlib) — *Note: For production at scale, replace with PostgreSQL* |
| Frontend | Vanilla HTML/CSS/JS (glassmorphism dark UI) |
| Async Jobs | Python `threading` (no Redis required) |
| Config | `python-dotenv` |

---

## 🏗️ Architecture

```text
User ──► UI ──► Flask API ──► Job Thread ──► OCR ──► Extraction ──► Validation ──► DB
                 ▲                 │
                 └─────────────────┘
                   poll /api/result
```

```text
OCRScanner/
├── app.py                   # Entry point (python app.py)
├── .env                     # Environment variables
├── .env.example             # Example environment variables
├── requirements.txt         # Python dependencies
│
├── core/
│   ├── config.py            # Centralised env-based config
│   └── app_factory.py       # Flask application factory
│
├── services/
│   ├── ocr_service.py       # OCR pipeline: preprocess → PaddleOCR → OCRBlocks
│   ├── extraction_service.py # Hybrid extraction: keyword + proximity + regex + optional Gemini LLM fallback
│   ├── job_service.py       # Async job orchestration
│   └── validation_service.py # Validation score (0-100) + fraud detection
│
├── models/
│   ├── database.py          # SQLite CRUD helpers
│   └── schemas.py           # Typed dataclasses (OCRBlock, ExtractedFields, …)
│
├── routes/
│   ├── upload_routes.py     # HTML routes: /, /upload, /status/<id>, /result/<id>
│   └── api_routes.py        # REST API: /api/health, /api/upload, /api/result/<id>, /api/jobs
│
├── static/
│   ├── css/style.css        # Design system (glassmorphism, dark mode)
│   └── js/
│       ├── script.js        # Shared UI (particles, tilt, drag-drop, form)
│       ├── poll.js          # Polling loop for status page
│       └── results.js       # Score circle animations
│
├── templates/
│   ├── index.html           # Upload page
│   ├── status.html          # Async polling/status page
│   └── result.html          # Results: fields + score + fraud + JSON preview
│
└── utils/                   # (Legacy: currently unused)
```

---

## ⚙️ OCR Pipeline

```
Document (image / PDF)
        │
        ▼
  pdf_to_image()         ← PyMuPDF renders PDF @ 200 DPI
        │
        ▼
  preprocess()
    ├─ Resize to max 2400px
    ├─ Grayscale
    ├─ CLAHE contrast enhancement
    ├─ Adaptive threshold (Gaussian)
    ├─ Median blur (noise removal)
    └─ Deskew via Hough transform
        │
        ▼
  PaddleOCR (use_angle_cls=True)
        │
        ▼
  [OCRBlock(text, bbox, confidence), …]
  (blocks below confidence threshold dropped)
```

---

## 🧬 Intelligent Extraction

Hybrid three-stage pipeline:

1. **Keyword anchoring** — scans all OCR blocks for keywords (`NAME`, `DOB`, `DL`, `EXP`, `INSURED`, etc.)
2. **Proximity-based value lookup** — finds the nearest block to the right or below the keyword anchor
3. **Regex fallback** — extracts dates and license number patterns from full text when keyword lookup fails

---

## 🛡️ Validation Score (0–100)

| Criterion | Points |
|---|---|
| Name present | +20 |
| DOB is a valid date | +15 |
| Issue date is a valid date | +15 |
| Expiry date is a valid date | +15 |
| Document not expired | +10 |
| License/policy number valid format | +10 |
| Avg OCR confidence ≥ 0.75 | +15 |

---

## 🕵️ Fraud Detection

Four heuristics analysed per document:

| Check | Trigger |
|---|---|
| Inconsistent text sizing | Bounding-box area coefficient of variation > 2.5 |
| Overlapping text | More than 5 overlapping bounding-box pairs |
| Missing critical fields | Name or license/policy number absent |
| Low OCR confidence | Average confidence < 0.5 |

Result: `"Valid"` or `"Suspicious"` with a list of flagged anomalies.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- `pip`

### Installation

```bash
git clone https://github.com/Hmishra230/OCR_SCANNER.git
cd OCRScanner
pip install -r requirements.txt
cp .env .env.local   # edit values if needed
```

### Run locally

```bash
python app.py
# → http://localhost:5000
```

---

## 📡 REST API

### POST `/api/upload`

Upload two documents and receive a `job_id` for async polling.

**Example cURL Request**:
```bash
curl -X POST http://localhost:5000/api/upload \
  -F "license_file=@dl.jpg" \
  -F "insurance_file=@ic.jpg"
```

**Request** — `multipart/form-data`:
| Field | Type | Required |
|---|---|---|
| `license_file` | file (jpg/png/pdf) | ✅ |
| `insurance_file` | file (jpg/png/pdf) | ✅ |

**Response** `202 Accepted`:
```json
{ "job_id": "a3f2c1d0-...", "status": "pending" }
```

---

### GET `/api/result/<job_id>`

Poll for job result.

**Response while processing** `202`:
```json
{ "status": "processing" }
```

**Response on completion** `200`:
```json
{
  "status": "done",
  "data": {
    "job_id": "a3f2c1d0-...",
    "license": {
      "doc_type": "license",
      "fields": {
        "name": "JOHN A. DOE",
        "dob": "1990-05-14",
        "license_number": "D1234567",
        "issue_date": "2020-01-15",
        "expiry_date": "2026-01-15",
        "expired": false
      },
      "validation": {
        "score": 85,
        "breakdown": {
          "name_present": 20,
          "dob_valid": 15,
          "issue_date_valid": 15,
          "expiry_date_valid": 15,
          "not_expired": 10,
          "license_format_valid": 10,
          "high_ocr_confidence": 0,
          "avg_ocr_confidence": 0.71
        }
      },
      "fraud": {
        "status": "Valid",
        "flags": []
      }
    },
    "insurance": {
      "doc_type": "insurance",
      "fields": {
        "name": "JOHN DOE",
        "dob": null,
        "license_number": "POL-9988771",
        "issue_date": "2024-07-01",
        "expiry_date": "2025-07-01",
        "expired": true
      },
      "validation": {
        "score": 55,
        "breakdown": {
          "name_present": 20,
          "dob_valid": 0,
          "issue_date_valid": 15,
          "expiry_date_valid": 15,
          "not_expired": 0,
          "license_format_valid": 5,
          "high_ocr_confidence": 0,
          "avg_ocr_confidence": 0.68
        }
      },
      "fraud": {
        "status": "Valid",
        "flags": []
      }
    },
    "error": null
  }
}
```

**Response on error** `500`:
```json
{ "status": "error", "error": "OCR engine failed: ..." }
```

---

### GET `/api/jobs`

Returns the 20 most recent jobs.

```json
[
  { "id": "a3f2c1d0-...", "status": "done", "created_at": "2025-04-17 12:00:00" },
  ...
]
```

---

## ☁️ Deployment

### Recommended: VPS or Container Platform
Deploy on robust platforms like **Render**, **Railway**, or **Fly.io** due to PaddleOCR's model size (~800MB) and ML processing times.

> ⚠️ **Note**: Serverless platforms (like Vercel or AWS Lambda) are **not recommended** for this backend due to cold starts, upload size limits, and max execution timeouts (typically 10-30s). 

### Docker / VPS Example

```bash
pip install gunicorn
gunicorn app:app --workers 2 --bind 0.0.0.0:8000
```

---

## 🔬 Why This Is Hard (and how we solved it)

Building an OCR system is deceptively complex. A standard regex script will break instantly in the real world. 

Here are the key challenges this architecture solves:
1. **OCR Noise**: Mobile photos are blurry, rotated, and poorly lit. We fix this via OpenCV using CLAHE contrast enhancement and Hough Transform deskewing.
2. **Spatial Layouts**: Every state and insurance company uses different document layouts. We built a **hybrid extraction engine** that anchors to keywords (like `"DOB:"`) and uses spatial nearest-neighbour proximity checks to find the value, falling back on regex only as a last resort.
3. **Fraud Detection**: Cropped documents or manually edited expiration dates can easily fool simple parsers. Our validation service detects inconsistencies in font sizes (bounding-box CV analysis) and overlapping text blocks to flag tampering automatically.

---

## 🔐 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `change-me-in-production` | Flask session secret |
| `FLASK_DEBUG` | `false` | Enable debug mode |
| `MAX_UPLOAD_MB` | `16` | Max file upload size |
| `DB_NAME` | `ocr_jobs.db` | SQLite database filename |
| `OCR_CONF_THRESHOLD` | `0.6` | Min OCR block confidence |
| `HIGH_CONF_THRESHOLD` | `0.75` | Threshold for score bonus |
| `FRAUD_THRESHOLD` | `2` | Anomalies needed to flag as Suspicious |
| `GEMINI_API_KEY` | (empty) | Optional: Gemini API key for LLM fallback extraction |

---

## 📜 License

MIT License — see `LICENSE` for details.
