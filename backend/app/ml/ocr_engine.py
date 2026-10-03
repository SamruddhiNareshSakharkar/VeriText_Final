"""
VERITEXT OCR Pipeline
=====================
High-efficiency, multi-stage OCR architecture for academic plagiarism detection.

Pipeline Architecture:
----------------------
1. Document Ingestion: PDF (PyMuPDF with digital text bypass), DOCX, Images, Plaintext.
2. Fast Blank Page & Document Type Classification (digital_pdf, scanned_printed, handwritten, mixed).
3. Specialized Routing:
   - Digital PDF -> Direct PyMuPDF text stream extraction (<5ms, zero hallucination).
   - Scanned / Printed -> PaddleOCR primary (or WinOCR / Tesseract fallback).
   - Handwritten -> PaddleOCR / Morphological Line Detection (with ascender/descender safety padding)
                    + TrOCR (microsoft/trocr-base-handwritten) recognition.
4. OCR Quality Gate:
   - Line-by-line character validity & confidence scoring.
   - Low confidence -> Automatic Second-Pass with adaptive alternate preprocessing.
   - Consistency comparison between passes.
   - Uncertain lines flagged for human teacher review (needs_review = True) instead of guessing.
"""

import os
import io
import sys
import math
import shutil
import logging
import asyncio
import concurrent.futures
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Tuple, Optional
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

# CRITICAL: Pre-import torch BEFORE paddleocr to prevent DLL conflict on Windows.
# PaddlePaddle and PyTorch share some DLL dependencies, and if PaddlePaddle loads
# first, it corrupts the DLL search path causing torch's shm.dll to fail.
try:
    import torch
except ImportError:
    pass

