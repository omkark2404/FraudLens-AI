"""
services/ocr_service.py
Full OCR pipeline:
  preprocess → PaddleOCR → structured OCR blocks with confidence scores
"""
import logging
import math
from typing import List, Optional

import cv2
import numpy as np
from PIL import Image
import fitz  # PyMuPDF

from models.schemas import OCRBlock
from core.config import config

logger = logging.getLogger(__name__)

# Lazy-load PaddleOCR to avoid slow import at module level
_ocr_engine = None


def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="en")
        logger.info("PaddleOCR engine initialised")
    return _ocr_engine


# ── Image pre-processing ───────────────────────────────────────────────────────

def _to_numpy(image: Image.Image) -> np.ndarray:
    """Convert PIL Image to BGR numpy array."""
    rgb = np.array(image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _deskew(image: np.ndarray) -> np.ndarray:
    """Correct image skew using Hough line transform."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, math.pi / 180, threshold=80,
                            minLineLength=80, maxLineGap=10)
    if lines is None:
        return image

    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 - x1 != 0:
            angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            if abs(angle) < 30:           # ignore near-vertical lines
                angles.append(angle)

    if not angles:
        return image

    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.5:         # already straight enough
        return image

    h, w = image.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), median_angle, 1.0)
    deskewed = cv2.warpAffine(image, M, (w, h),
                              flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    logger.debug("Deskewed by %.2f°", median_angle)
    return deskewed


def preprocess(image: Image.Image) -> np.ndarray:
    """
    Full preprocessing pipeline:
      resize → grayscale → CLAHE → adaptive threshold → median blur → deskew
    Returns a numpy BGR array ready for PaddleOCR.
    """
    # 1. Cap resolution
    max_dim = 2400
    w, h = image.size
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        image = image.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    bgr = _to_numpy(image)

    # 2. Grayscale
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # 3. CLAHE contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 4. Adaptive threshold
    thresh = cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 15, 8
    )

    # 5. Reduce noise
    denoised = cv2.medianBlur(thresh, 3)

    # 6. Convert back to BGR (PaddleOCR expects colour image)
    bgr_out = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)

    # 7. Deskew
    bgr_out = _deskew(bgr_out)

    return bgr_out


# ── PDF handling ───────────────────────────────────────────────────────────────

def pdf_to_image(pdf_path: str, page_index: int = 0, dpi: int = 200) -> Image.Image:
    """Render a PDF page to a PIL Image at the specified DPI."""
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_index)
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img


# ── OCR extraction ─────────────────────────────────────────────────────────────

def extract_text(processed_image: np.ndarray) -> List[OCRBlock]:
    """
    Run PaddleOCR on a preprocessed numpy array.
    Returns a list of OCRBlock objects with text, bbox, and confidence.
    """
    ocr = _get_ocr()
    result = ocr.ocr(processed_image)

    blocks: List[OCRBlock] = []
    if not result or not result[0]:
        logger.warning("PaddleOCR returned empty result")
        return blocks

    for line in result[0]:
        poly, (text, conf) = line
        # poly is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        bbox = [min(xs), min(ys), max(xs), max(ys)]

        if conf < config.OCR_CONFIDENCE_THRESHOLD:
            logger.debug("Skipping low-confidence block (%.2f): %s", conf, text)
            continue

        blocks.append(OCRBlock(text=text.strip(), bbox=bbox, confidence=round(conf, 4)))

    logger.info("OCR extracted %d blocks (confidence ≥ %.2f)",
                len(blocks), config.OCR_CONFIDENCE_THRESHOLD)
    return blocks


# ── High-level entry point ────────────────────────────────────────────────────

def process_document(file_path: str) -> List[OCRBlock]:
    """
    Full pipeline for a file path (image or PDF):
    load → preprocess → OCR → OCRBlock list
    """
    try:
        if file_path.lower().endswith(".pdf"):
            pil_image = pdf_to_image(file_path)
        else:
            pil_image = Image.open(file_path).convert("RGB")

        processed = preprocess(pil_image)
        return extract_text(processed)

    except Exception as exc:
        logger.error("process_document failed for %s: %s", file_path, exc, exc_info=True)
        raise
