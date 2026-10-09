"""
VERITEXT OCR Pipeline
=====================
High-efficiency, multi-stage OCR architecture for academic plagiarism detection and evaluation.

Core Architectural Principles:
------------------------------
1. Document Ingestion: PDF (PyMuPDF with digital text bypass), DOCX, Images, Plaintext.
2. Blank Page & Document Type Classification (digital_pdf, scanned_printed, handwritten, mixed).
3. Specialized Routing:
   - Digital PDF -> Direct PyMuPDF text stream extraction (<5ms, zero hallucination).
   - Scanned / Printed -> PaddleOCR primary (or WinOCR / Tesseract fallback).
   - Handwritten -> Ascender/Descender-safe Line Segmentation + local TrOCR (microsoft/trocr-base-handwritten).
4. 100% Local / Offline: No external cloud OCR APIs (Google Cloud Vision, Azure, AWS, OpenAI, Gemini).
5. Strict Raw OCR Preservation: Zero spelling, grammar, dictionary, or LLM mutation on raw_text and authoritative text.
6. Multi-Factor Candidate Selection with 3rd Hypothesis Arbitration: Combines model recognition score, normalized
   token length, cross-pass agreement, and anomaly metrics. Disagreements are preserved in candidate_details.
7. Complete Spatial Line Matching & Unmatched Pass-2 Line Preservation: Unmatched Pass-2 lines are retained in the
   final output with their actual bounding boxes and flagged for review.
8. Non-Destructive Ruled-Line Handling: Optional per-crop ruled line removal with stroke preservation fallbacks.
9. Source Traceability & Granular Diagnostics: Every line maintains exact page/bbox/crop/candidate traceability.
"""

import os
import io
import sys
import math
import json
import shutil
import logging
import asyncio
import concurrent.futures
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Tuple, Optional, Set
import docx
import numpy as np
import re
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from scipy import ndimage

# Ensure PaddleX / PaddleOCR 3.x bypasses external network model source checks
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_allocator_strategy"] = "auto_growth"
os.environ["OMP_NUM_THREADS"] = "4"

logger = logging.getLogger(__name__)

# =====================================================================
# CONFIGURATION & AUTO-DISCOVERY
# =====================================================================

TESSERACT_CANDIDATE_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
]

_tesseract_cache = {"checked": False, "module": None}
_paddle_cache = {"checked": False, "instance": None, "detector": None, "retry_count": 0}
_PADDLE_MAX_RETRIES = 3
DEBUG_HANDWRITING_OCR = os.getenv("DEBUG_HANDWRITING_OCR", "true").lower() in ("true", "1", "yes")

def _get_configured_tesseract():
    if _tesseract_cache["checked"]:
        return _tesseract_cache["module"]
    _tesseract_cache["checked"] = True
    try:
        import pytesseract
        for p in TESSERACT_CANDIDATE_PATHS:
            if os.path.isfile(p):
                pytesseract.pytesseract.tesseract_cmd = p
                _tesseract_cache["module"] = pytesseract
                logger.info(f"Tesseract OCR discovered at {p}")
                return pytesseract
        which_tess = shutil.which("tesseract")
        if which_tess:
            pytesseract.pytesseract.tesseract_cmd = which_tess
            _tesseract_cache["module"] = pytesseract
            logger.info(f"Tesseract OCR discovered on PATH: {which_tess}")
            return pytesseract
        _tesseract_cache["module"] = None
        return None
    except Exception as e:
        logger.debug(f"Tesseract discovery check: {e}")
        _tesseract_cache["module"] = None
        return None

def _get_paddle_ocr():
    """Dynamically loads PaddleOCR for printed text recognition."""
    if _paddle_cache["instance"] is not None:
        return _paddle_cache["instance"]
    if _paddle_cache["checked"] and _paddle_cache["retry_count"] >= _PADDLE_MAX_RETRIES:
        return None
    _paddle_cache["checked"] = True
    try:
        from paddleocr import PaddleOCR
        instance = None
        try:
            instance = PaddleOCR(use_textline_orientation=True, lang="en")
        except Exception:
            pass
        if instance is None:
            try:
                instance = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            except Exception:
                pass
        if instance is None:
            try:
                instance = PaddleOCR(lang="en")
            except Exception:
                pass

        if instance is not None:
            _paddle_cache["instance"] = instance
            _paddle_cache["retry_count"] = 0
            logger.info("PaddleOCR engine loaded for printed text processing.")
            return instance
        else:
            _paddle_cache["retry_count"] = _paddle_cache.get("retry_count", 0) + 1
            return None
    except Exception as e:
        _paddle_cache["retry_count"] = _paddle_cache.get("retry_count", 0) + 1
        logger.debug(f"PaddleOCR init fallback: {e}")
        return None


# =====================================================================
# DATA STRUCTURES
# =====================================================================

@dataclass
class LineRegion:
    image: Image.Image
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    center_y: int
    line_number: int
    is_handwritten: bool = True
    original_crop: Optional[Image.Image] = None
    line_removed_crop: Optional[Image.Image] = None


@dataclass
class RecognizedLine:
    line_number: int
    page_number: int                       # Source page index for traceability
    raw_text: str                          # Verbatim recognition output (untouched)
    text: str                              # Authoritative text preserving case, punctuation, math, code
    normalized_text: str                   # Downstream helper for similarity/indexing
    recognition_score: float               # Model-derived recognition score (normalized beam likelihood)
    variant_agreement: float               # Token/character agreement across preprocessing passes (0.0 to 1.0)
    uncertainty_score: float               # Composite uncertainty indicator (0.0 to 1.0)
    confidence: float                      # Legacy backward-compatible float: round(1.0 - uncertainty_score, 3)
    bbox: Tuple[int, int, int, int]        # x1, y1, x2, y2
    center_y: int
    doc_type: str
    ocr_engine: str
    flagged_for_review: bool
    uncertain_words: List[str] = field(default_factory=list)
    candidate_details: Optional[Dict[str, Any]] = None


@dataclass
class SegmentationDiagnostics:
    detected_lines_count: int = 0
    merged_lines_count: int = 0
    split_lines_count: int = 0
    unmatched_lines_count: int = 0
    avg_line_height: float = 0.0
    suspicious_tiny_crops: int = 0
    suspicious_huge_crops: int = 0
    segmentation_warning: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =====================================================================
# STEP 1: IMAGE QUALITY & BLANK PAGE DETECTION
# =====================================================================

def _is_blank_page(pil_image: Image.Image) -> bool:
    """Fast blank-page detection in <1ms using a 32x32 thumbnail sample."""
    try:
        thumb = pil_image.resize((32, 32), Image.Resampling.NEAREST).convert("L")
        arr = np.array(thumb, dtype=np.uint8)
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr))
        if mean_val >= 248.0 and std_val < 5.0:
            return True
        if mean_val <= 8.0 and std_val < 4.0:
            return True
        return False
    except Exception:
        return False

def _image_needs_heavy_preprocessing(pil_image: Image.Image) -> bool:
    """Determines if an image needs background normalization or is already clean."""
    try:
        thumb = pil_image.resize((128, 128), Image.Resampling.NEAREST).convert("L")
        arr = np.array(thumb, dtype=np.float32)
        bg_mask = arr > 200
        bg_ratio = float(np.sum(bg_mask)) / arr.size
        if bg_ratio > 0.55:
            bg_std = float(np.std(arr[bg_mask])) if np.any(bg_mask) else 999.0
            if bg_std < 18.0:
                return False
        return True
    except Exception:
        return True

def classify_document_type(
    pil_image: Optional[Image.Image] = None,
    digital_text: str = ""
) -> str:
    """Classifies the document/page type into digital_pdf, scanned_printed, handwritten, or mixed."""
    if digital_text:
        words = digital_text.strip().split()
        if len(words) >= 5:
            alpha_ratio = sum(c.isalnum() or c.isspace() for c in digital_text) / max(len(digital_text), 1)
            if alpha_ratio > 0.80:
                return "digital_pdf"

    if pil_image is None:
        return "scanned_printed"

    try:
        thumb = pil_image.copy()
        thumb.thumbnail((500, 500))
        gray = np.array(thumb.convert("L"), dtype=np.float32)

        bg = ndimage.gaussian_filter(gray, sigma=6)
        norm = np.clip((gray / (bg + 1e-5)) * 255.0, 0, 255)
        binary = (norm < 195).astype(np.uint8)

        total_ink = np.sum(binary)
        if total_ink < 80:
            return "scanned_printed"

        labeled, num_features = ndimage.label(binary)
        if num_features > 10:
            slices = ndimage.find_objects(labeled)
            heights = [(s[0].stop - s[0].start) for s in slices if s and (s[0].stop - s[0].start) > 3]
            widths = [(s[1].stop - s[1].start) for s in slices if s and (s[1].stop - s[1].start) > 3]

            if heights and widths:
                h_var = float(np.std(heights) / (np.mean(heights) + 1e-5))
                w_var = float(np.std(widths) / (np.mean(widths) + 1e-5))

                if h_var > 0.82 or w_var > 0.92:
                    return "handwritten"
                elif h_var > 0.58:
                    return "mixed"
                else:
                    return "scanned_printed"

        return "scanned_printed"
    except Exception as e:
        logger.debug(f"Document type classification fallback: {e}")
        return "scanned_printed"


# =====================================================================
# STEP 2: PREPROCESSING (NON-DESTRUCTIVE & CONSERVATIVE)
# =====================================================================