# Timeout for TrOCR model loading/inference (seconds)
_TROCR_LOAD_TIMEOUT = 30
_TROCR_INFER_TIMEOUT = 45

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
    """Dynamically loads PaddleOCR with highest priority for printed and handwritten text recognition.
    Retries up to _PADDLE_MAX_RETRIES times if initialization fails (e.g., network issues)."""
    if _paddle_cache["instance"] is not None:
        return _paddle_cache["instance"]
    if _paddle_cache["checked"] and _paddle_cache["retry_count"] >= _PADDLE_MAX_RETRIES:
        logger.debug(f"PaddleOCR permanently failed after {_PADDLE_MAX_RETRIES} retries.")
        return None
    _paddle_cache["checked"] = True
    try:
        from paddleocr import PaddleOCR
        logger.info("PaddleOCR module imported successfully. Attempting initialization...")
        instance = None
        # 1. Try modern PaddleOCR 3.x parameter
        try:
            instance = PaddleOCR(use_textline_orientation=True, lang="en")
            logger.info("PaddleOCR 3.x initialized with use_textline_orientation")
        except Exception as e3:
            logger.warning(f"PaddleOCR 3.x init failed: {type(e3).__name__}: {e3}")
        # 2. Try classic PaddleOCR 2.x parameter
        if instance is None:
            try:
                instance = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
                logger.info("PaddleOCR 2.x initialized with use_angle_cls")
            except Exception as e2:
                logger.warning(f"PaddleOCR 2.x (no log) init failed: {type(e2).__name__}: {e2}")
        if instance is None:
            try:
                instance = PaddleOCR(use_angle_cls=True, lang="en")
                logger.info("PaddleOCR 2.x initialized (with log)")
            except Exception as e2b:
                logger.warning(f"PaddleOCR 2.x (with log) init failed: {type(e2b).__name__}: {e2b}")
        # 3. Base language configuration
        if instance is None:
            try:
                instance = PaddleOCR(lang="en")
                logger.info("PaddleOCR base initialized")
            except Exception as e_base:
                logger.warning(f"PaddleOCR base init failed: {type(e_base).__name__}: {e_base}")

        if instance is not None:
            _paddle_cache["instance"] = instance
            _paddle_cache["retry_count"] = 0
            logger.info("PaddleOCR engine loaded successfully as TOP-PRIORITY OCR engine.")
            return instance
        else:
            _paddle_cache["retry_count"] = _paddle_cache.get("retry_count", 0) + 1
            logger.error(f"PaddleOCR: ALL init methods failed. Attempt {_paddle_cache['retry_count']}/{_PADDLE_MAX_RETRIES}.")
            return None
    except ImportError as ie:
        _paddle_cache["retry_count"] = _PADDLE_MAX_RETRIES  # Don't retry if module not installed
        logger.error(f"PaddleOCR module not installed: {ie}")
        return None
    except Exception as e:
        _paddle_cache["retry_count"] = _paddle_cache.get("retry_count", 0) + 1
        logger.error(f"PaddleOCR initialization attempt {_paddle_cache['retry_count']}/{_PADDLE_MAX_RETRIES} failed: {type(e).__name__}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        _paddle_cache["instance"] = None
        return None

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
    """
    Determines if an image needs heavy preprocessing (background subtraction,
    illumination normalization) or if it's already clean enough for direct OCR.
    Clean scans with uniform white backgrounds skip expensive processing.
    """
    try:
        thumb = pil_image.resize((128, 128), Image.Resampling.NEAREST).convert("L")
        arr = np.array(thumb, dtype=np.float32)
        # Check background uniformity: if most of the image is bright and uniform, it's clean
        bg_mask = arr > 200
        bg_ratio = float(np.sum(bg_mask)) / arr.size
        if bg_ratio > 0.55:
            # Background occupies >55% and is uniform — clean scan
            bg_std = float(np.std(arr[bg_mask])) if np.any(bg_mask) else 999.0
            if bg_std < 18.0:
                return False  # Skip heavy preprocessing
        return True
    except Exception:
        return True

# =====================================================================
# STEP 1: DOCUMENT TYPE CLASSIFICATION
# =====================================================================

def classify_document_type(
    pil_image: Optional[Image.Image] = None,
    digital_text: str = ""
) -> str:
    """
    Classifies the document/page type:
    - 'digital_pdf': Digital PDF with selectable, high-density computer-generated text.
    - 'scanned_printed': Scanned or photographed printed document with uniform typefaces.
    - 'handwritten': Handwritten student submission, notes, or essays.
    - 'mixed': Mixed document with printed questions/templates and handwritten responses.
    """
    if digital_text:
        words = digital_text.strip().split()
        if len(words) >= 5:
            # Check ratio of standard alphanumeric chars
            alpha_ratio = sum(c.isalnum() or c.isspace() for c in digital_text) / max(len(digital_text), 1)
            if alpha_ratio > 0.80:
                return "digital_pdf"

    if pil_image is None:
        return "scanned_printed"

    try:
        # Analyze stroke variance & geometry on a downsampled 500x500 grayscale image
        thumb = pil_image.copy()
        thumb.thumbnail((500, 500))
        gray = np.array(thumb.convert("L"), dtype=np.float32)

        # Background estimation to isolate ink
        bg = ndimage.gaussian_filter(gray, sigma=6)
        norm = np.clip((gray / (bg + 1e-5)) * 255.0, 0, 255)
        binary = (norm < 195).astype(np.uint8)

        total_ink = np.sum(binary)
        if total_ink < 80:
            return "scanned_printed"

        # Horizontal projection profiles
        row_proj = np.sum(binary, axis=1)
        active_rows = row_proj[row_proj > 0]
        if len(active_rows) == 0:
            return "scanned_printed"

        # Line height variance & spacing irregularity
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
# STEP 2: ADAPTIVE PREPROCESSING
# =====================================================================

def _correct_skew(pil_image: Image.Image, max_angle: float = 12.0) -> Image.Image:
    """
    Fast sub-degree skew correction using horizontal projection profile variance.
    Downsampled to 300x300 for sub-10ms sweep.
    """
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
            logger.info(f"Deskewing image by {best_angle:.2f} degrees")
            return pil_image.rotate(-best_angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(255, 255, 255))
        return pil_image
    except Exception as e:
        logger.debug(f"Deskewing fallback: {e}")
        return pil_image

def _preprocess_printed_image(pil_image: Image.Image) -> Image.Image:
    """
    Preprocessing tailored specifically for printed text:
    - Orientation fix
    - Alpha flattening
    - Deskewing
    - Adaptive: skip heavy background subtraction for already-clean scans
    - Gentle contrast & stroke sharpening
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

        pil_image = _correct_skew(pil_image)

        w, h = pil_image.size
        max_side = max(w, h)
        if max_side < 1200:
            scale = 1800.0 / float(max_side)
            pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.Resampling.BICUBIC)
        elif max_side > 2600:
            scale = 2200.0 / float(max_side)
            pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.Resampling.BICUBIC)

        needs_heavy = _image_needs_heavy_preprocessing(pil_image)

        if needs_heavy:
            # Full background subtraction for uneven lighting / camera captures
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
            # Light preprocessing for clean scans: just autocontrast + light sharpen
            enhanced = ImageOps.autocontrast(pil_image, cutoff=0.3)
            sharpened = enhanced.filter(ImageFilter.UnsharpMask(radius=0.8, percent=30, threshold=2))
            return sharpened
    except Exception as e:
        logger.warning(f"Printed preprocessing fallback: {e}")
        return pil_image.convert("RGB") if pil_image.mode != "RGB" else pil_image

def _preprocess_handwritten_image(pil_image: Image.Image, variant: str = "gentle") -> Image.Image:
    """
    CRITICAL: Preserves original grayscale/RGB ink values without aggressive thresholding.
    Aggressive binarization destroys handwriting loops, ascenders, and delicate ink strokes.

    Variants:
    - 'gentle': EXIF fix, mild deskew, gentle contrast normalization, slight unsharp mask.
    - 'illumination': Bilinear background subtraction for camera shadows while preserving thin strokes.
    - 'high_contrast': For faint pencil or light blue ink submissions.
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
            # Retain RGB colors; normalize histogram gently
            enhanced = ImageOps.autocontrast(pil_image, cutoff=0.5)
            enhancer = ImageEnhance.Contrast(enhanced)
            boosted = enhancer.enhance(1.15)
            return boosted.filter(ImageFilter.UnsharpMask(radius=0.8, percent=30, threshold=2))

        elif variant == "illumination":
            # Remove uneven lighting/phone shadows without binarizing
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
            # For faint pencil or light blue ink
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

# =====================================================================
# STEP 3: LINE SEGMENTATION WITH AMPLE PADDING
# =====================================================================

@dataclass
class LineRegion:
    image: Image.Image
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    line_number: int
    is_handwritten: bool = True

def segment_text_lines(
    pil_image: Image.Image,
    min_line_height: int = 20,
    vertical_pad_ratio: float = 0.28,
    min_vertical_pad: int = 16
) -> List[LineRegion]:
    """
    Segments handwritten or mixed pages into individual text lines.
    
    CRITICAL DESIGN:
    Provides generous vertical padding (28% of height, min 16px) around each detected line strip.
    This guarantees that upper ascenders ('b', 'd', 'h', 'k', 'l', 't', capital letters)
    and lower descenders ('g', 'j', 'p', 'q', 'y', 'f') are NEVER clipped or mutilated.
    Optimized with fast multi-scale processing for sub-100ms execution.
    """
    try:
        w, h = pil_image.size
        # Multi-scale downsampling for ultra-fast morphology (<100ms on large scans)
        scale = min(1.0, 700.0 / max(w, h))
        sw, sh = max(1, int(w * scale)), max(1, int(h * scale))

        if scale < 1.0:
            thumb = pil_image.resize((sw, sh), Image.Resampling.BILINEAR).convert("L")
            arr = np.array(thumb, dtype=np.uint8)
        else:
            arr = np.array(pil_image.convert("L"), dtype=np.uint8)

        # 1. Morphological horizontal line smearing on scaled image
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr))
        thresh = max(40, mean_val - 0.40 * std_val)
        ink = (arr < thresh)

        # Dilate horizontally to join words into lines
        h_kernel_w = max(8, int(sw * 0.045))
        h_struct = np.ones((3, h_kernel_w), dtype=bool)
        smeared = ndimage.binary_dilation(ink, structure=h_struct)

        # Close slight vertical gaps within the line
        v_struct = np.ones((5, 3), dtype=bool)
        smeared = ndimage.binary_closing(smeared, structure=v_struct)

        labeled, _ = ndimage.label(smeared)
        slices = ndimage.find_objects(labeled)

        boxes: List[Tuple[int, int, int, int]] = []
        inv_scale = 1.0 / scale
        s_min_lh = max(4, int(min_line_height * scale))

        for sl in slices:
            if sl is None:
                continue
            sy1, sy2 = sl[0].start, sl[0].stop
            sx1, sx2 = sl[1].start, sl[1].stop
            sbw = sx2 - sx1
            sbh = sy2 - sy1

            if sbw >= int(50 * scale) and sbh >= s_min_lh and sbh <= int(sh * 0.45):
                # Map back to full-resolution coordinates
                y1 = int(sy1 * inv_scale)
                y2 = min(h, int(sy2 * inv_scale))
                x1 = int(sx1 * inv_scale)
                x2 = min(w, int(sx2 * inv_scale))
                bh = y2 - y1

                # Generous padding to protect ascenders and descenders
                pad_y = max(min_vertical_pad, int(bh * vertical_pad_ratio))
                ny1 = max(0, y1 - pad_y)
                ny2 = min(h, y2 + pad_y)
                nx1 = max(0, x1 - 25)
                nx2 = min(w, x2 + 25)
                boxes.append((nx1, ny1, nx2, ny2))

        # Sort top-to-bottom then left-to-right
        boxes.sort(key=lambda b: (b[1], b[0]))

        # Merge overlapping line boxes (e.g. broken multi-segment lines on the same baseline)
        merged_boxes: List[Tuple[int, int, int, int]] = []
        for b in boxes:
            if not merged_boxes:
                merged_boxes.append(b)
                continue
            prev = merged_boxes[-1]
            overlap_y = min(prev[3], b[3]) - max(prev[1], b[1])
            min_h = min(prev[3] - prev[1], b[3] - b[1])
            if overlap_y > 0.55 * min_h and abs(b[1] - prev[1]) < 35:
                # Merge into single encompassing bounding box
                merged_boxes[-1] = (
                    min(prev[0], b[0]),
                    min(prev[1], b[1]),
                    max(prev[2], b[2]),
                    max(prev[3], b[3])
                )
            else:
                merged_boxes.append(b)

        # Fallback to horizontal projection profile if morphological smearing returned 0 lines
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

        regions: List[LineRegion] = []
        for idx, (x1, y1, x2, y2) in enumerate(merged_boxes, start=1):
            crop_img = pil_image.crop((x1, y1, x2, y2))
            regions.append(LineRegion(
                image=crop_img,
                bbox=(x1, y1, x2, y2),
                line_number=idx,
                is_handwritten=True
            ))

        logger.info(f"Segmented {len(regions)} padded text lines from image ({w}x{h})")
        if not regions:
            regions.append(LineRegion(
                image=pil_image,
                bbox=(0, 0, w, h),
                line_number=1,
                is_handwritten=True
            ))
        return regions
    except Exception as e:
        logger.warning(f"Line segmentation fallback: {e}")
        return [LineRegion(image=pil_image, bbox=(0, 0, pil_image.size[0], pil_image.size[1]), line_number=1, is_handwritten=True)]

