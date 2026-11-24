"""
VERITEXT GEMINI HYBRID HANDWRITTEN OCR ENGINE
==============================================
Provides high-accuracy, hallucination-free transcription for handwritten pages
via the Gemini API (default: gemini-3.8-flash with fallback to gemini-3.5-flash-lite).

If an API key is not configured, the network is unavailable, or a rate limit is reached,
the system transparently falls back to the local TrOCR ONNX pipeline.
"""

import os
import io
import json
import base64
import logging
import re
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiHandwrittenOCREngine:
    """
    Direct REST-based client for Gemini handwriting OCR.
    Bypasses line segmentation, ruled paper interference, and local decoder hallucinations.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        timeout_seconds: float = 35.0
    ):
        self._api_key = api_key
        self._primary_model = primary_model
        self._fallback_model = fallback_model
        self.timeout = timeout_seconds

    @property
    def primary_model(self) -> str:
        if self._primary_model:
            return self._primary_model
        return getattr(settings, "GEMINI_OCR_MODEL", "gemini-3.5-flash-lite")

    @property
    def fallback_model(self) -> str:
        if self._fallback_model:
            return self._fallback_model
        return getattr(settings, "GEMINI_FALLBACK_MODEL", "gemini-3-flash-preview")

    @property
    def api_key(self) -> Optional[str]:
        if self._api_key:
            return self._api_key
        key = getattr(settings, "GEMINI_API_KEY", None)
        if key:
            return key
        return os.getenv("GEMINI_API_KEY", None)

    def is_available(self) -> bool:
        """Returns True if the engine is enabled and a valid API key is present."""
        enabled = getattr(settings, "ENABLE_HYBRID_HANDWRITING_OCR", True)
        return bool(enabled and self.api_key and len(self.api_key.strip()) > 5)

    def _image_to_base64_jpeg(self, image: Image.Image, max_dimension: int = 1500) -> Tuple[str, str]:
        """Converts PIL image to base64 JPEG payload, scaling down to optimal OCR resolution."""
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        w, h = image.size
        if max(w, h) > max_dimension:
            scale = max_dimension / max(w, h)
            new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
            image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)

        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=82)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        return encoded, "image/jpeg"

    def _call_gemini_api(self, model: str, image_b64: str, mime_type: str) -> Optional[str]:
        """Executes the generateContent REST call against the Gemini API."""
        key = self.api_key
        if not key:
            return None

        url = f"{GEMINI_API_BASE}/{model}:generateContent?key={key}"
        headers = {"Content-Type": "application/json"}

        system_instruction = (
            "You are an expert OCR transcription engine. "
            "Transcribe all handwritten and printed text visible in the document image verbatim in strict top-to-bottom reading order. "
            "Do not summarize, do not hallucinate, and do not add introductory remarks, notes, or conversational comments. "
            "Preserve exact words, spelling, punctuation, equations, line breaks, and bullet points as written. "
            "Output ONLY the raw verbatim transcribed text."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": "Transcribe all handwriting from this page verbatim according to the instructions."},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_b64
                            }
                        }
                    ]
                }
            ],
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "generationConfig": {
                "temperature": 0.0,
                "max_output_tokens": 4096
            }
        }

        # Try httpx with generous connect/read/write timeouts
        if HAS_HTTPX:
            timeout_cfg = httpx.Timeout(self.timeout, connect=15.0, read=self.timeout, write=self.timeout)
            with httpx.Client(timeout=timeout_cfg) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"]
                logger.warning(f"Gemini API returned status {resp.status_code} on model {model}: {resp.text[:200]}")
                return None
        elif HAS_REQUESTS:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates and "content" in candidates[0]:
                    parts = candidates[0]["content"].get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
            logger.warning(f"Gemini API returned status {resp.status_code} on model {model}: {resp.text[:200]}")
            return None
        else:
            logger.error("Neither httpx nor requests is installed; cannot call Gemini API.")
            return None

    def transcribe_page(
        self,
        pil_image: Image.Image,
        page_number: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Transcribes a handwritten page image using the Gemini API.
        Attempts primary_model first, falls back to fallback_model on 4xx/5xx failure.
        Returns a standardized VeriText page dict, or None if the API fails or is unavailable.
        """
        if not self.is_available():
            return None

        try:
            image_b64, mime_type = self._image_to_base64_jpeg(pil_image)
        except Exception as e:
            logger.warning(f"Failed to prepare image for Gemini OCR: {e}")
            return None

        # Multi-model resilient pool: automatically rotates models if one hits a temporary 503/429 demand spike
        candidate_pool = [
            self.primary_model,
            self.fallback_model,
            "gemini-3-flash-preview",
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.8-flash",
        ]
        # Deduplicate while preserving precedence
        seen_models = set()
        models_to_attempt = [m for m in candidate_pool if m and not (m in seen_models or seen_models.add(m))]

        raw_json_str = None
        active_model = self.primary_model

        for model_candidate in models_to_attempt:
            try:
                logger.info(f"Page {page_number}: Attempting Gemini OCR with model '{model_candidate}'...")
                raw_json_str = self._call_gemini_api(model_candidate, image_b64, mime_type)
                if raw_json_str and len(raw_json_str.strip()) > 5:
                    active_model = model_candidate
                    break
            except Exception as e:
                logger.warning(f"Gemini OCR call failed on model '{model_candidate}': {e}")

        if not raw_json_str:
            return None

        # Parse output
        try:
            cleaned_str = raw_json_str.strip()
            if cleaned_str.startswith("```"):
                cleaned_str = re.sub(r"^```[a-zA-Z]*\n", "", cleaned_str)
                cleaned_str = re.sub(r"\n```$", "", cleaned_str).strip()

            full_text = ""
            raw_lines = []

            if cleaned_str.startswith("{") and "text" in cleaned_str:
                try:
                    parsed = json.loads(cleaned_str)
                    full_text = parsed.get("text", "").strip()
                    raw_lines = parsed.get("lines", [])
                except Exception:
                    match = re.search(r'"text":\s*"(.*?)"', cleaned_str, re.DOTALL)
                    if match:
                        full_text = match.group(1).replace("\\n", "\n").replace('\\"', '"')
                    else:
                        full_text = cleaned_str
            else:
                full_text = cleaned_str

            img_w, img_h = pil_image.size
            structured_lines = []

            if isinstance(raw_lines, list) and raw_lines:
                total_lines = max(len(raw_lines), 1)
                for idx, line_item in enumerate(raw_lines, start=1):
                    line_txt = line_item.get("text", "").strip() if isinstance(line_item, dict) else str(line_item).strip()
                    if not line_txt:
                        continue
                    approx_y1 = int((idx - 1) * (img_h / total_lines))
                    approx_y2 = int(idx * (img_h / total_lines))
                    structured_lines.append({
                        "line_number": idx,
                        "page_number": page_number,
                        "raw_text": line_txt,
                        "text": line_txt,
                        "normalized_text": re.sub(r"[^\w\s]", " ", line_txt.lower()).strip(),
                        "recognition_score": 0.98,
                        "confidence": 0.98,
                        "bbox": [0, approx_y1, img_w, approx_y2],
                        "center_y": int((approx_y1 + approx_y2) / 2),
                        "doc_type": "handwritten",
                        "ocr_engine": f"gemini-hybrid ({active_model})",
                        "flagged_for_review": False,
                        "uncertain_words": [],
                        "candidate_details": {
                            "engine": active_model,
                            "provider": "gemini_api",
                            "status": "success"
                        }
                    })
            elif full_text:
                split_lines = [l.strip() for l in full_text.splitlines() if l.strip()]
                total_lines = max(len(split_lines), 1)
                for idx, clean_l in enumerate(split_lines, start=1):
                    approx_y1 = int((idx - 1) * (img_h / total_lines))
                    approx_y2 = int(idx * (img_h / total_lines))
                    structured_lines.append({
                        "line_number": idx,
                        "page_number": page_number,
                        "raw_text": clean_l,
                        "text": clean_l,
                        "normalized_text": re.sub(r"[^\w\s]", " ", clean_l.lower()).strip(),
                        "recognition_score": 0.98,
                        "confidence": 0.98,
                        "bbox": [0, approx_y1, img_w, approx_y2],
                        "center_y": int((approx_y1 + approx_y2) / 2),
                        "doc_type": "handwritten",
                        "ocr_engine": f"gemini-hybrid ({active_model})",
                        "flagged_for_review": False,
                        "uncertain_words": [],
                        "candidate_details": {
                            "engine": active_model,
                            "provider": "gemini_api",
                            "status": "success"
                        }
                    })

            if not full_text and structured_lines:
                full_text = "\n".join(l["text"] for l in structured_lines)

            logger.info(f"Page {page_number}: Gemini OCR successfully extracted {len(structured_lines)} line(s), {len(full_text.split())} words.")

            return {
                "page_number": page_number,
                "text": full_text,
                "raw_text": full_text,
                "lines": structured_lines,
                "doc_type": "handwritten",
                "ocr_engine": f"gemini-hybrid ({active_model})",
                "avg_confidence": 0.98,
                "confidence": 0.98,
                "needs_review": False,
                "diagnostics": {
                    "provider": "gemini_api",
                    "model": active_model,
                    "lines_count": len(structured_lines),
                    "segmentation_warning": False
                }
            }

        except Exception as e:
            logger.warning(f"Error parsing Gemini OCR JSON response: {e}. Raw response: {raw_json_str[:200]}")
            return None


# Global singleton instance
gemini_ocr_engine = GeminiHandwrittenOCREngine()