def _correct_skew(pil_image: Image.Image, max_angle: float = 12.0) -> Image.Image:
    """Fast sub-degree skew correction using horizontal projection profile variance."""
    try:
        thumb = pil_image.copy()
        thumb.thumbnail((300, 300))
        gray = np.array(thumb.convert("L"), dtype=np.float32)

        thresh = float(np.mean(gray)) * 0.95
        binary = (gray < thresh).astype(np.float32)

        if np.sum(binary) < 30:
            return pil_image

        coarse_angles = np.arange(-max_angle, max_angle + 1.0, 2.0)
        best_angle = 0.0
        max_var = -1.0

        for angle in coarse_angles:
            rotated = ndimage.rotate(binary, angle, reshape=False, order=0, cval=0.0)
            proj = np.sum(rotated, axis=1)
            var = float(np.var(proj))
            if var > max_var:
                max_var = var
                best_angle = angle

        fine_angles = np.arange(best_angle - 2.0, best_angle + 2.1, 0.5)
        for angle in fine_angles:
            rotated = ndimage.rotate(binary, angle, reshape=False, order=0, cval=0.0)
            proj = np.sum(rotated, axis=1)
            var = float(np.var(proj))
            if var > max_var:
                max_var = var
                best_angle = angle

        if abs(best_angle) >= 0.5:
            return pil_image.rotate(-best_angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(255, 255, 255))
        return pil_image
    except Exception as e:
        logger.debug(f"Deskewing fallback: {e}")
        return pil_image

def _preprocess_printed_image(pil_image: Image.Image) -> Image.Image:
    """Preprocessing tailored for printed text."""
    try:
        try:
            pil_image = ImageOps.exif_transpose(pil_image)
        except Exception:
            pass

        if pil_image.mode in ("RGBA", "LA") or (pil_image.mode == "P" and "transparency" in pil_image.info):
            rgba = pil_image.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            pil_image = Image.alpha_composite(bg, rgba).convert("RGB")
        elif pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        pil_image = _correct_skew(pil_image)

        w, h = pil_image.size
        max_side = max(w, h)
        if max_side < 1200:
            scale = 1800.0 / float(max_side)
            pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.Resampling.BICUBIC)
        elif max_side > 2600:
            scale = 2200.0 / float(max_side)
            pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.Resampling.BICUBIC)

        if _image_needs_heavy_preprocessing(pil_image):
            gray = pil_image.convert("L")
            w_cur, h_cur = gray.size
            small_w, small_h = max(1, w_cur // 4), max(1, h_cur // 4)
            small_gray = gray.resize((small_w, small_h), Image.Resampling.BILINEAR)
            small_arr = np.array(small_gray, dtype=np.float32)
            small_bg = ndimage.gaussian_filter(small_arr, sigma=10)

            bg_img = Image.fromarray(np.clip(small_bg, 1, 255).astype(np.uint8)).resize(gray.size, Image.Resampling.BILINEAR)
            bg_arr = np.array(bg_img, dtype=np.float32)
            gray_arr = np.array(gray, dtype=np.float32)

            norm_arr = np.clip((gray_arr / (bg_arr + 1e-5)) * 255.0, 0, 255).astype(np.uint8)
            norm_img = Image.fromarray(norm_arr)

            enhanced = ImageOps.autocontrast(norm_img, cutoff=0.5)
            enhancer = ImageEnhance.Contrast(enhanced)
            boosted = enhancer.enhance(1.20)
            sharpened = boosted.filter(ImageFilter.UnsharpMask(radius=1.0, percent=40, threshold=2))
            return sharpened.convert("RGB")
        else:
            enhanced = ImageOps.autocontrast(pil_image, cutoff=0.3)
            sharpened = enhanced.filter(ImageFilter.UnsharpMask(radius=0.8, percent=30, threshold=2))
            return sharpened
    except Exception as e:
        logger.warning(f"Printed preprocessing fallback: {e}")
        return pil_image.convert("RGB") if pil_image.mode != "RGB" else pil_image

def _preprocess_handwritten_image(pil_image: Image.Image, variant: str = "gentle") -> Image.Image:
    """
    Preserves original ink subtleties without aggressive binarization.
    Variants:
    - 'gentle': EXIF orientation fix, gentle skew correction, histogram normalization.
    - 'illumination': Bilinear background subtraction for shadow removal.
    - 'high_contrast': Autocontrast boost for faint ink or pencil.
    """
    try:
        try:
            pil_image = ImageOps.exif_transpose(pil_image)
        except Exception:
            pass

        if pil_image.mode in ("RGBA", "LA") or (pil_image.mode == "P" and "transparency" in pil_image.info):
            rgba = pil_image.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            pil_image = Image.alpha_composite(bg, rgba).convert("RGB")
        elif pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        pil_image = _correct_skew(pil_image, max_angle=10.0)

        w, h = pil_image.size
        max_side = max(w, h)
        if max_side < 1200:
            scale = 1600.0 / float(max_side)
            pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.Resampling.BICUBIC)
        elif max_side > 2400:
            scale = 2000.0 / float(max_side)
            pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.Resampling.BICUBIC)

        if variant == "gentle":
            enhanced = ImageOps.autocontrast(pil_image, cutoff=0.5)
            enhancer = ImageEnhance.Contrast(enhanced)
            boosted = enhancer.enhance(1.15)
            return boosted.filter(ImageFilter.UnsharpMask(radius=0.8, percent=30, threshold=2))

        elif variant == "illumination":
            gray = pil_image.convert("L")
            w_cur, h_cur = gray.size
            small_w, small_h = max(1, w_cur // 4), max(1, h_cur // 4)
            small_gray = gray.resize((small_w, small_h), Image.Resampling.BILINEAR)
            small_arr = np.array(small_gray, dtype=np.float32)
            small_bg = ndimage.gaussian_filter(small_arr, sigma=14)

            bg_img = Image.fromarray(np.clip(small_bg, 1, 255).astype(np.uint8)).resize(gray.size, Image.Resampling.BILINEAR)
            bg_arr = np.array(bg_img, dtype=np.float32)
            gray_arr = np.array(gray, dtype=np.float32)

            norm_arr = np.clip((gray_arr / (bg_arr + 1e-5)) * 255.0, 0, 255).astype(np.uint8)
            norm_img = Image.fromarray(norm_arr)
            enhanced = ImageOps.autocontrast(norm_img, cutoff=0.8)
            return enhanced.convert("RGB")

        elif variant == "high_contrast":
            gray = pil_image.convert("L")
            enhanced = ImageOps.autocontrast(gray, cutoff=1.5)
            enhancer = ImageEnhance.Contrast(enhanced)
            boosted = enhancer.enhance(1.35)
            sharpened = boosted.filter(ImageFilter.UnsharpMask(radius=1.0, percent=45, threshold=3))
            return sharpened.convert("RGB")

        return pil_image
    except Exception as e:
        logger.warning(f"Handwritten preprocessing fallback: {e}")
        return pil_image.convert("RGB") if pil_image.mode != "RGB" else pil_image

def _detect_and_remove_ruled_lines(line_crop: Image.Image) -> Tuple[Image.Image, bool]:
    """
    Conservatively detects and removes ruled notebook lines on a single line crop.
    Protects vertical and diagonal handwriting strokes intersecting the line.
    Returns (processed_image, lines_were_detected_and_removed).
    """
    try:
        w, h = line_crop.size
        if w < 60 or h < 15:
            return line_crop, False

        gray = np.array(line_crop.convert("L"), dtype=np.uint8)
        thresh = float(np.mean(gray)) - 0.35 * float(np.std(gray))
        binary = (gray < thresh).astype(np.uint8)

        min_line_len = max(30, int(w * 0.55))
        h_kernel = np.ones((1, min_line_len), dtype=np.uint8)
        eroded = ndimage.binary_erosion(binary, structure=h_kernel)
        detected_lines = ndimage.binary_dilation(eroded, structure=h_kernel)

        if not np.any(detected_lines):
            return line_crop, False

        v_kernel = np.ones((max(4, int(h * 0.35)), 1), dtype=np.uint8)
        vertical_strokes = ndimage.binary_opening(binary, structure=v_kernel)

        mask_to_remove = detected_lines & (~vertical_strokes)

        clean_arr = gray.copy()
        bg_val = int(np.percentile(gray, 85))
        clean_arr[mask_to_remove] = bg_val

        initial_ink = np.sum(binary)
        remaining_ink = np.sum(clean_arr < thresh)
        if initial_ink > 0 and (initial_ink - remaining_ink) / float(initial_ink) > 0.35:
            return line_crop, False

        return Image.fromarray(clean_arr).convert("RGB"), True
    except Exception as e:
        logger.debug(f"Ruled-line removal check fallback: {e}")
        return line_crop, False


# =====================================================================
# STEP 3: ASCENDER/DESCENDER-SAFE LINE SEGMENTATION & DIAGNOSTICS
# =====================================================================

def segment_text_lines(
    pil_image: Image.Image,
    min_line_height: int = 20,
    vertical_pad_ratio: float = 0.30,
    min_vertical_pad: int = 18
) -> Tuple[List[LineRegion], SegmentationDiagnostics]:
    """
    Segments handwritten pages into individual text line crops with ascender/descender protection.
    Returns: (list of LineRegion objects, SegmentationDiagnostics metadata).
    """
    diag = SegmentationDiagnostics()
    try:
        w, h = pil_image.size
        scale = min(1.0, 700.0 / max(w, h))
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))

        if scale < 1.0:
            thumb = pil_image.resize((sw, sh), Image.Resampling.BILINEAR).convert("L")
            arr = np.array(thumb, dtype=np.uint8)
        else:
            arr = np.array(pil_image.convert("L"), dtype=np.uint8)

        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr))
        thresh = max(40, mean_val - 0.40 * std_val)
        ink = (arr < thresh)

        # Horizontal smearing to connect words on each handwritten line
        h_kernel_w = max(8, int(sw * 0.045))
        h_struct = np.ones((3, h_kernel_w), dtype=bool)
        smeared = ndimage.binary_dilation(ink, structure=h_struct)

        # Close slight vertical intra-line gaps
        v_struct = np.ones((5, 3), dtype=bool)
        smeared = ndimage.binary_closing(smeared, structure=v_struct)

        labeled, _ = ndimage.label(smeared)
        slices = ndimage.find_objects(labeled)

        raw_boxes: List[Tuple[int, int, int, int]] = []
        inv_scale = 1.0 / scale
        s_min_lh = max(4, int(min_line_height * scale))

        for sl in slices:
            if sl is None:
                continue
            sy1, sy2 = sl[0].start, sl[0].stop
            sx1, sx2 = sl[1].start, sl[1].stop
            sbw = sx2 - sx1
            sbh = sy2 - sy1

            if sbw >= int(45 * scale) and sbh >= s_min_lh and sbh <= int(sh * 0.45):
                y1 = int(sy1 * inv_scale)
                y2 = min(h, int(sy2 * inv_scale))
                x1 = int(sx1 * inv_scale)
                x2 = min(w, int(sx2 * inv_scale))
                bh = y2 - y1

                pad_y = max(min_vertical_pad, int(bh * vertical_pad_ratio))
                ny1 = max(0, y1 - pad_y)
                ny2 = min(h, y2 + pad_y)
                nx1 = max(0, x1 - 25)
                nx2 = min(w, x2 + 25)
                raw_boxes.append((nx1, ny1, nx2, ny2))

        # Sort top-to-bottom
        raw_boxes.sort(key=lambda b: (b[1], b[0]))

        # Merge overlapping line segments on the same horizontal baseline
        merged_boxes: List[Tuple[int, int, int, int]] = []
        for b in raw_boxes:
            if not merged_boxes:
                merged_boxes.append(b)
                continue
            prev = merged_boxes[-1]
            overlap_y = min(prev[3], b[3]) - max(prev[1], b[1])
            min_h = min(prev[3] - prev[1], b[3] - b[1])
            if overlap_y > 0.50 * min_h and abs(b[1] - prev[1]) < 35:
                diag.merged_lines_count += 1
                merged_boxes[-1] = (
                    min(prev[0], b[0]),
                    min(prev[1], b[1]),
                    max(prev[2], b[2]),
                    max(prev[3], b[3])
                )
            else:
                merged_boxes.append(b)

        # Fallback to projection profile if morphology found no lines
        if not merged_boxes:
            proj = np.sum(ink.astype(np.float32), axis=1)
            kernel_size = max(5, int(sh * 0.012))
            if kernel_size % 2 == 0:
                kernel_size += 1
            smoothed = np.convolve(proj, np.ones(kernel_size) / kernel_size, mode="same")
            line_thresh = float(np.mean(smoothed)) * 0.22

            intervals: List[Tuple[int, int]] = []
            in_line = False
            start_y = 0
            for y in range(sh):
                val = smoothed[y]
                if not in_line and val > line_thresh:
                    in_line = True
                    start_y = y
                elif in_line and val <= line_thresh:
                    in_line = False
                    if y - start_y >= s_min_lh:
                        intervals.append((start_y, y))
            if in_line and (sh - start_y) >= s_min_lh:
                intervals.append((start_y, sh))

            for s, e in intervals:
                y1 = int(s * inv_scale)
                y2 = min(h, int(e * inv_scale))
                bh = y2 - y1
                pad_y = max(min_vertical_pad, int(bh * vertical_pad_ratio))
                merged_boxes.append((0, max(0, y1 - pad_y), w, min(h, y2 + pad_y)))

        # Create LineRegion objects and compute diagnostics
        regions: List[LineRegion] = []
        heights = []
        for idx, (x1, y1, x2, y2) in enumerate(merged_boxes, start=1):
            crop_orig = pil_image.crop((x1, y1, x2, y2))
            line_h = y2 - y1
            heights.append(line_h)

            if line_h < 18:
                diag.suspicious_tiny_crops += 1
            elif line_h > int(h * 0.35):
                diag.suspicious_huge_crops += 1

            crop_ruled, had_ruled = _detect_and_remove_ruled_lines(crop_orig)

            regions.append(LineRegion(
                image=crop_orig,
                bbox=(x1, y1, x2, y2),
                center_y=int((y1 + y2) / 2),
                line_number=idx,
                is_handwritten=True,
                original_crop=crop_orig,
                line_removed_crop=crop_ruled if had_ruled else None
            ))

        diag.detected_lines_count = len(regions)
        diag.avg_line_height = round(float(np.mean(heights)), 1) if heights else 0.0
        diag.segmentation_warning = (diag.suspicious_huge_crops > 0) or (diag.detected_lines_count == 0)

        return regions, diag
    except Exception as e:
        logger.warning(f"Line segmentation error: {e}")
        diag.segmentation_warning = True
        return [], diag