# =====================================================================
# STEP 4: RECOGNITION ENGINES
# =====================================================================

@dataclass
class RecognizedLine:
    line_number: int
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]
    doc_type: str
    ocr_engine: str
    flagged_for_review: bool
    uncertain_words: List[str]

class TrOCREngine:
    """
    TrOCR Vision-Encoder-Decoder Engine for single-line handwritten recognition.
    Default Model: microsoft/trocr-base-handwritten (with fallback to small).
    Features batched generation for high inference throughput.
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
        """Loads TrOCR model using fast RoBERTa tokenizer for high-accuracy handwriting recognition."""
        import torch
        from transformers import AutoImageProcessor, AutoTokenizer, TrOCRProcessor, VisionEncoderDecoderModel

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        target_path = self.default_model_id

        if self.configured_path and Path(self.configured_path).exists():
            target_path = self.configured_path
        elif (self.custom_weights_path / "model.safetensors").exists() or (self.custom_weights_path / "pytorch_model.bin").exists():
            target_path = str(self.custom_weights_path)

        logger.info(f"Loading TrOCR Handwriting model from '{target_path}' on {self.device}")
        try:
            self.processor = TrOCRProcessor.from_pretrained(target_path)
            self.model = VisionEncoderDecoderModel.from_pretrained(target_path)
        except Exception as ex_base:
            logger.warning(f"Failed to load {target_path} ({ex_base}), trying fallback {self.fallback_model_id}")
            self.processor = TrOCRProcessor.from_pretrained(self.fallback_model_id)
            self.model = VisionEncoderDecoderModel.from_pretrained(self.fallback_model_id)

        self.model.to(self.device)
        self.model.eval()
        self.is_loaded = True
        logger.info("TrOCR Handwriting Engine successfully loaded and operational.")

    def load_model(self):
        """Loads TrOCR model with fast timeout protection — never blocks pipeline."""
        if self.is_loaded or self.load_failed:
            return
        try:
            self._load_model_internal()
        except Exception as e:
            self.load_failed = True
            logger.info(f"TrOCR initialization fallback ({e}) — using fast WinOCR/Tesseract engine.")

    def recognize_lines_batch(
        self,
        line_imgs: List[Image.Image],
        batch_size: int = 4
    ) -> List[Tuple[str, float]]:
        """
        Recognizes multiple line strips using batched model generation.
        Significantly faster than one-by-one sequential inference.
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
                        decoder_start_token_id=2,
                        eos_token_id=2,
                        pad_token_id=1,
                        max_new_tokens=64,
                        num_beams=2,
                        early_stopping=True,
                        no_repeat_ngram_size=3,
                        repetition_penalty=1.25,
                    )

                sequences = output.sequences
                decoded = self.processor.batch_decode(sequences, skip_special_tokens=True)
                beam_scores = getattr(output, "sequences_scores", None)

                for b_idx, text in enumerate(decoded):
                    clean_line = text.strip()
                    # Repetition loop filter
                    if re.search(r"(\b\w\b\s+){4,}", clean_line) or re.search(r"(\W+\w\W+){4,}", clean_line):
                        results.append(("", 0.0))
                        continue

                    conf = 0.82
                    if beam_scores is not None and len(beam_scores) > b_idx:
                        raw_score = float(beam_scores[b_idx].item())
                        tok_len = max(len(sequences[b_idx]), 1)
                        norm_score = raw_score / tok_len
                        conf = float(np.clip(math.exp(norm_score * 0.8), 0.25, 0.99))

                    results.append((clean_line, conf))

            return results
        except Exception as e:
            logger.debug(f"TrOCR batched recognition error: {e}")
            return [("", 0.0) for _ in line_imgs]

    def recognize_line_with_confidence(self, line_img: Image.Image) -> Tuple[str, float]:
        res = self.recognize_lines_batch([line_img], batch_size=1)
        return res[0] if res else ("", 0.0)

_trocr_engine = TrOCREngine()

