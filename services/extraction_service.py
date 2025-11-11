"""
services/extraction_service.py
Hybrid extraction engine:
  1. Global text aggregation & Document detection
  2. Keyword + Proximity (with multi-line support)
  3. Global Regex extraction
  4. LLM Fallback (Gemini API)
"""
import re
import json
import logging
import datetime
from typing import List, Optional, Dict, Tuple, Any

from models.schemas import OCRBlock, ExtractedFields
from core.config import config

logger = logging.getLogger(__name__)

# ── Keyword maps ──────────────────────────────────────────────────────────────

_LICENSE_KEYWORDS: Dict[str, List[str]] = {
    "name":           ["NAME", "HOLDER", "FULL NAME"],
    "dob":            ["DOB", "BIRTH", "DATE OF BIRTH", "BORN"],
    "license_number": ["DL", "LIC", "LICENSE NO", "LICENCE NO", "DL NO", "DLN"],
    "issue_date":     ["ISSUE", "ISS", "DATE OF ISSUE", "ISSUED"],
    "expiry_date":    ["EXP", "EXPIRES", "EXPIRY", "EXPIRATION", "VALID THRU", "VALID UNTIL"],
}

_INSURANCE_KEYWORDS: Dict[str, List[str]] = {
    "name":           ["INSURED", "POLICY HOLDER", "NAME", "NAMED INSURED"],
    "dob":            ["DOB", "BIRTH", "DATE OF BIRTH"],
    "license_number": ["POLICY NO", "POLICY NUMBER", "POLICY#", "CERT NO"],
    "issue_date":     ["EFFECTIVE", "POLICY DATE", "ISSUED", "ISSUE DATE", "FROM"],
    "expiry_date":    ["EXPIRES", "EXPIRY", "EXPIRATION", "ENDS", "THROUGH", "THRU", "TO"],
}

# ── Regex patterns ────────────────────────────────────────────────────────────

_DATE_PATTERN = r"\b(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4}|\d{4}[\/\-\.]\d{2}[\/\-\.]\d{2}|\d{1,2}\s+[A-Za-z]{3,}\s+\d{4}|[A-Za-z]{3,}\.?\s+\d{1,2},?\s+\d{4})\b"
_LICENSE_PATTERN = r"\b([A-Z]{1,2}\d{5,8}|[A-Z]\d{3,4}-\d{3,4}-\d{2,4}|\d{3}-\d{2}-\d{4}|[A-Z0-9]{6,12})\b"

_DATE_FORMATS = [
    "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
    "%d.%m.%Y", "%m.%d.%Y", "%Y/%m/%d", "%Y-%m-%d",
    "%Y.%m.%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y",
    "%B %d, %Y", "%b. %d, %Y",
]

# ── Date utilities ────────────────────────────────────────────────────────────

def _parse_date(text: str) -> Optional[datetime.date]:
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None

def _format_date(dt: Optional[datetime.date]) -> Optional[str]:
    return dt.strftime("%Y-%m-%d") if dt else None


# ── Global Aggregation & Detection ───────────────────────────────────────────

def _build_full_text(blocks: List[OCRBlock]) -> Tuple[str, str]:
    """1. Global Text Aggregation"""
    texts = [block.text for block in blocks]
    full_text = " ".join(texts)
    return full_text, full_text.lower()

def _detect_doc_type(full_text_lower: str) -> str:
    """2. Document Type Detection (infers strictly from content)"""
    if "driver" in full_text_lower or "dl" in full_text_lower:
        return "license"
    if "policy" in full_text_lower or "member" in full_text_lower:
        return "insurance"
    return "unknown"


# ── Spatial Helpers ──────────────────────────────────────────────────────────

def _bbox_center(bbox: List[float]) -> Tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)

def _is_right_or_below(anchor_bbox, candidate_bbox, tolerance: float = 30) -> bool:
    ax1, ay1, ax2, ay2 = anchor_bbox
    cx1, cy1, cx2, cy2 = candidate_bbox
    same_row = abs((ay1 + ay2) / 2 - (cy1 + cy2) / 2) < tolerance
    to_right = cx1 >= ax2 - 5
    below    = cy1 >= ay2 - 5
    return (same_row and to_right) or below

