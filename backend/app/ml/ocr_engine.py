import os
import io
import sys
import shutil
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List
import docx
import numpy as np
import re
from PIL import Image, ImageEnhance, ImageOps, ImageFilter

logger = logging.getLogger(__name__)

# Auto-configure Tesseract executable path on Windows if present
TESSERACT_CANDIDATE_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
]

# Cache Tesseract lookup so we don't re-scan every page when it's not installed
_tesseract_cache = {"checked": False, "module": None}

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
                return pytesseract
        which_tess = shutil.which("tesseract")
        if which_tess:
            pytesseract.pytesseract.tesseract_cmd = which_tess
            _tesseract_cache["module"] = pytesseract
            return pytesseract
        # Tesseract import exists but binary not found — don't return module
        _tesseract_cache["module"] = None
        return None
    except Exception:
        _tesseract_cache["module"] = None
        return None

def _is_blank_page(pil_image: Image.Image) -> bool:
    """Fast blank-page detection in <1ms using a thumbnail sample."""
    try:
        thumb = pil_image.resize((64, 64), Image.Resampling.NEAREST).convert("L")
        arr = np.array(thumb, dtype=np.float32)
        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr))
        # Uniformly white (mean >= 250, std < 4) or uniformly black (mean <= 5, std < 3)
        if mean_val >= 250.0 and std_val < 4.0:
            return True
        if mean_val <= 5.0 and std_val < 3.0:
            return True
        return False
    except Exception:
        return False

def _preprocess_image_for_ocr(pil_image: Image.Image) -> Image.Image:
    """
    Enhanced OCR preprocessor with upscaling, contrast normalization, and stroke sharpening.
    - Composites alpha over white
    - Upscales small images (< 1400px) to 1800px for better character recognition
    - Downscales oversized images (> 2400px) to 2200px
    - Applies autocontrast with 0.5% cutoff + 1.35x contrast boost
    - Applies UnsharpMask to sharpen faint ink strokes and character edges
    """
    try:
        # Handle alpha channel (composite over solid white background)
        if pil_image.mode in ("RGBA", "LA") or (pil_image.mode == "P" and "transparency" in pil_image.info):
            rgba = pil_image.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            pil_image = Image.alpha_composite(bg, rgba).convert("RGB")
        elif pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        w, h = pil_image.size
        max_side = max(w, h)
        # Upscale small images for better OCR accuracy
        if max_side < 1400:
            scale = 1800.0 / float(max_side)
            pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        elif max_side > 2400:
            scale = 2200.0 / float(max_side)
            pil_image = pil_image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        gray = pil_image.convert("L")
        normalized = ImageOps.autocontrast(gray, cutoff=0.5)
        enhancer = ImageEnhance.Contrast(normalized)
        enhanced = enhancer.enhance(1.35)
        # Sharpen to define pen strokes and character boundaries
        sharpened = enhanced.filter(ImageFilter.UnsharpMask(radius=1.5, percent=125, threshold=3))
        return sharpened.convert("RGB")
    except Exception as e:
        logger.warning(f"Image preprocessing fallback: {e}")
        return pil_image.convert("RGB") if pil_image.mode != "RGB" else pil_image

def _extract_text_from_result(res) -> str:
    """Helper to safely extract recognized text from either a WinRT OcrResult object or a converted dict."""
    if res is None:
        return ""
    if isinstance(res, dict):
        return (res.get("text") or "").strip()
    if hasattr(res, "text") and res.text:
        return str(res.text).strip()
    return ""

def _clean_ocr_text(text: str) -> str:
    """Post-process OCR text: fix hyphenated line wraps, normalize Unicode marks."""
    if not text:
        return ""
    # Merge hyphenated word wraps: "implemen-\ntation" -> "implementation"
    cleaned = re.sub(r"(\b\w+)-\n(\w+\b)", r"\1\2", text)
    # Normalize common typographic marks
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
    cleaned = cleaned.replace("\u2014", " - ")
    # Collapse excessive blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