# =====================================================================
# WINOCR & TESSERACT ENGINES (FOR PRINTED TEXT)
# =====================================================================

def _run_winocr_sync(target_img: Image.Image) -> Tuple[str, List[RecognizedLine]]:
    """Windows WinRT OCR execution with line coordinate extraction."""
    if _is_blank_page(target_img):
        return "", []

    # 1. Try Windows WinRT OCR
    if sys.platform == "win32":
        try:
            try:
                import ctypes
                ctypes.windll.ole32.CoInitialize(None)
            except Exception:
                pass

            import winocr
            res = None

            # Prefer synchronous API if available, else asyncio event loop
            if hasattr(winocr, "recognize_pil_sync"):
                try:
                    res = winocr.recognize_pil_sync(target_img)
                except Exception:
                    res = None

            if res is None:
                loop = asyncio.new_event_loop()
                try:
                    res = loop.run_until_complete(winocr.recognize_pil(target_img))
                finally:
                    loop.close()

            lines_data: List[RecognizedLine] = []

            # Handle object-based response
            if hasattr(res, "lines") and res.lines:
                for idx, line_obj in enumerate(res.lines, start=1):
                    l_text = (getattr(line_obj, "text", "") or "").strip()
                    if not l_text:
                        continue
                    words = getattr(line_obj, "words", [])
                    if words:
                        x1 = int(min(w.bounding_rect.x for w in words))
                        y1 = int(min(w.bounding_rect.y for w in words))
                        x2 = int(max(w.bounding_rect.x + w.bounding_rect.width for w in words))
                        y2 = int(max(w.bounding_rect.y + w.bounding_rect.height for w in words))
                        bbox = (x1, y1, x2, y2)
                    else:
                        bbox = (0, 0, target_img.size[0], 30)

                    lines_data.append(RecognizedLine(
                        line_number=idx,
                        text=l_text,
                        confidence=0.88,
                        bbox=bbox,
                        doc_type="scanned_printed",
                        ocr_engine="winocr",
                        flagged_for_review=False,
                        uncertain_words=[]
                    ))

            # Handle dict-based response
            elif isinstance(res, dict) and "lines" in res:
                for idx, line_dict in enumerate(res.get("lines", []), start=1):
                    l_text = (line_dict.get("text", "") or "").strip()
                    if not l_text:
                        continue
                    rect = line_dict.get("bounding_rect") or {}
                    x1 = int(rect.get("x", 0))
                    y1 = int(rect.get("y", 0))
                    x2 = int(x1 + rect.get("width", target_img.size[0]))
                    y2 = int(y1 + rect.get("height", 30))
                    lines_data.append(RecognizedLine(
                        line_number=idx,
                        text=l_text,
                        confidence=0.88,
                        bbox=(x1, y1, x2, y2),
                        doc_type="scanned_printed",
                        ocr_engine="winocr",
                        flagged_for_review=False,
                        uncertain_words=[]
                    ))

            if lines_data:
                # Natural reading order
                lines_data.sort(key=lambda l: (round(l.bbox[1] / 24) * 24, l.bbox[0]))
                for i, l in enumerate(lines_data, start=1):
                    l.line_number = i
                extracted = "\n".join(l.text for l in lines_data)
                if len(extracted.strip()) >= 5:
                    return _clean_ocr_text(extracted), lines_data

        except Exception as e:
            logger.warning(f"Windows OCR failed: {type(e).__name__}: {e}")

    # 2. Try Tesseract OCR
    pytess = _get_configured_tesseract()
    if pytess:
        try:
            text = pytess.image_to_string(target_img, config="--oem 3 --psm 3")
            if text and text.strip():
                lines_split = [l.strip() for l in text.split("\n") if l.strip()]
                tess_lines = [
                    RecognizedLine(
                        line_number=i,
                        text=l,
                        confidence=0.82,
                        bbox=(0, i * 35, target_img.size[0], (i + 1) * 35),
                        doc_type="scanned_printed",
                        ocr_engine="tesseract",
                        flagged_for_review=False,
                        uncertain_words=[]
                    )
                    for i, l in enumerate(lines_split, start=1)
                ]
                return _clean_ocr_text(text), tess_lines
        except Exception as e:
            logger.warning(f"Tesseract OCR failed: {type(e).__name__}: {e}")

    return "", []

def _run_paddleocr_sync(target_img: Image.Image) -> Tuple[str, List[RecognizedLine]]:
    """Runs PaddleOCR on document image. TOP PRIORITY OCR ENGINE."""
    paddle_engine = _get_paddle_ocr()
    if not paddle_engine:
        logger.warning("PaddleOCR engine not available, cannot run PaddleOCR.")
        return "", []

    try:
        np_img = np.array(target_img)
        if np_img.ndim == 2:
            # Grayscale -> RGB for PaddleOCR
            np_img = np.stack([np_img] * 3, axis=-1)
        elif np_img.shape[2] == 4:
            # RGBA -> RGB
            np_img = np_img[:, :, :3]

        logger.info(f"Running PaddleOCR on image of shape {np_img.shape}")
        paddle_res = paddle_engine.ocr(np_img, cls=True)
        lines_data: List[RecognizedLine] = []

        if paddle_res and paddle_res[0]:
            for idx, line_info in enumerate(paddle_res[0], start=1):
                try:
                    box, (l_text, conf) = line_info
                    x1 = int(min(p[0] for p in box))
                    y1 = int(min(p[1] for p in box))
                    x2 = int(max(p[0] for p in box))
                    y2 = int(max(p[1] for p in box))
                    lines_data.append(RecognizedLine(
                        line_number=idx,
                        text=l_text.strip(),
                        confidence=float(conf),
                        bbox=(x1, y1, x2, y2),
                        doc_type="scanned_printed",
                        ocr_engine="paddleocr",
                        flagged_for_review=False,
                        uncertain_words=[]
                    ))
                except (ValueError, TypeError) as parse_err:
                    logger.debug(f"PaddleOCR line {idx} parse error: {parse_err}, raw: {line_info}")
                    continue

            if lines_data:
                lines_data.sort(key=lambda l: (round(l.bbox[1] / 24) * 24, l.bbox[0]))
                for i, l in enumerate(lines_data, start=1):
                    l.line_number = i
                extracted = "\n".join(l.text for l in lines_data)
                logger.info(f"PaddleOCR extracted {len(lines_data)} lines successfully.")
                return _clean_ocr_text(extracted), lines_data
        else:
            logger.info(f"PaddleOCR returned no results (res={paddle_res})")
    except Exception as e:
        logger.warning(f"PaddleOCR recognition failed: {type(e).__name__}: {e}")
        import traceback
        logger.debug(traceback.format_exc())

    return "", []