def _distance(b1: List[float], b2: List[float]) -> float:
    c1 = _bbox_center(b1)
    c2 = _bbox_center(b2)
    return ((c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2) ** 0.5

def _find_nearest_block(anchor: OCRBlock, blocks: List[OCRBlock],
                        max_distance: float = 400) -> Optional[OCRBlock]:
    best_block: Optional[OCRBlock] = None
    best_dist = float("inf")
    for block in blocks:
        if block is anchor: continue
        if not _is_right_or_below(anchor.bbox, block.bbox): continue
        dist = _distance(anchor.bbox, block.bbox)
        if dist < best_dist and dist <= max_distance:
            best_dist = dist
            best_block = block
    return best_block

def _get_multiline_value(blocks: List[OCRBlock], index: int, max_lines: int = 2) -> Optional[Tuple[str, float]]:
    """3. Multi-line extraction by looking ahead sequentially."""
    values = []
    confs = []
    for i in range(1, max_lines + 1):
        if index + i < len(blocks):
            values.append(blocks[index + i].text)
            confs.append(blocks[index + i].confidence)
            
    if values:
        return " ".join(values), (sum(confs) / len(confs))
    return None

def _extract_with_keywords(
    blocks: List[OCRBlock],
    keyword_map: Dict[str, List[str]]
) -> Tuple[Dict[str, Optional[str]], Dict[str, Optional[float]]]:
    """4. Keyword + Proximity Extraction"""
    values: Dict[str, Optional[str]] = {k: None for k in keyword_map}
    confidences: Dict[str, Optional[float]] = {k: None for k in keyword_map}

    for i, block in enumerate(blocks):
        upper = block.text.upper()
        for field_name, keywords in keyword_map.items():
            if values[field_name] is not None:
                continue
            for kw in keywords:
                if kw in upper:
                    if field_name == "name" or field_name == "address":
                        res = _get_multiline_value(blocks, i, max_lines=2)
                        if res:
                            values[field_name] = res[0]
                            confidences[field_name] = res[1]
                    else:
                        val_block = _find_nearest_block(block, blocks)
                        if val_block:
                            values[field_name] = val_block.text
                            confidences[field_name] = val_block.confidence
                    break
    return values, confidences


# ── Global Regex Extraction ──────────────────────────────────────────────────

def _regex_extract(
    full_text: str,
    values: Dict[str, Optional[str]],
    confidences: Dict[str, Optional[float]]
) -> Tuple[Dict[str, Optional[str]], Dict[str, Optional[float]]]:
    """5. Global Regex Extraction scanning the full text block."""
    
    # Extract Dates
    dates_raw = re.findall(_DATE_PATTERN, full_text, flags=re.IGNORECASE)
    dates_parsed = []
    for d in dates_raw:
        parsed = _parse_date(d)
        if parsed:
            dates_parsed.append(parsed)
            
    dates_parsed = sorted(set(dates_parsed))
    
    if dates_parsed:
        if values.get("dob") is None and len(dates_parsed) >= 1:
            values["dob"] = _format_date(dates_parsed[0])
            confidences["dob"] = None
        if values.get("issue_date") is None and len(dates_parsed) >= 2:
            values["issue_date"] = _format_date(dates_parsed[1])
            confidences["issue_date"] = None
        if values.get("expiry_date") is None and len(dates_parsed) >= 3:
            values["expiry_date"] = _format_date(dates_parsed[-1])
            confidences["expiry_date"] = None
        elif values.get("expiry_date") is None and len(dates_parsed) >= 2: 
            values["expiry_date"] = _format_date(dates_parsed[-1])
            confidences["expiry_date"] = None

    # Extract License Number
    if values.get("license_number") is None:
        matches = re.finditer(_LICENSE_PATTERN, full_text)
        for m in matches:
            values["license_number"] = m.group(1)
            confidences["license_number"] = None
            break

    return values, confidences


# ── LLM Fallback (Gemini) ─────────────────────────────────────────────────────

def _should_use_llm(values: Dict[str, Optional[str]]) -> bool:
    """7. LLM Filtering: Only trigger LLM if multiple fields are missing."""
    keys_to_check = ["name", "license_number", "issue_date", "expiry_date"]
    missing = sum(1 for k in keys_to_check if not values.get(k))
    return missing >= 2


def _llm_extract_fallback(
    full_text: str, 
    current_values: Dict[str, Optional[str]], 
    doc_type: str
) -> Dict[str, Optional[str]]:
    """8. LLM Extraction (Optional)"""
    if not config.GEMINI_API_KEY:
        logger.warning("LLM Fallback skipped: GEMINI_API_KEY not set.")
        return current_values
        
    try:
        import google.generativeai as genai
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        prompt = f"""
        Extract structured data from this {doc_type} document.
        Return ONLY valid JSON with exactly these keys:
        {{
          "name": "string or null",
          "dob": "YYYY-MM-DD or null",
          "license_number": "string or null",
          "issue_date": "YYYY-MM-DD or null",
          "expiry_date": "YYYY-MM-DD or null"
        }}
        
        Text:
        {full_text}
        """
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        
        # 9. Error Handling - parse safely
        text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(text)
        
        logger.info(f"LLM Fallback successful. Data: {data}")
        
        # Merge results: only fill missing fields natively
        for k, v in data.items():
            if current_values.get(k) is None and v:
                current_values[k] = v
                
        return current_values

    except Exception as e:
        logger.error(f"LLM Fallback failed, failing over to heuristics cleanly: {e}")
        return current_values


# ── Final Build Logic ────────────────────────────────────────────────────────

def _filter_blocks(blocks: List[OCRBlock]) -> List[OCRBlock]:
    """6. Confidence Filtering"""
    return [b for b in blocks if b.confidence >= 0.6]

def _build_fields(
    values: Dict[str, Optional[str]],
    confidences: Dict[str, Optional[float]],
) -> ExtractedFields:
    expiry_str = values.get("expiry_date")
    expired = None
    if expiry_str:
        dt = _parse_date(expiry_str)
        if dt:
            expired = dt < datetime.date.today()

    field_confidence = {
        k: confidences.get(k)
        for k in ("name", "dob", "license_number", "issue_date", "expiry_date")
        if values.get(k) is not None
    }

    return ExtractedFields(
        name=values.get("name"),
        dob=values.get("dob"),
        license_number=values.get("license_number"),
        issue_date=values.get("issue_date"),
        expiry_date=values.get("expiry_date"),
        expired=expired,
        field_confidence=field_confidence,
    )

def _merge_results(
    doc_type: str,
    blocks: List[OCRBlock],
    keyword_map: Dict[str, List[str]]
) -> ExtractedFields:
    """10. Final Merge Logic Pipeline"""
    
    # 6. Filter low confidence
    clean_blocks = _filter_blocks(blocks)
    
    # 1. Global Aggregation
    full_text, full_text_lower = _build_full_text(clean_blocks)
    
    # 2. Document Detection Override
    inferred_type = _detect_doc_type(full_text_lower)
    if inferred_type != "unknown":
        doc_type = inferred_type

    # 4. Keyword extraction
    values, confidences = _extract_with_keywords(clean_blocks, keyword_map)
    
    # 5. Regex extraction
    values, confidences = _regex_extract(full_text, values, confidences)
    
    # 7. LLM Fallback
    if _should_use_llm(values):
        logger.info(f"Missing >=2 fields. Triggering LLM Fallback.")
        values = _llm_extract_fallback(full_text, values, doc_type)
    
    # Re-parse dates properly in case they were weirdly formatted by LLM/Regex
    for key in ("dob", "issue_date", "expiry_date"):
        if values.get(key):
            dt = _parse_date(values[key])
            values[key] = _format_date(dt)

    return _build_fields(values, confidences)


# ── Public API ────────────────────────────────────────────────────────────────

def extract_license_fields(blocks: List[OCRBlock]) -> ExtractedFields:
    """High-accuracy hybrid extraction for Drivers Licenses."""
    logger.info("Extracting license fields...")
    return _merge_results("license", blocks, _LICENSE_KEYWORDS)


def extract_insurance_fields(blocks: List[OCRBlock]) -> ExtractedFields:
    """High-accuracy hybrid extraction for Insurance Cards."""
    logger.info("Extracting insurance fields...")
    return _merge_results("insurance", blocks, _INSURANCE_KEYWORDS)