def _run_winocr_sync(pil_image: Image.Image, lang: str = "en-US") -> str:
    """
    High-performance Windows OCR with blank-page detection,
    enhanced preprocessing, and minimal WinRT invocations.
    """
    # 0. Auto-orient based on EXIF tags (crucial for smartphone camera photos)
    try:
        pil_image = ImageOps.exif_transpose(pil_image)
    except Exception:
        pass

    # 1. Fast blank-page detection — skip pure white/black pages instantly
    if _is_blank_page(pil_image):
        return ""

    # Ensure RGB mode for WinOCR (handle transparency)
    if pil_image.mode in ("RGBA", "LA") or (pil_image.mode == "P" and "transparency" in pil_image.info):
        rgba = pil_image.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        raw_image = Image.alpha_composite(bg, rgba).convert("RGB")
    elif pil_image.mode != "RGB":
        raw_image = pil_image.convert("RGB")
    else:
        raw_image = pil_image

    # 2. Prepare enhanced image (upscaled, contrast-normalized, sharpened)
    enhanced_image = _preprocess_image_for_ocr(raw_image)

    # 3. Try Windows WinRT OCR — only 2 attempts (enhanced first, raw fallback)
    if sys.platform == "win32":
        try:
            try:
                import ctypes
                ctypes.windll.ole32.CoInitialize(None)
            except Exception:
                pass

            import winocr

            loop = asyncio.new_event_loop()
            try:
                # Attempt 1: Enhanced/sharpened image (best for faint handwriting)
                res = loop.run_until_complete(winocr.recognize_pil(enhanced_image))
                extracted = _extract_text_from_result(res)

                # Attempt 2: If enhanced produced very few words, try raw image
                if not extracted or len(extracted.split()) < 8:
                    res_raw = loop.run_until_complete(winocr.recognize_pil(raw_image))
                    extracted_raw = _extract_text_from_result(res_raw)
                    if len(extracted_raw.split()) > len((extracted or "").split()):
                        extracted = extracted_raw

                if extracted:
                    logger.info(f"OCR successful using Windows OCR, {len(extracted.split())} words")
                    return _clean_ocr_text(extracted)
            finally:
                loop.close()

        except Exception as e:
            logger.warning(f"Windows OCR failed: {type(e).__name__}: {e}")

    # 4. Try Tesseract OCR (only if installed — cached check)
    pytess = _get_configured_tesseract()
    if pytess:
        try:
            text = pytess.image_to_string(enhanced_image, config="--oem 3 --psm 3")
            text = text.strip()
            if text:
                logger.info("OCR successful using Tesseract")
                return _clean_ocr_text(text)
        except Exception as e:
            logger.warning(f"Tesseract OCR failed: {type(e).__name__}: {e}")

    logger.warning("All OCR engines completed without finding extractable text.")
    return ""