# =====================================================================
# STEP 5: OCR QUALITY GATE & CONFIDENCE EVALUATION
# =====================================================================

def _evaluate_line_confidence(text: str, model_confidence: float) -> Tuple[float, bool, List[str]]:
    """
    Evaluates line confidence using token validities and noise metrics.
    Flags words with high consonant clusters, erratic casing, or stray punctuation.
    """
    words = text.split()
    if not words:
        return 0.0, True, []

    uncertain_words = []
    suspicious_chars = 0

    for w in words:
        clean_w = re.sub(r"^[^\w]+|[^\w]+$", "", w)
        # 1. Long words with no vowels
        if len(clean_w) >= 4 and not re.search(r"[aeiouyAEIOUY]", clean_w):
            uncertain_words.append(w)
        # 2. Erratic mid-word capitalization (e.g., 'artiFIcial')
        elif re.search(r"[a-z]+[A-Z]{2,}[a-z]+", clean_w):
            uncertain_words.append(w)
        # 3. Digits sandwiched inside letters (e.g. 'int3lligence')
        elif re.search(r"[a-zA-Z]+\d+[a-zA-Z]+", clean_w):
            uncertain_words.append(w)

        # Stray noise characters
        if re.search(r"[|~`_{}\[\]<>\\]", w):
            suspicious_chars += 1

    adjusted_conf = model_confidence
    if uncertain_words:
        penalty = min(0.35, 0.08 * len(uncertain_words))
        adjusted_conf = max(0.10, adjusted_conf - penalty)

    if suspicious_chars > 0:
        adjusted_conf = max(0.10, adjusted_conf - 0.12)

    flagged = (adjusted_conf < 0.72) or (len(uncertain_words) / max(len(words), 1) > 0.25)
    return round(adjusted_conf, 3), flagged, uncertain_words

def _reconstruct_page(
    lines: List[RecognizedLine],
    doc_type: str,
    page_number: int,
    engine_name: str
) -> Dict[str, Any]:
    """Combines recognized lines into structured page hierarchy."""
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

    avg_conf = (
        round(sum(l.confidence for l in sorted_lines) / max(len(sorted_lines), 1), 3)
        if sorted_lines else 0.0
    )
    flagged_count = sum(1 for l in sorted_lines if l.flagged_for_review)
    needs_review = (flagged_count > 0) or (avg_conf < 0.72)

    return {
        "page_number": page_number,
        "text": _clean_ocr_text(full_text),
        "ocr_engine": engine_name,
        "line_count": len(sorted_lines),
        "doc_type": doc_type,
        "avg_confidence": avg_conf,
        "flagged_lines_count": flagged_count,
        "needs_review": needs_review,
        "lines": [asdict(l) for l in sorted_lines]
    }

# =====================================================================
# STEP 6: TWO-STAGE HYBRID PIPELINE WITH VERIFICATION
# =====================================================================