# =====================================================================
# STEP 4: LOCAL PRIMARY HANDWRITING ENGINE (TrOCR)
# =====================================================================

class TrOCREngine:
    """
    Local Vision-Encoder-Decoder Engine for single-line handwriting recognition.
    Default Model: microsoft/trocr-base-handwritten.
    Inference: Deterministic beam search (do_sample=False, num_beams=4).
    Zero cloud calls — 100% offline inference.
    """
    def __init__(self, model_path: Optional[str] = None):
        self.processor = None
        self.model = None
        self.is_loaded = False
        self.load_failed = False
        self.device = "cpu"
        self.configured_path = model_path
        self.default_model_id = "microsoft/trocr-base-handwritten"
        self.fallback_model_id = "microsoft/trocr-small-handwritten"
        self.custom_weights_path = Path(__file__).resolve().parent / "weights" / "trocr"

    def _load_model_internal(self):
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        target_path = self.default_model_id

        if self.configured_path and Path(self.configured_path).exists():
            target_path = self.configured_path
        elif (self.custom_weights_path / "model.safetensors").exists() or (self.custom_weights_path / "pytorch_model.bin").exists():
            target_path = str(self.custom_weights_path)

        logger.info(f"Loading local TrOCR Handwriting model from '{target_path}' on {self.device}")
        try:
            self.processor = TrOCRProcessor.from_pretrained(target_path)
            self.model = VisionEncoderDecoderModel.from_pretrained(target_path)
        except Exception as ex_base:
            logger.warning(f"Failed loading {target_path} ({ex_base}), trying fallback {self.fallback_model_id}")
            self.processor = TrOCRProcessor.from_pretrained(self.fallback_model_id)
            self.model = VisionEncoderDecoderModel.from_pretrained(self.fallback_model_id)

        self.model.to(self.device)
        self.model.eval()
        self.is_loaded = True
        logger.info("Local TrOCR Handwriting Engine initialized successfully.")

    def load_model(self):
        if self.is_loaded or self.load_failed:
            return
        try:
            self._load_model_internal()
        except Exception as e:
            self.load_failed = True
            logger.info(f"TrOCR initialization fallback ({e}).")

    def recognize_lines_batch(
        self,
        line_imgs: List[Image.Image],
        batch_size: int = 4
    ) -> List[Tuple[str, float]]:
        """
        Recognizes multiple line strips using batched deterministic beam search.
        Returns: List of (raw_recognized_text, recognition_score).
        recognition_score is the model-derived length-normalized sequence score (0.0 to 1.0).
        """
        if not self.is_loaded:
            self.load_model()
        if not self.is_loaded or self.model is None or self.processor is None:
            return [("", 0.0) for _ in line_imgs]

        try:
            import torch
            results: List[Tuple[str, float]] = []

            for i in range(0, len(line_imgs), batch_size):
                batch = line_imgs[i : i + batch_size]
                rgb_batch = [img.convert("RGB") if img.mode != "RGB" else img for img in batch]

                inputs = self.processor(rgb_batch, return_tensors="pt")
                pixel_values = inputs.pixel_values.to(self.device)

                with torch.no_grad():
                    output = self.model.generate(
                        pixel_values,
                        return_dict_in_generate=True,
                        output_scores=True,
                        do_sample=False,
                        num_beams=4,
                        length_penalty=1.0,
                        early_stopping=True,
                        max_new_tokens=64,
                        no_repeat_ngram_size=4,
                        repetition_penalty=1.20,
                    )

                sequences = output.sequences
                decoded = self.processor.batch_decode(sequences, skip_special_tokens=True)
                beam_scores = getattr(output, "sequences_scores", None)

                for b_idx, text in enumerate(decoded):
                    clean_line = text.strip()

                    # Filter out pathological looping tokens (e.g. "a a a a a a")
                    if re.search(r"(\b\w\b\s+){5,}", clean_line) or re.search(r"(\W+\w\W+){5,}", clean_line):
                        results.append(("", 0.0))
                        continue

                    # Compute model recognition score from length-normalized beam log-likelihood
                    rec_score = 0.80
                    if beam_scores is not None and len(beam_scores) > b_idx:
                        raw_score = float(beam_scores[b_idx].item())
                        tok_len = max(len(sequences[b_idx]), 1)
                        norm_score = raw_score / tok_len
                        rec_score = float(np.clip(math.exp(norm_score * 0.75), 0.20, 0.98))

                    results.append((clean_line, round(rec_score, 3)))

            return results
        except Exception as e:
            logger.debug(f"TrOCR recognition error: {e}")
            return [("", 0.0) for _ in line_imgs]