class OCREngine:
    def process_document(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return {
                "extracted_text": "",
                "pages": [],
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
                "pages": [],
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
                "pages": [],
                "word_count": 0,
                "status": "failed",
                "error": f"All PDF extraction engines failed: {str(e)}"
            }

    def _process_pdf_pymupdf(self, path: Path) -> Dict[str, Any]:
        import pymupdf
        pages = []
        full_text = []
        doc = pymupdf.open(str(path))
        num_pages = len(doc)

        for idx in range(num_pages):
            try:
                page = doc[idx]
                # 1. Extract digital text
                text = (page.get_text("text") or "").strip()

                # 2. If digital text is missing, sparse (< 50 words), or the page contains embedded images, run OCR
                words_in_text = text.split()
                has_images = bool(page.get_images())
                if len(words_in_text) < 50 or has_images:
                    try:
                        pix = page.get_pixmap(dpi=300)
                        pil_img = Image.open(io.BytesIO(pix.tobytes("png")))
                        ocr_extracted = _run_winocr_sync(pil_img)
                        if ocr_extracted:
                            ocr_words = ocr_extracted.split()
                            if len(ocr_words) > len(words_in_text):
                                text = ocr_extracted.strip()
                            elif not text:
                                text = ocr_extracted.strip()
                            elif has_images and len(ocr_words) > 15 and ocr_extracted.strip() not in text:
                                text = f"{text}\n\n{ocr_extracted.strip()}".strip()
                    except Exception as ocr_err:
                        logger.warning(f"Page {idx + 1} pixmap OCR failed: {ocr_err}")

                lines = [l.strip() for l in text.split("\n") if l.strip()]
                pages.append({
                    "page_number": idx + 1,
                    "text": text,
                    "line_count": len(lines)
                })
                if text:
                    full_text.append(text)
            except Exception as page_err:
                logger.warning(f"Error processing page {idx + 1} in {path}: {page_err}")
                pages.append({
                    "page_number": idx + 1,
                    "text": "",
                    "line_count": 0,
                    "error": str(page_err)
                })

        joined_text = "\n\n".join(full_text)
        words = joined_text.split()
        status = "completed" if words else ("partial" if pages else "failed")

        return {
            "extracted_text": joined_text,
            "pages": pages,
            "word_count": len(words),
            "status": status
        }

    def _process_pdf_pypdf(self, path: Path) -> Dict[str, Any]:
        import pypdf
        pages = []
        full_text = []
        reader = pypdf.PdfReader(str(path), strict=False)

        for idx, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if len(text) < 30 and hasattr(page, "images") and page.images:
                page_ocr_parts = []
                for img_obj in page.images:
                    try:
                        pil_img = Image.open(io.BytesIO(img_obj.data))
                        extracted = _run_winocr_sync(pil_img)
                        if extracted:
                            page_ocr_parts.append(extracted)
                    except Exception as ex:
                        logger.warning(f"Error in pypdf image OCR: {ex}")
                if page_ocr_parts:
                    text = "\n\n".join(page_ocr_parts).strip()

            lines = [l.strip() for l in text.split("\n") if l.strip()]
            pages.append({
                "page_number": idx + 1,
                "text": text,
                "line_count": len(lines)
            })
            if text:
                full_text.append(text)

        joined_text = "\n\n".join(full_text)
        words = joined_text.split()
        return {
            "extracted_text": joined_text,
            "pages": pages,
            "word_count": len(words),
            "status": "completed" if words else "failed"
        }

    def _process_pdf_pdfminer(self, path: Path) -> Dict[str, Any]:
        from pdfminer.high_level import extract_text
        text = extract_text(str(path)) or ""
        text = text.strip()
        words = text.split()
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        return {
            "extracted_text": text,
            "pages": [{"page_number": 1, "text": text, "line_count": len(lines)}],
            "word_count": len(words),
            "status": "completed" if words else "failed"
        }

    def _process_docx(self, path: Path) -> Dict[str, Any]:
        doc = docx.Document(str(path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        joined_text = "\n\n".join(paragraphs)
        words = joined_text.split()

        pages = []
        current_page_text = []
        current_words = 0
        page_num = 1

        for p in paragraphs:
            w_count = len(p.split())
            current_page_text.append(p)
            current_words += w_count
            if current_words >= 350:
                pages.append({
                    "page_number": page_num,
                    "text": "\n\n".join(current_page_text),
                    "line_count": len(current_page_text)
                })
                page_num += 1
                current_page_text = []
                current_words = 0

        if current_page_text or not pages:
            pages.append({
                "page_number": page_num,
                "text": "\n\n".join(current_page_text),
                "line_count": len(current_page_text)
            })

        return {
            "extracted_text": joined_text,
            "pages": pages,
            "word_count": len(words),
            "status": "completed"
        }

    def _process_plaintext(self, path: Path) -> Dict[str, Any]:
        content = ""
        # Try multiple encodings
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

        lines = content.splitlines()
        words = content.split()

        return {
            "extracted_text": content,
            "pages": [{
                "page_number": 1,
                "text": content,
                "line_count": len(lines)
            }],
            "word_count": len(words),
            "status": "completed"
        }

    def _process_image(self, path: Path) -> Dict[str, Any]:
        with Image.open(str(path)) as img:
            extracted_text = _run_winocr_sync(img)

        lines = [l.strip() for l in extracted_text.split("\n") if l.strip()]
        words = extracted_text.split()

        return {
            "extracted_text": extracted_text,
            "pages": [{
                "page_number": 1,
                "text": extracted_text,
                "line_count": len(lines)
            }],
            "word_count": len(words),
            "status": "completed" if words else "failed",
            "error": None if words else "OCR could not extract any text"
        }

ocr_engine = OCREngine()