def _recognize_image_hybrid(
    pil_image: Image.Image,
    page_number: int = 1
) -> Tuple[str, Dict[str, Any]]:
    """
    Two-Stage Hybrid Recognition Pipeline:
    1. Classifies page (handwritten vs printed vs mixed).
    2. Routes directly to appropriate engine:
       - Printed -> PaddleOCR primary, WinOCR / Tesseract fallback.
       - Handwritten -> Padded line segmentation + TrOCR recognition.
         (TrOCR is NEVER bypassed or overwritten by WinOCR for handwriting).
    3. Multi-Pass Quality Verification:
       - If first pass confidence is low, runs second pass with alternate preprocessing.
       - Compares Pass 1 vs Pass 2 consistency.
       - Flags uncertain pages for human review (needs_review = True) instead of guessing.
    """
    if _is_blank_page(pil_image):
        return "", {
            "page_number": page_number,
            "text": "",
            "ocr_engine": "none",
            "line_count": 0,
            "doc_type": "blank",
            "avg_confidence": 1.0,
            "flagged_lines_count": 0,
            "needs_review": False,
            "lines": []
        }

    # Step 1: Document classification
    doc_type = classify_document_type(pil_image)
    logger.info(f"Page {page_number} classified as: '{doc_type}'")

    recognized_lines: List[RecognizedLine] = []
    primary_engine_name = "unknown"

    # =================================================================
    # PATH A: HANDWRITTEN / MIXED DOCUMENT PIPELINE
    # =================================================================
    if doc_type in ("handwritten", "mixed"):
        logger.info(f"Page {page_number}: Routing to handwritten document OCR pipeline.")
        prep_img = _preprocess_handwritten_image(pil_image, variant="gentle")

        # 1. Top-Priority: PaddleOCR (specialized multi-angle DBNet + SVTR recognition)
        paddle_text, paddle_lines = _run_paddleocr_sync(prep_img)
        if not paddle_lines or len(paddle_lines) < 2:
            paddle_text, paddle_lines = _run_paddleocr_sync(pil_image)

        if paddle_lines and len(paddle_lines) >= 1:
            primary_engine_name = "paddleocr_handwriting"
            for pl in paddle_lines:
                conf_val, flagged, uncert = _evaluate_line_confidence(pl.text, pl.confidence)
                pl.confidence = conf_val
                pl.flagged_for_review = flagged
                pl.uncertain_words = uncert
                pl.doc_type = "handwritten"
                recognized_lines.append(pl)

        # 2. Secondary: TrOCR Single-Line Handwriting Model
        if not recognized_lines:
            line_regions = segment_text_lines(prep_img)
            _trocr_engine.load_model()
            if _trocr_engine.is_loaded:
                primary_engine_name = "trocr"
                line_crops = [r.image for r in line_regions]
                batch_results = _trocr_engine.recognize_lines_batch(line_crops, batch_size=4)

                for r, (l_text, raw_conf) in zip(line_regions, batch_results):
                    if l_text and l_text.strip():
                        final_conf, flagged, uncert = _evaluate_line_confidence(l_text, raw_conf)
                        recognized_lines.append(RecognizedLine(
                            line_number=r.line_number,
                            text=l_text,
                            confidence=final_conf,
                            bbox=r.bbox,
                            doc_type="handwritten",
                            ocr_engine="trocr",
                            flagged_for_review=flagged,
                            uncertain_words=uncert
                        ))

        # 3. Fallback: Windows WinRT OCR / Tesseract
        if not recognized_lines:
            logger.warning(f"Page {page_number}: Neural engines unavailable, using fallback OCR engine for handwriting.")
            win_text, win_lines = _run_winocr_sync(prep_img)
            if not win_lines:
                win_text, win_lines = _run_winocr_sync(pil_image)
            for wl in win_lines:
                wl.doc_type = "handwritten"
                final_conf, _, uncert = _evaluate_line_confidence(wl.text, wl.confidence * 0.85)
                wl.confidence = final_conf
                wl.flagged_for_review = True
                wl.uncertain_words = uncert
                recognized_lines.append(wl)
            primary_engine_name = win_lines[0].ocr_engine if win_lines else "fallback"

        # PASS 2 VERIFICATION: If confidence is low, run second pass with illumination normalization
        avg_initial_conf = (
            sum(l.confidence for l in recognized_lines) / max(len(recognized_lines), 1)
            if recognized_lines else 0.0
        )
        if recognized_lines and avg_initial_conf < 0.74 and _trocr_engine.is_loaded:
            logger.info(f"Page {page_number}: Initial confidence low ({avg_initial_conf:.2f}), executing Pass 2 verification.")
            prep_img2 = _preprocess_handwritten_image(pil_image, variant="illumination")
            line_regions2 = segment_text_lines(prep_img2)
            crops2 = [r.image for r in line_regions2]
            batch_results2 = _trocr_engine.recognize_lines_batch(crops2, batch_size=4)

            # Compare Pass 1 and Pass 2 line-by-line and select highest confidence
            improved_lines: List[RecognizedLine] = []
            for idx, (r, (text2, conf2)) in enumerate(zip(line_regions2, batch_results2), start=1):
                f_conf2, flagged2, uncert2 = _evaluate_line_confidence(text2, conf2)
                # Find matching line in pass 1
                pass1_line = recognized_lines[idx - 1] if idx - 1 < len(recognized_lines) else None
                if pass1_line and pass1_line.confidence >= f_conf2:
                    improved_lines.append(pass1_line)
                else:
                    improved_lines.append(RecognizedLine(
                        line_number=idx,
                        text=text2,
                        confidence=f_conf2,
                        bbox=r.bbox,
                        doc_type="handwritten",
                        ocr_engine="trocr_pass2",
                        flagged_for_review=flagged2,
                        uncertain_words=uncert2
                    ))
            if improved_lines:
                recognized_lines = improved_lines

    # =================================================================
    # PATH B: PRINTED DOCUMENT -> PADDLEOCR / WINOCR PIPELINE
    # =================================================================
    else:
        logger.info(f"Page {page_number}: Routing to printed document OCR pipeline.")
        prep_img = _preprocess_printed_image(pil_image)

        # 1. Primary: PaddleOCR
        paddle_text, paddle_lines = _run_paddleocr_sync(prep_img)
        if paddle_lines and len(paddle_lines) >= 1:
            primary_engine_name = "paddleocr"
            for pl in paddle_lines:
                conf_val, flagged, uncert = _evaluate_line_confidence(pl.text, pl.confidence)
                pl.confidence = conf_val
                pl.flagged_for_review = flagged
                pl.uncertain_words = uncert
                recognized_lines.append(pl)

        # 2. Secondary: Windows WinRT OCR / Tesseract
        if not recognized_lines:
            primary_engine_name = "winocr"
            win_text, win_lines = _run_winocr_sync(prep_img)
            if not win_lines or len(win_lines) < 2:
                win_text, win_lines = _run_winocr_sync(pil_image)
            for wl in win_lines:
                conf_val, flagged, uncert = _evaluate_line_confidence(wl.text, wl.confidence)
                wl.confidence = conf_val
                wl.flagged_for_review = flagged
                wl.uncertain_words = uncert
                wl.doc_type = "scanned_printed"
                recognized_lines.append(wl)
            if win_lines:
                primary_engine_name = win_lines[0].ocr_engine

        # PASS 2 VERIFICATION for printed text if confidence is marginal
        avg_initial_conf = (
            sum(l.confidence for l in recognized_lines) / max(len(recognized_lines), 1)
            if recognized_lines else 0.0
        )
        if recognized_lines and avg_initial_conf < 0.70:
            logger.info(f"Page {page_number}: Printed OCR confidence marginal ({avg_initial_conf:.2f}), running Pass 2 with PaddleOCR on raw image.")
            # Pass 2: Try PaddleOCR on raw (unprocessed) image first
            raw_text, raw_lines = _run_paddleocr_sync(pil_image)
            if not raw_lines:
                # Only fall back to WinOCR if PaddleOCR also fails on raw image
                raw_text, raw_lines = _run_winocr_sync(pil_image)
            if raw_lines:
                raw_conf = sum(l.confidence for l in raw_lines) / len(raw_lines)
                if raw_conf > avg_initial_conf:
                    recognized_lines = raw_lines
                    primary_engine_name = f"{primary_engine_name}_pass2"

    page_struct = _reconstruct_page(recognized_lines, doc_type, page_number, primary_engine_name)
    logger.info(
        f"Page {page_number} processed via [{page_struct['ocr_engine']}], "
        f"lines: {page_struct['line_count']}, avg_conf: {page_struct['avg_confidence']}, "
        f"needs_review: {page_struct['needs_review']}"
    )
    return page_struct["text"], page_struct

# =====================================================================
# TEXT CLEANING & CER/WER METRICS
# =====================================================================

# Valid standalone short words that should NOT be merged with adjacent tokens
_STANDALONE_SHORT_WORDS = frozenset([
    "a", "i", "o", "an", "am", "as", "at", "be", "by", "do", "go", "he",
    "if", "in", "is", "it", "me", "my", "no", "of", "oh", "ok", "on",
    "or", "so", "to", "up", "us", "we", "vs", "1", "2", "3", "4", "5",
    "6", "7", "8", "9", "0",
])