_trocr_engine = TrOCREngine()


# =====================================================================
# WINOCR & TESSERACT ENGINES (FOR SCANNED PRINTED TEXT ONLY)
# =====================================================================

def _run_winocr_sync(target_img: Image.Image, page_number: int = 1) -> Tuple[str, List[RecognizedLine]]:
    """Windows WinRT OCR execution for printed text documents."""
    lines_found: List[RecognizedLine] = []
    try:
        import winocr
        rgb_img = target_img.convert("RGB") if target_img.mode != "RGB" else target_img
        loop = asyncio.new_event_loop()
        try:
            ocr_result = loop.run_until_complete(winocr.recognize_pil(rgb_img, lang="en"))
        finally:
            loop.close()

        if ocr_result and hasattr(ocr_result, "lines"):
            for idx, line in enumerate(ocr_result.lines, start=1):
                txt = getattr(line, "text", "").strip()
                if not txt:
                    continue
                bbox = (0, 0, target_img.width, target_img.height)
                if hasattr(line, "words") and line.words:
                    min_x = min(getattr(w.bounding_rect, "x", 0) for w in line.words)
                    min_y = min(getattr(w.bounding_rect, "y", 0) for w in line.words)
                    max_x = max(getattr(w.bounding_rect, "x", 0) + getattr(w.bounding_rect, "width", 0) for w in line.words)
                    max_y = max(getattr(w.bounding_rect, "y", 0) + getattr(w.bounding_rect, "height", 0) for w in line.words)
                    bbox = (int(min_x), int(min_y), int(max_x), int(max_y))

                rec_score = 0.90
                lines_found.append(RecognizedLine(
                    line_number=idx,
                    page_number=page_number,
                    raw_text=txt,
                    text=txt,
                    normalized_text=_normalize_for_indexing(txt),
                    recognition_score=rec_score,
                    variant_agreement=1.0,
                    uncertainty_score=0.10,
                    confidence=0.90,
                    bbox=bbox,
                    center_y=int((bbox[1] + bbox[3]) / 2),
                    doc_type="scanned_printed",
                    ocr_engine="winocr",
                    flagged_for_review=False,
                    uncertain_words=[],
                    candidate_details=None
                ))
            full_txt = "\n".join(l.text for l in lines_found)
            return full_txt, lines_found
    except Exception as e:
        logger.debug(f"WinOCR printed fallback: {e}")

    # Tesseract fallback
    tess = _get_configured_tesseract()
    if tess:
        try:
            data = tess.image_to_data(target_img, output_type=tess.Output.DICT)
            n_boxes = len(data["text"])
            line_map: Dict[int, List[str]] = {}
            line_boxes: Dict[int, List[Tuple[int, int, int, int]]] = {}

            for i in range(n_boxes):
                w_text = data["text"][i].strip()
                if not w_text:
                    continue
                l_num = data["line_num"][i]
                line_map.setdefault(l_num, []).append(w_text)
                bx = (data["left"][i], data["top"][i], data["left"][i] + data["width"][i], data["top"][i] + data["height"][i])
                line_boxes.setdefault(l_num, []).append(bx)

            for idx, (l_num, w_list) in enumerate(sorted(line_map.items()), start=1):
                txt = " ".join(w_list).strip()
                bxs = line_boxes[l_num]
                min_x = min(b[0] for b in bxs)
                min_y = min(b[1] for b in bxs)
                max_x = max(b[2] for b in bxs)
                max_y = max(b[3] for b in bxs)
                lines_found.append(RecognizedLine(
                    line_number=idx,
                    page_number=page_number,
                    raw_text=txt,
                    text=txt,
                    normalized_text=_normalize_for_indexing(txt),
                    recognition_score=0.85,
                    variant_agreement=1.0,
                    uncertainty_score=0.15,
                    confidence=0.85,
                    bbox=(min_x, min_y, max_x, max_y),
                    center_y=int((min_y + max_y) / 2),
                    doc_type="scanned_printed",
                    ocr_engine="tesseract",
                    flagged_for_review=False,
                    uncertain_words=[],
                    candidate_details=None
                ))
            return "\n".join(l.text for l in lines_found), lines_found
        except Exception as e:
            logger.debug(f"Tesseract fallback: {e}")

    return "", []

def _run_paddleocr_sync(target_img: Image.Image, page_number: int = 1) -> Tuple[str, List[RecognizedLine]]:
    """Runs PaddleOCR on printed documents."""
    paddle_engine = _get_paddle_ocr()
    if paddle_engine is None:
        return "", []

    try:
        np_img = np.array(target_img.convert("RGB"))
        ocr_res = paddle_engine.ocr(np_img, cls=True)

        if not ocr_res or ocr_res == [None] or len(ocr_res) == 0:
            return "", []

        lines_found: List[RecognizedLine] = []
        page_results = ocr_res[0] if (isinstance(ocr_res, list) and len(ocr_res) > 0 and isinstance(ocr_res[0], list)) else ocr_res

        if not page_results:
            return "", []

        for idx, item in enumerate(page_results, start=1):
            if not item or len(item) < 2:
                continue
            box_points = item[0]
            text_conf_tuple = item[1]

            text_content = text_conf_tuple[0].strip() if len(text_conf_tuple) > 0 else ""
            if not text_content:
                continue

            conf_val = float(text_conf_tuple[1]) if len(text_conf_tuple) > 1 else 0.85

            x_coords = [p[0] for p in box_points]
            y_coords = [p[1] for p in box_points]
            min_x, max_x = int(min(x_coords)), int(max(x_coords))
            min_y, max_y = int(min(y_coords)), int(max(y_coords))

            lines_found.append(RecognizedLine(
                line_number=idx,
                page_number=page_number,
                raw_text=text_content,
                text=text_content,
                normalized_text=_normalize_for_indexing(text_content),
                recognition_score=round(conf_val, 3),
                variant_agreement=1.0,
                uncertainty_score=round(max(0.05, 1.0 - conf_val), 3),
                confidence=round(conf_val, 3),
                bbox=(min_x, min_y, max_x, max_y),
                center_y=int((min_y + max_y) / 2),
                doc_type="scanned_printed",
                ocr_engine="paddleocr",
                flagged_for_review=conf_val < 0.70,
                uncertain_words=[],
                candidate_details=None
            ))

        full_text = "\n".join(l.text for l in lines_found)
        return full_text, lines_found
    except Exception as e:
        logger.warning(f"PaddleOCR recognition failed: {e}")
        return "", []


# =====================================================================
# STEP 5: SPATIAL MATCHING & MULTI-FACTOR CANDIDATE SELECTION
# =====================================================================

def _normalize_for_indexing(text: str) -> str:
    """Helper for downstream plagiarism similarity indexing without altering authoritative OCR text."""
    t = re.sub(r"\s+", " ", text).strip()
    return t

