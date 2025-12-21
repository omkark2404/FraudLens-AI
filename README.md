# FraudLens-AI

FraudLens-AI is a web application that processes uploaded identity and insurance documents to extract structured data, validate their contents, and flag potential anomalies. It uses PaddleOCR for text extraction and applies a rule-based engine to compute validation scores and detect signs of tampering or poor document quality.

## Overview

FraudLens-AI addresses the challenge of manually verifying documents like driver's licenses and insurance cards. Users upload document images or PDFs, which are processed asynchronously. The application extracts key fields, validates the extracted information to generate a confidence score, and runs heuristic checks to flag suspicious documents.

## Key Features

- **Document Processing**: Supports Driver's Licenses and Insurance Cards in JPG, PNG, and PDF formats.
- **Image Preprocessing**: Enhances contrast, removes noise, and deskews images before OCR to improve accuracy.
- **Hybrid Data Extraction**: Uses spatial proximity, regex, and an optional LLM fallback to extract fields.
- **Validation Scoring**: Computes a 0-100 score based on field presence, date validity, and OCR confidence.
- **Heuristic Fraud Detection**: Flags documents for bounding box variance, overlapping text, or missing critical fields.
- **Asynchronous Processing**: Uses a bounded `ThreadPoolExecutor` and SQLite with Write-Ahead Logging (WAL) to process documents without blocking the main web request.
- **REST API**: Provides endpoints for uploading documents and polling job status, secured by API key authentication.
- **Strict Security**: Validates uploaded files using magic-byte inspection (not just extensions/mime types) to ensure safety.

## Privacy & Security

**Privacy Statement**: FraudLens-AI processes Personally Identifiable Information (PII) including names, dates of birth, and driver's license numbers. 
- **No Data Retention**: Uploaded files are strictly transient. They are deleted from the local disk immediately after processing, regardless of success or failure.
- **No Training**: We do not use any submitted documents or PII to train machine learning models.
- **Third-Party Services**: If the optional Gemini LLM fallback is enabled, data is sent to Google's API for extraction processing. It is recommended to configure enterprise data-privacy controls on your Google Cloud project if using this feature.

## Architecture & Tech Stack

| Category | Technology |
|---|---|
| Backend | Flask, Werkzeug, Gunicorn |
| OCR | PaddleOCR, PaddlePaddle |
| Image Processing | OpenCV (cv2), Pillow, Numpy |
| PDF Processing | pypdfium2 (AGPL/MIT compliant) |
| Database | SQLite (WAL mode) |
| Async Processing | Python `concurrent.futures.ThreadPoolExecutor` |
| LLM Fallback | Google Generative AI (Gemini) |

## Quality vs. Fraud

FraudLens-AI categorizes issues cleanly into a `FinalVerdict`:

1. **Quality Issues (`needs_better_image`)**: Triggered when the average OCR confidence is too low or critical fields could not be extracted due to blur, glare, or poor lighting. 
2. **Fraud Anomalies (`rejected` / `needs_review`)**: Triggered when the system detects active tampering (e.g., overlapping text blocks, abnormal font-size variance indicating pasted text) or logical inconsistencies (e.g., the document is expired, issue date > expiry date).

## Validation Scoring Rules

The system awards points up to 100 based on the logical correctness and presence of fields. 

| Check | Driver's License | Auto Insurance |
|---|---|---|
| Name Extracted | +20 pts | +20 pts |
| Age >= 16 (Calculated from DOB) | +15 pts | N/A (DOB not required) |
| Issue Date > DOB | +10 pts | N/A |
| Expiry Date > Issue Date | +15 pts | +15 pts (Effective vs Expiry) |
| Expiry Date is in the Future | +15 pts | +15 pts |
| High Avg OCR Confidence (>= 75%) | +15 pts | +15 pts |
| Format Check (License/Policy No) | +10 pts (Generic format = 5 pts) | +10 pts |

*Note: If the score drops below 50, the document is automatically rejected.*

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
   Set `API_KEY` to secure the API. 
   Set `GEMINI_ENABLED=true` and `GEMINI_API_KEY` to use the fallback extraction engine.

5. **Start the application**:
   ```bash
   python app.py
   ```
   The application will be available locally at `http://localhost:5000`.

## Evaluation & Synthetic Documents

We provide scripts to generate synthetic driver's licenses and insurance cards, and to run an automated evaluation of the pipeline's extraction and fraud detection capabilities.

1. **Generate Synthetic Data**:
   ```bash
   python scripts/generate_synthetic_docs.py
   ```
   This generates 20 images (10 valid, 10 fraudulent/poor quality) in the `fixtures/synthetic/` directory.

2. **Run Evaluation**:
   ```bash
   python scripts/evaluate.py
   ```
   This will process all fixtures and output a precision, recall, and accuracy report directly to `docs/EVALUATION.md`.

## License

This project is licensed under the MIT License.