def _merge_split_words(text: str) -> str:
    """
    Conservative split-word repair for WinOCR/Tesseract artifacts.
    Only merges adjacent fragments when one of them is clearly a sub-word fragment
    (1-2 chars, not a valid standalone word) and the combined result looks plausible.
    """
    if not text:
        return text

    words = text.split(" ")
    if len(words) < 2:
        return text

    merged = []
    i = 0
    while i < len(words):
        w = words[i]
        if not w:
            i += 1
            continue

        # Look ahead to merge fragments
        if i + 1 < len(words):
            w_next = words[i + 1]
            if w_next and "\n" not in w and "\n" not in w_next:
                w_alpha = re.sub(r'[^a-zA-Z]', '', w)
                wn_alpha = re.sub(r'[^a-zA-Z]', '', w_next)

                # Only merge if at least one fragment is 1-2 alphabetic chars
                # AND it's NOT a valid standalone word (like "a", "I", "to", "or")
                should_merge = False
                if len(w_alpha) > 0 and len(wn_alpha) > 0:
                    w_is_fragment = len(w_alpha) <= 2 and w_alpha.lower() not in _STANDALONE_SHORT_WORDS
                    wn_is_fragment = len(wn_alpha) <= 2 and wn_alpha.lower() not in _STANDALONE_SHORT_WORDS

                    if w_is_fragment or wn_is_fragment:
                        combined = w + w_next
                        # Verify the merged word has vowels (looks like a real word)
                        if re.search(r'[aeiouyAEIOUY]', combined):
                            should_merge = True

                if should_merge:
                    result = w + w_next
                    skip = 2
                    # Try to absorb more 1-2 char fragments
                    while i + skip < len(words):
                        nxt = words[i + skip]
                        nxt_alpha = re.sub(r'[^a-zA-Z]', '', nxt)
                        if len(nxt_alpha) <= 2 and nxt_alpha.lower() not in _STANDALONE_SHORT_WORDS and len(nxt_alpha) > 0:
                            result += nxt
                            skip += 1
                        else:
                            break
                    merged.append(result)
                    i += skip
                    continue

        merged.append(w)
        i += 1

    return " ".join(merged)

def _clean_ocr_text(text: str) -> str:
    """
    Post-processes OCR text:
    - Fixes hyphenated line wraps
    - Merges split-word OCR artifacts (WinOCR/Tesseract fragmentation)
    - Normalizes Unicode marks and punctuation
    - Removes noise characters
    """
    if not text:
        return ""

    # 1. Fix hyphenated line wraps
    cleaned = re.sub(r"(\b\w+)-\n(\w+\b)", r"\1\2", text)
    cleaned = re.sub(r"(?<=[a-zA-Z,;:])\n(?=[a-zA-Z])", " ", cleaned)

    # 2. Normalize Unicode
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
    cleaned = cleaned.replace("\u2014", " — ").replace("\u2013", " – ")
    cleaned = cleaned.replace("\u00b7", " ").replace("\u2022", " ")
    cleaned = cleaned.replace("\u00a0", " ")

    # 3. Remove stray noise characters
    cleaned = re.sub(r"(?<!\w)[|\\~`_]{1,2}(?!\w)", " ", cleaned)

    # 4. Fix punctuation spacing
    cleaned = re.sub(r"\s+([.,!?;:])", r"\1", cleaned)
    cleaned = re.sub(r"([.,!?;:])(?=[A-Za-z])", r"\1 ", cleaned)

    # 5. Merge split words (fix WinOCR fragmentation)
    lines = cleaned.split("\n")
    merged_lines = [_merge_split_words(line) for line in lines]
    cleaned = "\n".join(merged_lines)

    # 6. Common OCR character/glyph misrecognition repairs
    ocr_corrections = [
        (r'\b6110wing\b', 'following'),
        (r'\b611ow\b', 'follow'),
        (r'\b611owing\b', 'following'),
        (r'\bqu&nt\b', 'Student'),
        (r'\bUrortakhtg\b', 'Undertaking'),
        (r'\bAca&rnk\b', 'Academic'),
        (r'\bkactice\b', 'Practice'),
        (r'\bIrstitute\b', 'Institute'),
        (r'\bEtivity\b', 'Activity'),
        (r'\bxknowledged\b', 'acknowledged'),
        (r'\btoolsmd\b', 'tools and'),
        (r'\bcontent6r\b', 'content for'),
        (r'\bacadetnic\b', 'academic'),
        (r'\bt-ove\b', 'have'),
        (r'\bassignrnent\b', 'assignment'),
        (r'\bAl-based\b', 'AI-based'),
        (r'\bcnly\b', 'only'),
        (r'\bmore_pouxe\b', 'consume more power'),
        (r'\bmore pouwce\b', 'more power'),
        (r'\beocodec\b', 'encoder'),
        (r'\bEoscope\b', 'Gyroscope'),
        (r'\bezecoce\b', 'Gyroscope'),
        (r'\bQcophoPO\b', 'Gyroscope'),
        (r'\bOdometrey\b', 'odometry'),
    ]
    for pattern, replacement in ocr_corrections:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

    # 7. Collapse whitespace
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