def _compute_token_agreement(text_a: str, text_b: str) -> float:
    """Computes word and character overlap ratio between two candidate texts (0.0 to 1.0)."""
    if not text_a and not text_b:
        return 1.0
    if not text_a or not text_b:
        return 0.0

    words_a = text_a.split()
    words_b = text_b.split()

    if not words_a or not words_b:
        return 0.0

    set_a, set_b = set(words_a), set(words_b)
    word_overlap = len(set_a & set_b) / float(len(set_a | set_b))

    len_a, len_b = len(text_a), len(text_b)
    dp = [[0] * (len_b + 1) for _ in range(len_a + 1)]
    for i in range(len_a + 1):
        dp[i][0] = i
    for j in range(len_b + 1):
        dp[0][j] = j
    for i in range(1, len_a + 1):
        for j in range(1, len_b + 1):
            cost = 0 if text_a[i - 1] == text_b[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    lev_sim = 1.0 - (float(dp[len_a][len_b]) / max(len_a, len_b, 1))

    return round(float(0.5 * word_overlap + 0.5 * max(0.0, lev_sim)), 3)

def _evaluate_line_anomalies(text: str) -> Tuple[float, List[str]]:
    """
    Evaluates character and token plausibility for uncertainty scoring ONLY.
    IMPORTANT: Single-character tokens (A, x, n, Q, 1, etc.) are NOT penalized.
    Preserves math, programming code, formulas, and abbreviations without rewriting text.
    """
    words = text.split()
    if not words:
        return 1.0, []

    uncertain_words = []
    penalty = 0.0

    for w in words:
        if "\ufffd" in w or "\\x" in w or "|" in w or "~" in w or "^" in w:
            uncertain_words.append(w)
            penalty += 0.15
            continue

        # Mathematical and technical tokens are fully valid
        if re.search(r"^[<>=!+\-*/_#&|~`]+$", w) or re.search(r"^\d+[\w\^\.]*$", w):
            continue

        clean_w = re.sub(r"^[^\w]+|[^\w]+$", "", w)
        if not clean_w:
            continue

        # Single characters are legitimate (math variables, options, code) - NO PENALTY
        if len(clean_w) <= 2:
            continue

        # Digit mixed inside alphabetical word (OCR digit substitution artifact e.g. pr0c3ssing)
        if re.search(r"[a-zA-Z]+\d+[a-zA-Z]+", clean_w):
            uncertain_words.append(w)
            penalty += 0.12
            continue

        # Long consonant clusters with no vowels in non-technical tokens (e.g. sytctc, smlrt, mdls)
        if len(clean_w) >= 4 and not re.search(r"[aeiouyAEIOUY]", clean_w):
            uncertain_words.append(w)
            penalty += 0.10

    return round(min(0.40, penalty), 3), uncertain_words

def _select_best_candidate(
    cand1_text: str,
    cand1_score: float,
    cand2_text: str,
    cand2_score: float,
    line_number: int,
    page_number: int,
    bbox: Tuple[int, int, int, int],
    crop_img: Optional[Image.Image] = None
) -> RecognizedLine:
    """
    Multi-Factor Candidate Selection with 3rd Hypothesis Arbitration:
    - If Pass 1 and Pass 2 disagree severely (agreement < 0.60), runs a 3rd hypothesis crop.
    - Preserves all candidates in candidate_details.
    - Never mutates raw_text. Flags line explicitly if disagreement persists.
    """
    agreement = _compute_token_agreement(cand1_text, cand2_text)
    cand3_text = ""
    cand3_score = 0.0
    third_hypothesis_used = False

    # Severe Disagreement Handling: trigger 3rd deterministic hypothesis
    if cand1_text.strip() and cand2_text.strip() and agreement < 0.60 and crop_img is not None:
        try:
            high_contrast_crop = ImageOps.autocontrast(crop_img.convert("L"), cutoff=1.5)
            enhancer = ImageEnhance.Contrast(high_contrast_crop)
            boosted_crop = enhancer.enhance(1.30).filter(ImageFilter.UnsharpMask(radius=1.0, percent=40, threshold=2)).convert("RGB")
            c3_res = _trocr_engine.recognize_lines_batch([boosted_crop], batch_size=1)
            if c3_res and len(c3_res) > 0:
                cand3_text, cand3_score = c3_res[0]
                third_hypothesis_used = True
        except Exception as ex_c3:
            logger.debug(f"3rd hypothesis generation skipped: {ex_c3}")

    anomaly_pen1, uncert1 = _evaluate_line_anomalies(cand1_text)
    anomaly_pen2, uncert2 = _evaluate_line_anomalies(cand2_text)
    anomaly_pen3, uncert3 = _evaluate_line_anomalies(cand3_text) if third_hypothesis_used else (0.0, [])

    q1 = cand1_score - anomaly_pen1
    q2 = cand2_score - anomaly_pen2
    q3 = cand3_score - anomaly_pen3 if third_hypothesis_used else -999.0

    if not cand1_text.strip() and (cand2_text.strip() or cand3_text.strip()):
        q1 -= 1.0
    if not cand2_text.strip() and (cand1_text.strip() or cand3_text.strip()):
        q2 -= 1.0

    # Agreement matrix with 3rd candidate
    agr_13 = _compute_token_agreement(cand1_text, cand3_text) if third_hypothesis_used else 0.0
    agr_23 = _compute_token_agreement(cand2_text, cand3_text) if third_hypothesis_used else 0.0

    is_divergent = bool(cand1_text.strip() and cand2_text.strip() and agreement < 0.60)
    disagreement_severe = is_divergent and not (agr_13 >= 0.70 or agr_23 >= 0.70)

    # Candidate selection logic
    if third_hypothesis_used and agr_23 >= 0.70 and q2 >= q1:
        chosen_text = cand2_text
        chosen_score = cand2_score
        chosen_uncert = uncert2
        chosen_engine = "trocr_pass2_verified_by_pass3"
    elif third_hypothesis_used and agr_13 >= 0.70:
        chosen_text = cand1_text
        chosen_score = cand1_score
        chosen_uncert = uncert1
        chosen_engine = "trocr_pass1_verified_by_pass3"
    elif q2 > q1:
        chosen_text = cand2_text
        chosen_score = cand2_score
        chosen_uncert = uncert2
        chosen_engine = "trocr_pass2"
    else:
        chosen_text = cand1_text
        chosen_score = cand1_score
        chosen_uncert = uncert1
        chosen_engine = "trocr"

    # Transparent uncertainty calculation
    base_uncertainty = max(0.02, 1.0 - chosen_score)
    if is_divergent:
        base_uncertainty = min(0.95, base_uncertainty + 0.25)
    if disagreement_severe:
        base_uncertainty = min(0.98, base_uncertainty + 0.20)
    if chosen_uncert:
        base_uncertainty = min(0.95, base_uncertainty + min(0.30, 0.08 * len(chosen_uncert)))

    uncertainty_score = round(base_uncertainty, 3)
    flagged = (uncertainty_score > 0.35) or is_divergent or (len(chosen_uncert) > 0)
    conf_legacy = round(max(0.05, 1.0 - uncertainty_score), 3)

    return RecognizedLine(
        line_number=line_number,
        page_number=page_number,
        raw_text=chosen_text,
        text=chosen_text,
        normalized_text=_normalize_for_indexing(chosen_text),
        recognition_score=chosen_score,
        variant_agreement=agreement,
        uncertainty_score=uncertainty_score,
        confidence=conf_legacy,
        bbox=bbox,
        center_y=int((bbox[1] + bbox[3]) / 2),
        doc_type="handwritten",
        ocr_engine=chosen_engine,
        flagged_for_review=flagged,
        uncertain_words=chosen_uncert,
        candidate_details={
            "pass1_text": cand1_text,
            "pass1_score": cand1_score,
            "pass2_text": cand2_text,
            "pass2_score": cand2_score,
            "pass3_text": cand3_text if third_hypothesis_used else None,
            "pass3_score": cand3_score if third_hypothesis_used else None,
            "token_agreement_p1_p2": agreement,
            "is_divergent": is_divergent,
            "disagreement_severe": disagreement_severe,
            "all_candidates": [c for c in [cand1_text, cand2_text, cand3_text] if c]
        }
    )


# =====================================================================
# STEP 6: TWO-STAGE HYBRID PIPELINE WITH SPATIAL RECONSTRUCTION
# =====================================================================

def _reconstruct_page(
    lines: List[RecognizedLine],
    doc_type: str,
    page_number: int,
    engine_name: str,
    diagnostics: Optional[SegmentationDiagnostics] = None
) -> Dict[str, Any]:
    """Combines recognized lines into structured page hierarchy and metadata."""
    sorted_lines = sorted(lines, key=lambda l: (l.bbox[1], l.bbox[0]))
    for idx, l in enumerate(sorted_lines, start=1):
        l.line_number = idx

    paragraphs = []
    current_para = []
    prev_y2 = None
    median_line_height = 28.0

    if sorted_lines:
        heights = [(l.bbox[3] - l.bbox[1]) for l in sorted_lines if (l.bbox[3] - l.bbox[1]) > 5]
        if heights:
            median_line_height = float(np.median(heights))

    for line in sorted_lines:
        if not line.text.strip():
            continue
        y1, y2 = line.bbox[1], line.bbox[3]
        if prev_y2 is not None and (y1 - prev_y2) > (1.6 * median_line_height):
            if current_para:
                paragraphs.append(" ".join(current_para))
                current_para = []

        current_para.append(line.text.strip())
        prev_y2 = y2

    if current_para:
        paragraphs.append(" ".join(current_para))

    full_text = "\n\n".join(paragraphs).strip()
    if not full_text and sorted_lines:
        full_text = "\n".join(l.text.strip() for l in sorted_lines if l.text.strip())

    avg_rec_score = (
        round(sum(l.recognition_score for l in sorted_lines) / max(len(sorted_lines), 1), 3)
        if sorted_lines else 0.0
    )
    avg_agreement = (
        round(sum(l.variant_agreement for l in sorted_lines) / max(len(sorted_lines), 1), 3)
        if sorted_lines else 1.0
    )
    avg_conf = (
        round(sum(l.confidence for l in sorted_lines) / max(len(sorted_lines), 1), 3)
        if sorted_lines else 0.0
    )
    flagged_count = sum(1 for l in sorted_lines if l.flagged_for_review)
    needs_review = (flagged_count > 0) or (avg_conf < 0.70)

    if diagnostics and diagnostics.segmentation_warning:
        needs_review = True

    return {
        "page_number": page_number,
        "text": full_text,
        "raw_text": full_text,
        "ocr_engine": engine_name,
        "line_count": len(sorted_lines),
        "doc_type": doc_type,
        "avg_recognition_score": avg_rec_score,
        "avg_variant_agreement": avg_agreement,
        "avg_confidence": avg_conf,
        "flagged_lines_count": flagged_count,
        "needs_review": needs_review,
        "segmentation_diagnostics": diagnostics.to_dict() if diagnostics else {},
        "lines": [asdict(l) for l in sorted_lines]
    }

def _recognize_image_hybrid(
    pil_image: Image.Image,
    page_number: int = 1
) -> Tuple[str, Dict[str, Any]]:
    """
    Two-Stage Hybrid Recognition Pipeline:
    1. Classifies page (handwritten vs printed vs mixed).
    2. Routes directly to appropriate local engine:
       - Printed -> PaddleOCR primary, WinOCR / Tesseract fallback.
       - Handwritten -> Padded line segmentation + local TrOCR recognition.
    3. Multi-Pass Spatial Verification for Handwriting:
       - Matches Pass 1 lines with Pass 2 lines by spatial vertical overlap.
       - PRESERVES unmatched Pass-2 lines in final output with segmentation mismatch flags.
       - Multi-factor candidate selection with 3rd hypothesis arbitration for severe disagreements.
    4. Granular Debug Logging when DEBUG_HANDWRITING_OCR is active.
    """
    if _is_blank_page(pil_image):
        return "", {
            "page_number": page_number,
            "text": "",
            "raw_text": "",
            "ocr_engine": "none",
            "line_count": 0,
            "doc_type": "blank",
            "avg_recognition_score": 1.0,
            "avg_variant_agreement": 1.0,
            "avg_confidence": 1.0,
            "flagged_lines_count": 0,
            "needs_review": False,
            "segmentation_diagnostics": {},
            "lines": []
        }

def _legacy_recognize_handwritten_image(
    pil_image: Image.Image,
    page_number: int = 1
) -> Tuple[str, Dict[str, Any]]:
    """
    LEGACY Handwritten Recognition Implementation (PRESERVED INTACT FOR FALLBACK & TESTING).
    Multi-pass spatial verification with TrOCR base model.
    """
    recognized_lines: List[RecognizedLine] = []
    primary_engine_name = "trocr_legacy"
    diagnostics = SegmentationDiagnostics()

    logger.info(f"Page {page_number}: Executing LEGACY TrOCR handwriting pipeline.")
    prep_img_pass1 = _preprocess_handwritten_image(pil_image, variant="gentle")

    line_regions, diagnostics = segment_text_lines(prep_img_pass1)
    _trocr_engine.load_model()

    if _trocr_engine.is_loaded and line_regions:
        primary_engine_name = "trocr"
        crops_p1 = [r.image for r in line_regions]
        batch_results_p1 = _trocr_engine.recognize_lines_batch(crops_p1, batch_size=4)

        # Adaptive Pass 2 with illumination normalization
        needs_pass2 = any(score < 0.76 for (_, score) in batch_results_p1) or diagnostics.segmentation_warning
        batch_results_p2: Dict[int, Tuple[str, float]] = {}
        unmatched_p2_lines: List[RecognizedLine] = []

        if needs_pass2:
            logger.info(f"Page {page_number}: Executing Pass 2 with illumination-normalized crops.")
            prep_img_pass2 = _preprocess_handwritten_image(pil_image, variant="illumination")
            line_regions_p2, diag_p2 = segment_text_lines(prep_img_pass2)

            crops_p2 = [r.image for r in line_regions_p2]
            res_p2 = _trocr_engine.recognize_lines_batch(crops_p2, batch_size=4)

            matched_p2_indices: Set[int] = set()

            # Spatial Line Matcher between Pass 1 and Pass 2
            for idx2, (r2, (txt2, sc2)) in enumerate(zip(line_regions_p2, res_p2)):
                best_match_idx = None
                best_overlap = 0.0
                for idx1, r1 in enumerate(line_regions):
                    top = max(r1.bbox[1], r2.bbox[1])
                    bottom = min(r1.bbox[3], r2.bbox[3])
                    if bottom > top:
                        overlap = (bottom - top) / float(max(r1.bbox[3] - r1.bbox[1], r2.bbox[3] - r2.bbox[1], 1))
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_match_idx = idx1

                if best_match_idx is not None and best_overlap >= 0.40:
                    batch_results_p2[best_match_idx] = (txt2, sc2)
                    matched_p2_indices.add(idx2)
                else:
                    diagnostics.unmatched_lines_count += 1
                    diagnostics.split_lines_count += 1
                    diagnostics.segmentation_warning = True

                    if txt2 and txt2.strip():
                        unmatched_line = RecognizedLine(
                            line_number=len(line_regions) + len(unmatched_p2_lines) + 1,
                            page_number=page_number,
                            raw_text=txt2,
                            text=txt2,
                            normalized_text=_normalize_for_indexing(txt2),
                            recognition_score=sc2,
                            variant_agreement=0.0,
                            uncertainty_score=round(max(0.40, 1.0 - sc2), 3),
                            confidence=round(max(0.05, sc2 * 0.75), 3),
                            bbox=r2.bbox,
                            center_y=r2.center_y,
                            doc_type="handwritten",
                            ocr_engine="trocr_pass2_unmatched",
                            flagged_for_review=True,
                            uncertain_words=[],
                            candidate_details={
                                "pass1_text": "",
                                "pass1_score": 0.0,
                                "pass2_text": txt2,
                                "pass2_score": sc2,
                                "unmatched_pass2": True,
                                "segmentation_mismatch": True
                            }
                        )
                        unmatched_p2_lines.append(unmatched_line)

        # Build final recognized lines with candidate selection & debugging
        debug_dir = Path("debug_handwriting") / f"page_{page_number:03d}" if DEBUG_HANDWRITING_OCR else None
        if debug_dir:
            debug_dir.mkdir(parents=True, exist_ok=True)

        for idx, (r, (text1, score1)) in enumerate(zip(line_regions, batch_results_p1), start=1):
            p2_match = batch_results_p2.get(idx - 1, ("", 0.0))
            text2, score2 = p2_match

            rec_line = _select_best_candidate(
                cand1_text=text1,
                cand1_score=score1,
                cand2_text=text2,
                cand2_score=score2,
                line_number=idx,
                page_number=page_number,
                bbox=r.bbox,
                crop_img=r.image
            )
            recognized_lines.append(rec_line)

            if debug_dir:
                try:
                    r.image.save(str(debug_dir / f"line_{idx:03d}_original.png"))
                    if r.line_removed_crop:
                        r.line_removed_crop.save(str(debug_dir / f"line_{idx:03d}_line_removed.png"))
                    with open(debug_dir / f"line_{idx:03d}_result.txt", "w", encoding="utf-8") as df:
                        df.write(f"Raw Text: {rec_line.raw_text}\nScore: {rec_line.recognition_score}\nAgreement: {rec_line.variant_agreement}\nUncertainty: {rec_line.uncertainty_score}\nFlagged: {rec_line.flagged_for_review}\nCandidates: {json.dumps(rec_line.candidate_details, indent=2)}\n")
                except Exception as e:
                    logger.debug(f"Debug save error on line {idx}: {e}")

        if unmatched_p2_lines:
            recognized_lines.extend(unmatched_p2_lines)

    # TrOCR failure / fallback handling
    if not recognized_lines:
        logger.warning(f"Page {page_number}: TrOCR produced no lines for handwriting.")
        win_text, win_lines = _run_winocr_sync(prep_img_pass1, page_number=page_number)
        for wl in win_lines:
            wl.doc_type = "handwritten"
            wl.ocr_engine = "printed_ocr_fallback_on_handwriting"
            wl.flagged_for_review = True
            wl.uncertainty_score = 0.90
            wl.confidence = 0.10
            recognized_lines.append(wl)
        primary_engine_name = "printed_ocr_fallback_on_handwriting" if win_lines else "trocr_handwriting_failed"

    page_struct = _reconstruct_page(recognized_lines, "handwritten", page_number, primary_engine_name, diagnostics)
    return page_struct["text"], page_struct


def _evaluate_line_confidence(text: str, model_score: float = 0.85) -> Tuple[float, bool, List[str]]:
    """Legacy helper for test compatibility."""
    penalty, uncertain = _evaluate_line_anomalies(text)
    conf = round(max(0.05, min(0.99, model_score - penalty)), 2)
    flagged = (conf < 0.70) or (len(uncertain) > 0)
    return conf, flagged, uncertain


def _clean_ocr_text(text: str) -> str:
    """Helper for clean text output."""
    return re.sub(r"\s+", " ", text).strip()


def _recognize_image_hybrid(
    pil_image: Image.Image,
    page_number: int = 1
) -> Tuple[str, Dict[str, Any]]:
    """
    Two-Stage Hybrid Recognition Pipeline:
    1. Classifies page (handwritten vs printed vs mixed).
    2. Routes directly to appropriate local engine:
       - Printed -> PaddleOCR primary, WinOCR / Tesseract fallback (100% PRESERVED).
       - Handwritten -> NEW Handwritten OCR Pipeline (with legacy fallback).
    """
    if _is_blank_page(pil_image):
        return "", {
            "page_number": page_number,
            "text": "",
            "raw_text": "",
            "ocr_engine": "none",
            "line_count": 0,
            "doc_type": "blank",
            "avg_recognition_score": 1.0,
            "avg_variant_agreement": 1.0,
            "avg_confidence": 1.0,
            "flagged_lines_count": 0,
            "needs_review": False,
            "segmentation_diagnostics": {},
            "lines": []
        }

    doc_type = classify_document_type(pil_image)
    logger.info(f"Page {page_number} classified as: '{doc_type}'")

    recognized_lines: List[RecognizedLine] = []
    primary_engine_name = "unknown"
    diagnostics = SegmentationDiagnostics()

    # =================================================================
    # PATH A: HANDWRITTEN / MIXED DOCUMENT PIPELINE
    # =================================================================
    if doc_type in ("handwritten", "mixed"):
        try:
            from backend.app.ml.handwritten_ocr_pipeline import handwritten_ocr_pipeline
            logger.info(f"Page {page_number}: Routing to Local ONNX TrOCR handwritten pipeline.")
            page_struct = handwritten_ocr_pipeline.process_image(pil_image, page_number=page_number)
            if page_struct.get("text") or page_struct.get("lines"):
                return page_struct["text"], page_struct
        except Exception as ex_new:
            logger.warning(f"ONNX handwritten pipeline fallback to legacy due to: {ex_new}")

        # Fallback to legacy implementation if needed
        return _legacy_recognize_handwritten_image(pil_image, page_number=page_number)

    # =================================================================
    # PATH B: PRINTED DOCUMENT PIPELINE (PaddleOCR / WinOCR Primary)
    # =================================================================
    else:
        logger.info(f"Page {page_number}: Routing to printed document OCR pipeline.")

        prep_img = _preprocess_printed_image(pil_image)

        paddle_text, paddle_lines = _run_paddleocr_sync(prep_img, page_number=page_number)
        if paddle_lines and len(paddle_lines) >= 1:
            primary_engine_name = "paddleocr"
            recognized_lines.extend(paddle_lines)

        if not recognized_lines:
            primary_engine_name = "winocr"
            win_text, win_lines = _run_winocr_sync(prep_img, page_number=page_number)
            if not win_lines:
                win_text, win_lines = _run_winocr_sync(pil_image, page_number=page_number)
            recognized_lines.extend(win_lines)

    page_struct = _reconstruct_page(recognized_lines, doc_type, page_number, primary_engine_name, diagnostics)
    logger.info(
        f"Page {page_number} processed via [{page_struct['ocr_engine']}], "
        f"lines: {page_struct['line_count']}, avg_rec_score: {page_struct.get('avg_recognition_score', 0.0)}, "
        f"needs_review: {page_struct['needs_review']}"
    )
    return page_struct["text"], page_struct


# =====================================================================
# STEP 7: GROUND-TRUTH ACCURACY METRICS (CER & WER)
# =====================================================================

def compute_cer(reference: str, hypothesis: str) -> float:
    """
    Computes Character Error Rate (CER) against ground truth reference text.
    CER = (Substitutions + Deletions + Insertions) / len(reference).
    This function is strictly for ground-truth benchmark validation.
    """
    r_len, h_len = len(reference), len(hypothesis)
    if r_len == 0:
        return 0.0 if h_len == 0 else 1.0

    dp = [[0] * (h_len + 1) for _ in range(r_len + 1)]
    for i in range(r_len + 1):
        dp[i][0] = i
    for j in range(h_len + 1):
        dp[0][j] = j

    for i in range(1, r_len + 1):
        for j in range(1, h_len + 1):
            cost = 0 if reference[i - 1] == hypothesis[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)

    return round(float(dp[r_len][h_len]) / max(r_len, 1), 4)

def compute_wer(reference: str, hypothesis: str) -> float:
    """
    Computes Word Error Rate (WER) against ground truth reference text.
    WER = (Word Substitutions + Deletions + Insertions) / num_ref_words.
    This function is strictly for ground-truth benchmark validation.
    """
    r_words = reference.strip().split()
    h_words = hypothesis.strip().split()
    r_len, h_len = len(r_words), len(h_words)

    if r_len == 0:
        return 0.0 if h_len == 0 else 1.0

    dp = [[0] * (h_len + 1) for _ in range(r_len + 1)]
    for i in range(r_len + 1):
        dp[i][0] = i
    for j in range(h_len + 1):
        dp[0][j] = j

    for i in range(1, r_len + 1):
        for j in range(1, h_len + 1):
            cost = 0 if r_words[i - 1] == h_words[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)

    return round(float(dp[r_len][h_len]) / max(r_len, 1), 4)


# =====================================================================
# MAIN OCR ENGINE CLASS
# =====================================================================

class OCREngine:
    def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Main entry point for processing student assignment documents.
        Handles PDF, DOCX, Images, and Text files.
        """
        path = Path(file_path)
        if not path.exists():
            return {
                "extracted_text": "",
                "raw_text": "",
                "ocr_engine": "none",
                "confidence": 0.0,
                "needs_review": False,
                "pages": [],
                "lines": [],
                "word_count": 0,
                "status": "failed",
                "error": "File not found on storage"
            }

        suffix = path.suffix.lower()

        try:
            if suffix == ".pdf":
                return self._process_pdf(path)
            elif suffix == ".docx":
                return self._process_docx(path)
            elif suffix in [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"]:
                return self._process_image(path)
            else:
                return self._process_plaintext(path)
        except Exception as e:
            logger.exception(f"Document extraction error on {path}: {e}")
            return {
                "extracted_text": "",
                "raw_text": "",
                "ocr_engine": "error",
                "confidence": 0.0,
                "needs_review": False,
                "pages": [],
                "lines": [],
                "word_count": 0,
                "status": "failed",
                "error": f"Extraction error: {str(e)}"
            }

    def _process_pdf(self, path: Path) -> Dict[str, Any]:
        try:
            res = self._process_pdf_pymupdf(path)
            if res.get("word_count", 0) > 0 or len(res.get("pages", [])) > 0:
                return res
        except Exception as e:
            logger.warning(f"PyMuPDF failed on {path}, attempting pypdf fallback: {e}")

        try:
            res = self._process_pdf_pypdf(path)
            if res.get("word_count", 0) > 0:
                return res
        except Exception as e:
            logger.warning(f"pypdf failed on {path}, attempting pdfminer fallback: {e}")

        try:
            return self._process_pdf_pdfminer(path)
        except Exception as e:
            logger.error(f"All PDF extractors failed on {path}: {e}")
            return {
                "extracted_text": "",
                "raw_text": "",
                "ocr_engine": "none",
                "confidence": 0.0,
                "needs_review": False,
                "pages": [],
                "lines": [],
                "word_count": 0,
                "status": "failed",
                "error": f"All PDF extraction engines failed: {str(e)}"
            }

    def _process_pdf_pymupdf(self, path: Path) -> Dict[str, Any]:
        import pymupdf
        pages = []
        full_text = []
        all_lines = []
        doc = pymupdf.open(str(path))
        num_pages = len(doc)
        overall_engines = []

        for idx in range(num_pages):
            page_num = idx + 1
            try:
                page = doc[idx]
                raw_digital = (page.get_text("text", sort=True) or "").strip()
                doc_type = classify_document_type(digital_text=raw_digital)

                if doc_type == "digital_pdf" and len(raw_digital.split()) >= 5:
                    logger.info(f"Page {page_num}/{num_pages}: Digital text layer extracted directly via PyMuPDF.")
                    lines_split = [l.strip() for l in raw_digital.split("\n") if l.strip()]
                    page_lines = [
                        {
                            "line_number": i,
                            "page_number": page_num,
                            "raw_text": l,
                            "text": l,
                            "normalized_text": _normalize_for_indexing(l),
                            "recognition_score": 0.99,
                            "variant_agreement": 1.0,
                            "uncertainty_score": 0.01,
                            "confidence": 0.99,
                            "bbox": [0, i * 20, 800, (i + 1) * 20],
                            "center_y": i * 20 + 10,
                            "doc_type": "digital_pdf",
                            "ocr_engine": "pymupdf_digital",
                            "flagged_for_review": False,
                            "uncertain_words": [],
                            "candidate_details": None
                        }
                        for i, l in enumerate(lines_split, start=1)
                    ]
                    page_dict = {
                        "page_number": page_num,
                        "text": raw_digital,
                        "raw_text": raw_digital,
                        "ocr_engine": "pymupdf_digital",
                        "line_count": len(lines_split),
                        "doc_type": "digital_pdf",
                        "avg_recognition_score": 0.99,
                        "avg_variant_agreement": 1.0,
                        "avg_confidence": 0.99,
                        "flagged_lines_count": 0,
                        "needs_review": False,
                        "segmentation_diagnostics": {},
                        "lines": page_lines
                    }
                    pages.append(page_dict)
                    all_lines.extend(page_lines)
                    overall_engines.append("pymupdf_digital")
                    if raw_digital:
                        full_text.append(raw_digital)
                else:
                    pix = page.get_pixmap(dpi=300)
                    pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    _, page_dict = _recognize_image_hybrid(pil_img, page_number=page_num)
                    pages.append(page_dict)
                    all_lines.extend(page_dict.get("lines", []))
                    overall_engines.append(page_dict.get("ocr_engine", "hybrid"))
                    if page_dict["text"]:
                        full_text.append(page_dict["text"])
            except Exception as page_err:
                logger.warning(f"Error processing page {page_num} in {path}: {page_err}")
                pages.append({
                    "page_number": page_num,
                    "text": "",
                    "raw_text": "",
                    "ocr_engine": "failed",
                    "line_count": 0,
                    "doc_type": "unknown",
                    "avg_recognition_score": 0.0,
                    "avg_variant_agreement": 0.0,
                    "avg_confidence": 0.0,
                    "flagged_lines_count": 0,
                    "needs_review": True,
                    "segmentation_diagnostics": {},
                    "lines": [],
                    "error": str(page_err)
                })

        joined_text = "\n\n".join(full_text).strip()
        words = joined_text.split()
        status = "completed" if words else ("partial" if pages else "failed")

        total_flags = sum(p.get("flagged_lines_count", 0) for p in pages)
        overall_conf = (
            round(sum(p.get("avg_confidence", 0.0) for p in pages) / max(len(pages), 1), 3)
            if pages else 0.0
        )
        needs_review = any(p.get("needs_review", False) for p in pages) or (total_flags > 0)
        dominant_engine = max(set(overall_engines), key=overall_engines.count) if overall_engines else "pymupdf"

        return {
            "extracted_text": joined_text,
            "raw_text": joined_text,
            "ocr_engine": dominant_engine,
            "confidence": overall_conf,
            "needs_review": needs_review,
            "pages": pages,
            "lines": all_lines,
            "word_count": len(words),
            "status": status,
            "doc_type": pages[0].get("doc_type", "unknown") if pages else "unknown",
            "flagged_lines_count": total_flags
        }

    def _process_pdf_pypdf(self, path: Path) -> Dict[str, Any]:
        import pypdf
        pages = []
        full_text = []
        all_lines = []
        reader = pypdf.PdfReader(str(path), strict=False)

        for idx, page in enumerate(reader.pages):
            page_num = idx + 1
            text = (page.extract_text() or "").strip()
            if len(text) < 20 and hasattr(page, "images") and page.images:
                page_ocr_parts = []
                for img_obj in page.images:
                    try:
                        pil_img = Image.open(io.BytesIO(img_obj.data))
                        p_text, p_dict = _recognize_image_hybrid(pil_img, page_number=page_num)
                        if p_text:
                            page_ocr_parts.append(p_text)
                    except Exception as ex:
                        logger.warning(f"Error in pypdf image OCR: {ex}")
                if page_ocr_parts:
                    text = "\n\n".join(page_ocr_parts).strip()

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            page_lines = [
                {
                    "line_number": i,
                    "page_number": page_num,
                    "raw_text": l,
                    "text": l,
                    "normalized_text": _normalize_for_indexing(l),
                    "recognition_score": 0.88,
                    "variant_agreement": 1.0,
                    "uncertainty_score": 0.12,
                    "confidence": 0.88,
                    "bbox": [0, i * 20, 800, (i + 1) * 20],
                    "center_y": i * 20 + 10,
                    "doc_type": "digital_pdf",
                    "ocr_engine": "pypdf",
                    "flagged_for_review": False,
                    "uncertain_words": [],
                    "candidate_details": None
                }
                for i, l in enumerate(lines, start=1)
            ]
            pages.append({
                "page_number": page_num,
                "text": text,
                "raw_text": text,
                "ocr_engine": "pypdf",
                "line_count": len(lines),
                "doc_type": "digital_pdf",
                "avg_recognition_score": 0.88,
                "avg_variant_agreement": 1.0,
                "avg_confidence": 0.88,
                "flagged_lines_count": 0,
                "needs_review": False,
                "segmentation_diagnostics": {},
                "lines": page_lines
            })
            all_lines.extend(page_lines)
            if text:
                full_text.append(text)

        joined_text = "\n\n".join(full_text).strip()
        words = joined_text.split()
        return {
            "extracted_text": joined_text,
            "raw_text": joined_text,
            "ocr_engine": "pypdf",
            "confidence": 0.88,
            "needs_review": False,
            "pages": pages,
            "lines": all_lines,
            "word_count": len(words),
            "status": "completed" if words else "failed",
            "doc_type": "digital_pdf"
        }

    def _process_pdf_pdfminer(self, path: Path) -> Dict[str, Any]:
        from pdfminer.high_level import extract_text
        text = (extract_text(str(path)) or "").strip()
        words = text.split()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        page_lines = [
            {
                "line_number": i,
                "page_number": 1,
                "raw_text": l,
                "text": l,
                "normalized_text": _normalize_for_indexing(l),
                "recognition_score": 0.90,
                "variant_agreement": 1.0,
                "uncertainty_score": 0.10,
                "confidence": 0.90,
                "bbox": [0, i * 20, 800, (i + 1) * 20],
                "center_y": i * 20 + 10,
                "doc_type": "digital_pdf",
                "ocr_engine": "pdfminer",
                "flagged_for_review": False,
                "uncertain_words": [],
                "candidate_details": None
            }
            for i, l in enumerate(lines, start=1)
        ]
        return {
            "extracted_text": text,
            "raw_text": text,
            "ocr_engine": "pdfminer",
            "confidence": 0.90,
            "needs_review": False,
            "pages": [{
                "page_number": 1,
                "text": text,
                "raw_text": text,
                "ocr_engine": "pdfminer",
                "line_count": len(lines),
                "doc_type": "digital_pdf",
                "avg_recognition_score": 0.90,
                "avg_variant_agreement": 1.0,
                "avg_confidence": 0.90,
                "flagged_lines_count": 0,
                "needs_review": False,
                "segmentation_diagnostics": {},
                "lines": page_lines
            }],
            "lines": page_lines,
            "word_count": len(words),
            "status": "completed" if words else "failed",
            "doc_type": "digital_pdf"
        }

    def _process_docx(self, path: Path) -> Dict[str, Any]:
        doc = docx.Document(str(path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        joined_text = "\n\n".join(paragraphs).strip()
        words = joined_text.split()

        pages = []
        current_page_text = []
        current_words = 0
        page_num = 1
        all_lines = []

        for p in paragraphs:
            w_count = len(p.split())
            current_page_text.append(p)
            current_words += w_count
            if current_words >= 350:
                p_text = "\n\n".join(current_page_text)
                lines_split = [l.strip() for l in p_text.split("\n") if l.strip()]
                p_lines = [
                    {
                        "line_number": i,
                        "page_number": page_num,
                        "raw_text": l,
                        "text": l,
                        "normalized_text": _normalize_for_indexing(l),
                        "recognition_score": 1.0,
                        "variant_agreement": 1.0,
                        "uncertainty_score": 0.0,
                        "confidence": 1.0,
                        "bbox": [0, i * 20, 800, (i + 1) * 20],
                        "center_y": i * 20 + 10,
                        "doc_type": "digital_doc",
                        "ocr_engine": "docx_native",
                        "flagged_for_review": False,
                        "uncertain_words": [],
                        "candidate_details": None
                    }
                    for i, l in enumerate(lines_split, start=1)
                ]
                pages.append({
                    "page_number": page_num,
                    "text": p_text,
                    "raw_text": p_text,
                    "ocr_engine": "docx_native",
                    "line_count": len(lines_split),
                    "doc_type": "digital_doc",
                    "avg_recognition_score": 1.0,
                    "avg_variant_agreement": 1.0,
                    "avg_confidence": 1.0,
                    "flagged_lines_count": 0,
                    "needs_review": False,
                    "segmentation_diagnostics": {},
                    "lines": p_lines
                })
                all_lines.extend(p_lines)
                page_num += 1
                current_page_text = []
                current_words = 0

        if current_page_text or not pages:
            p_text = "\n\n".join(current_page_text)
            lines_split = [l.strip() for l in p_text.split("\n") if l.strip()]
            p_lines = [
                {
                    "line_number": i,
                    "page_number": page_num,
                    "raw_text": l,
                    "text": l,
                    "normalized_text": _normalize_for_indexing(l),
                    "recognition_score": 1.0,
                    "variant_agreement": 1.0,
                    "uncertainty_score": 0.0,
                    "confidence": 1.0,
                    "bbox": [0, i * 20, 800, (i + 1) * 20],
                    "center_y": i * 20 + 10,
                    "doc_type": "digital_doc",
                    "ocr_engine": "docx_native",
                    "flagged_for_review": False,
                    "uncertain_words": [],
                    "candidate_details": None
                }
                for i, l in enumerate(lines_split, start=1)
            ]
            pages.append({
                "page_number": page_num,
                "text": p_text,
                "raw_text": p_text,
                "ocr_engine": "docx_native",
                "line_count": len(lines_split),
                "doc_type": "digital_doc",
                "avg_recognition_score": 1.0,
                "avg_variant_agreement": 1.0,
                "avg_confidence": 1.0,
                "flagged_lines_count": 0,
                "needs_review": False,
                "segmentation_diagnostics": {},
                "lines": p_lines
            })
            all_lines.extend(p_lines)

        return {
            "extracted_text": joined_text,
            "raw_text": joined_text,
            "ocr_engine": "docx_native",
            "confidence": 1.0,
            "needs_review": False,
            "pages": pages,
            "lines": all_lines,
            "word_count": len(words),
            "status": "completed",
            "doc_type": "digital_doc",
            "flagged_lines_count": 0
        }

    def _process_plaintext(self, path: Path) -> Dict[str, Any]:
        content = ""
        for enc in ["utf-8", "latin-1", "cp1252", "ascii"]:
            try:
                with open(path, "r", encoding=enc) as f:
                    content = f.read()
                break
            except Exception:
                continue

        if not content:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

        content = content.strip()
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        words = content.split()
        p_lines = [
            {
                "line_number": i,
                "page_number": 1,
                "raw_text": l,
                "text": l,
                "normalized_text": _normalize_for_indexing(l),
                "recognition_score": 1.0,
                "variant_agreement": 1.0,
                "uncertainty_score": 0.0,
                "confidence": 1.0,
                "bbox": [0, i * 20, 800, (i + 1) * 20],
                "center_y": i * 20 + 10,
                "doc_type": "plain_text",
                "ocr_engine": "text_native",
                "flagged_for_review": False,
                "uncertain_words": [],
                "candidate_details": None
            }
            for i, l in enumerate(lines, start=1)
        ]

        return {
            "extracted_text": content,
            "raw_text": content,
            "ocr_engine": "text_native",
            "confidence": 1.0,
            "needs_review": False,
            "pages": [{
                "page_number": 1,
                "text": content,
                "raw_text": content,
                "ocr_engine": "text_native",
                "line_count": len(lines),
                "doc_type": "plain_text",
                "avg_recognition_score": 1.0,
                "avg_variant_agreement": 1.0,
                "avg_confidence": 1.0,
                "flagged_lines_count": 0,
                "needs_review": False,
                "segmentation_diagnostics": {},
                "lines": p_lines
            }],
            "lines": p_lines,
            "word_count": len(words),
            "status": "completed" if words else "failed",
            "doc_type": "plain_text",
            "flagged_lines_count": 0
        }

    def _process_image(self, path: Path) -> Dict[str, Any]:
        with Image.open(str(path)) as img:
            extracted_text, page_struct = _recognize_image_hybrid(img, page_number=1)

        words = extracted_text.split()

        return {
            "extracted_text": extracted_text,
            "raw_text": page_struct.get("raw_text", extracted_text),
            "ocr_engine": page_struct.get("ocr_engine", "hybrid"),
            "confidence": page_struct.get("avg_confidence", 0.0),
            "needs_review": page_struct.get("needs_review", False),
            "pages": [page_struct],
            "lines": page_struct.get("lines", []),
            "word_count": len(words),
            "status": "completed" if words else "failed",
            "error": None if words else "OCR could not extract any readable text",
            "doc_type": page_struct.get("doc_type", "scanned_printed"),
            "flagged_lines_count": page_struct.get("flagged_lines_count", 0)
        }

ocr_engine = OCREngine()
trocr_engine = _trocr_engine