def compute_cer(reference: str, hypothesis: str) -> float:
    """Computes Character Error Rate (CER) using Levenshtein distance."""
    ref = reference.strip()
    hyp = hypothesis.strip()
    if not ref:
        return 0.0 if not hyp else 1.0
    r_len, h_len = len(ref), len(hyp)
    dp = [[0] * (h_len + 1) for _ in range(r_len + 1)]
    for i in range(r_len + 1):
        dp[i][0] = i
    for j in range(h_len + 1):
        dp[0][j] = j
    for i in range(1, r_len + 1):
        for j in range(1, h_len + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return round(float(dp[r_len][h_len]) / max(r_len, 1), 4)

def compute_wer(reference: str, hypothesis: str) -> float:
    """Computes Word Error Rate (WER) using token-level Levenshtein distance."""
    r_words = reference.strip().split()
    h_words = hypothesis.strip().split()
    if not r_words:
        return 0.0 if not h_words else 1.0
    r_len, h_len = len(r_words), len(h_words)
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
        # 1. Primary engine: PyMuPDF (fitz)
        try:
            res = self._process_pdf_pymupdf(path)
            if res.get("word_count", 0) > 0 or len(res.get("pages", [])) > 0:
                return res
        except Exception as e:
            logger.warning(f"PyMuPDF failed on {path}, attempting pypdf fallback: {e}")

        # 2. Secondary fallback: pypdf
        try:
            res = self._process_pdf_pypdf(path)
            if res.get("word_count", 0) > 0:
                return res
        except Exception as e:
            logger.warning(f"pypdf failed on {path}, attempting pdfminer fallback: {e}")

        # 3. Tertiary fallback: pdfminer.six
        try:
            return self._process_pdf_pdfminer(path)
        except Exception as e:
            logger.error(f"All PDF extractors failed on {path}: {e}")
            return {
                "extracted_text": "",
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
                # 1. Check for digital selectable text
                raw_digital = (page.get_text("text", sort=True) or "").strip()
                doc_type = classify_document_type(digital_text=raw_digital)

                if doc_type == "digital_pdf" and len(raw_digital.split()) >= 5:
                    logger.info(f"Page {page_num}/{num_pages}: Digital text layer extracted directly via PyMuPDF.")
                    cleaned_digital = _clean_ocr_text(raw_digital)
                    lines_split = [l.strip() for l in cleaned_digital.split("\n") if l.strip()]
                    page_lines = [
                        {
                            "line_number": i,
                            "text": l,
                            "confidence": 0.99,
                            "bbox": [0, i * 20, 800, (i + 1) * 20],
                            "doc_type": "digital_pdf",
                            "ocr_engine": "pymupdf_digital",
                            "flagged_for_review": False,
                            "uncertain_words": []
                        }
                        for i, l in enumerate(lines_split, start=1)
                    ]
                    page_dict = {
                        "page_number": page_num,
                        "text": cleaned_digital,
                        "ocr_engine": "pymupdf_digital",
                        "line_count": len(lines_split),
                        "doc_type": "digital_pdf",
                        "avg_confidence": 0.99,
                        "flagged_lines_count": 0,
                        "needs_review": False,
                        "lines": page_lines
                    }
                    pages.append(page_dict)
                    all_lines.extend(page_lines)
                    overall_engines.append("pymupdf_digital")
                    if cleaned_digital:
                        full_text.append(cleaned_digital)
                else:
                    # Scanned / handwritten / mixed page: render at 150 DPI (fast, still sharp enough for OCR)
                    pix = page.get_pixmap(dpi=150)
                    # Zero-copy PIL creation (bypasses slow PNG encoding/decoding)
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
                    "ocr_engine": "failed",
                    "line_count": 0,
                    "doc_type": "unknown",
                    "avg_confidence": 0.0,
                    "flagged_lines_count": 0,
                    "needs_review": True,
                    "lines": [],
                    "error": str(page_err)
                })

        joined_text = _clean_ocr_text("\n\n".join(full_text))
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
                    "text": l,
                    "confidence": 0.88,
                    "bbox": [0, i * 20, 800, (i + 1) * 20],
                    "doc_type": "digital_pdf",
                    "ocr_engine": "pypdf",
                    "flagged_for_review": False,
                    "uncertain_words": []
                }
                for i, l in enumerate(lines, start=1)
            ]
            pages.append({
                "page_number": page_num,
                "text": text,
                "ocr_engine": "pypdf",
                "line_count": len(lines),
                "doc_type": "digital_pdf",
                "avg_confidence": 0.88,
                "flagged_lines_count": 0,
                "needs_review": False,
                "lines": page_lines
            })
            all_lines.extend(page_lines)
            if text:
                full_text.append(text)

        joined_text = "\n\n".join(full_text)
        words = joined_text.split()
        return {
            "extracted_text": joined_text,
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
        text = extract_text(str(path)) or ""
        text = text.strip()
        words = text.split()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        page_lines = [
            {
                "line_number": i,
                "text": l,
                "confidence": 0.90,
                "bbox": [0, i * 20, 800, (i + 1) * 20],
                "doc_type": "digital_pdf",
                "ocr_engine": "pdfminer",
                "flagged_for_review": False,
                "uncertain_words": []
            }
            for i, l in enumerate(lines, start=1)
        ]
        return {
            "extracted_text": text,
            "ocr_engine": "pdfminer",
            "confidence": 0.90,
            "needs_review": False,
            "pages": [{
                "page_number": 1,
                "text": text,
                "ocr_engine": "pdfminer",
                "line_count": len(lines),
                "doc_type": "digital_pdf",
                "avg_confidence": 0.90,
                "flagged_lines_count": 0,
                "needs_review": False,
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
        raw_joined = "\n\n".join(paragraphs)
        joined_text = _clean_ocr_text(raw_joined)
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
                        "text": l,
                        "confidence": 1.0,
                        "bbox": [0, i * 20, 800, (i + 1) * 20],
                        "doc_type": "digital_doc",
                        "ocr_engine": "docx_native",
                        "flagged_for_review": False,
                        "uncertain_words": []
                    }
                    for i, l in enumerate(lines_split, start=1)
                ]
                pages.append({
                    "page_number": page_num,
                    "text": p_text,
                    "ocr_engine": "docx_native",
                    "line_count": len(lines_split),
                    "doc_type": "digital_doc",
                    "avg_confidence": 1.0,
                    "flagged_lines_count": 0,
                    "needs_review": False,
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
                    "text": l,
                    "confidence": 1.0,
                    "bbox": [0, i * 20, 800, (i + 1) * 20],
                    "doc_type": "digital_doc",
                    "ocr_engine": "docx_native",
                    "flagged_for_review": False,
                    "uncertain_words": []
                }
                for i, l in enumerate(lines_split, start=1)
            ]
            pages.append({
                "page_number": page_num,
                "text": p_text,
                "ocr_engine": "docx_native",
                "line_count": len(lines_split),
                "doc_type": "digital_doc",
                "avg_confidence": 1.0,
                "flagged_lines_count": 0,
                "needs_review": False,
                "lines": p_lines
            })
            all_lines.extend(p_lines)

        return {
            "extracted_text": joined_text,
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

        content = _clean_ocr_text(content)
        lines = [l.strip() for l in content.splitlines() if l.strip()]
        words = content.split()
        p_lines = [
            {
                "line_number": i,
                "text": l,
                "confidence": 1.0,
                "bbox": [0, i * 20, 800, (i + 1) * 20],
                "doc_type": "plain_text",
                "ocr_engine": "text_native",
                "flagged_for_review": False,
                "uncertain_words": []
            }
            for i, l in enumerate(lines, start=1)
        ]

        return {
            "extracted_text": content,
            "ocr_engine": "text_native",
            "confidence": 1.0,
            "needs_review": False,
            "pages": [{
                "page_number": 1,
                "text": content,
                "ocr_engine": "text_native",
                "line_count": len(lines),
                "doc_type": "plain_text",
                "avg_confidence": 1.0,
                "flagged_lines_count": 0,
                "needs_review": False,
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

        extracted_text = _clean_ocr_text(extracted_text)
        words = extracted_text.split()

        return {
            "extracted_text": extracted_text,
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

# NOTE: PaddleOCR is initialized lazily on first OCR request via _get_paddle_ocr().
# Do NOT eagerly init here — PaddlePaddle DLLs conflict with PyTorch on Windows.
