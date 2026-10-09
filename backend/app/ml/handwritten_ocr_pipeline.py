"""
VERITEXT LOCAL HANDWRITTEN OCR PIPELINE (ONNX RUNTIME + TrOCR)
==============================================================
Dedicated, 100% offline, multi-stage handwritten document OCR pipeline
built specifically for academic integrity evaluation and similarity detection.

Architecture Flow:
------------------
Original Handwritten Page (High-Res 300 DPI Render)
        ↓
High-Res Preprocessing (Orientation, Deskew, Illumination Normalization, CLAHE, Ruled-Line Mitigation)
        ↓
Handwritten Text/Line Detection (Morphological Smearing + Contour Analysis + Projection Profile Fallback)
        ↓
Ascender/Descender Margin Protection & Horizontal Fragment Merging
        ↓
High-Resolution Line Crops from Original Image
        ↓
Pure ONNX Runtime TrOCR Recognition (microsoft/trocr-base-handwritten ONNX)
        - CPU Inference (Zero PyTorch requirement)
        - Vision Encoder (DeiT/ViT) -> Hidden States
        - Autoregressive Decoder -> Token Generation
        - Length-Calibrated Confidence & Uncertainty Scoring
        ↓
Deterministic Post-Processing & Reading Order Assembly
        ↓
Structured VeriText Page Schema (text, raw_text, lines, bbox, confidence, doc_type="handwritten")
"""

import os
import io
import math
import time
import logging
import re
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Tuple, Optional, Union

import numpy as np
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from scipy import ndimage

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

try:
    import onnxruntime as ort
    from tokenizers import Tokenizer
    HAS_ONNX_RUNTIME = True
except ImportError:
    HAS_ONNX_RUNTIME = False

logger = logging.getLogger(__name__)

# Directory where local TrOCR ONNX weights reside
MODEL_WEIGHTS_DIR = Path(__file__).resolve().parent / "weights" / "trocr"


# =====================================================================
# DATA STRUCTURES
# =====================================================================

@dataclass
class HandwrittenLineCrop:
    line_number: int
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2 on original image
    center_y: int
    image: Image.Image              # Padded high-res crop from original image
    is_ruled_notebook: bool = False
    preprocessing_variant: str = "standard"


@dataclass
class HandwrittenLineResult:
    line_number: int
    page_number: int
    raw_text: str                   # Exact verbatim model output without mutation
    text: str                       # Authoritative text
    normalized_text: str            # Cleaned string for similarity search & indexing
    recognition_score: float        # Model beam / token confidence score (0.0 to 1.0)
    confidence: float               # Calibrated confidence (0.0 to 1.0)
    bbox: Tuple[int, int, int, int] # [x1, y1, x2, y2]
    center_y: int
    doc_type: str = "handwritten"
    ocr_engine: str = "trocr-base-onnx"
    flagged_for_review: bool = False
    uncertain_words: List[str] = field(default_factory=list)
    candidate_details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_number": self.line_number,
            "page_number": self.page_number,
            "raw_text": self.raw_text,
            "text": self.text,
            "normalized_text": self.normalized_text,
            "recognition_score": self.recognition_score,
            "confidence": self.confidence,
            "bbox": list(self.bbox),
            "center_y": self.center_y,
            "doc_type": self.doc_type,
            "ocr_engine": self.ocr_engine,
            "flagged_for_review": self.flagged_for_review,
            "uncertain_words": self.uncertain_words,
            "candidate_details": self.candidate_details or {}
        }


@dataclass
class LineSegmentationStats:
    total_detected: int = 0
    merged_lines: int = 0
    avg_line_height: float = 0.0
    tiny_crops_filtered: int = 0
    large_crops_flagged: int = 0
    ruled_lines_detected: bool = False
    preprocessing_variant: str = "clahe_illumination"
    warning: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =====================================================================
# STEP 1: IMAGE PREPROCESSING & RULED-LINE MITIGATION
# =====================================================================

def deskew_image(pil_image: Image.Image, max_angle: float = 12.0) -> Image.Image:
    """Sub-degree deskewing using horizontal projection profile variance."""
    try:
        thumb = pil_image.copy()
        thumb.thumbnail((400, 400))
        gray = np.array(thumb.convert("L"), dtype=np.float32)

        mean_val = float(np.mean(gray))
        thresh = mean_val * 0.92
        binary = (gray < thresh).astype(np.float32)

        if np.sum(binary) < 50:
            return pil_image

        best_angle = 0.0
        max_var = -1.0

        for angle in np.arange(-max_angle, max_angle + 1.0, 2.0):
            rotated = ndimage.rotate(binary, angle, reshape=False, order=0, cval=0.0)
            proj = np.sum(rotated, axis=1)
            var = float(np.var(proj))
            if var > max_var:
                max_var = var
                best_angle = angle

        for angle in np.arange(best_angle - 2.0, best_angle + 2.1, 0.5):
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
        logger.debug(f"Deskew warning: {e}")
        return pil_image


def preprocess_handwritten_page(
    pil_image: Image.Image,
    enhance_contrast: bool = True,
    correct_illumination: bool = True
) -> Image.Image:
    """
    Careful non-destructive preprocessing tailored for real student handwriting:
    1. EXIF orientation correction & RGBA transparency flattening.
    2. Sub-degree deskewing.
    3. Flat-field background illumination normalization (removes uneven lighting/mobile shadows).
    4. CLAHE contrast enhancement between ink (blue/black) and paper.
    5. Does NOT harshly binarize so delicate handwriting strokes remain crisp.
    """
    try:
        # 1. EXIF orientation
        try:
            pil_image = ImageOps.exif_transpose(pil_image)
        except Exception:
            pass

        # 2. Flatten transparency
        if pil_image.mode in ("RGBA", "LA") or (pil_image.mode == "P" and "transparency" in pil_image.info):
            rgba = pil_image.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            pil_image = Image.alpha_composite(bg, rgba).convert("RGB")
        elif pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")

        # 3. Deskew
        pil_image = deskew_image(pil_image, max_angle=10.0)

        # 4. Illumination Normalization
        if correct_illumination:
            gray = pil_image.convert("L")
            w, h = gray.size
            small_w, small_h = max(1, w // 4), max(1, h // 4)
            small_gray = gray.resize((small_w, small_h), Image.Resampling.BILINEAR)
            small_arr = np.array(small_gray, dtype=np.float32)

            small_bg = ndimage.gaussian_filter(small_arr, sigma=12)
            bg_img = Image.fromarray(np.clip(small_bg, 1, 255).astype(np.uint8)).resize((w, h), Image.Resampling.BILINEAR)
            bg_arr = np.array(bg_img, dtype=np.float32)
            gray_arr = np.array(gray, dtype=np.float32)

            norm_arr = np.clip((gray_arr / (bg_arr + 1e-5)) * 255.0, 0, 255).astype(np.uint8)

            if HAS_OPENCV:
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced_arr = clahe.apply(norm_arr)
                norm_img = Image.fromarray(enhanced_arr)
            else:
                norm_img = Image.fromarray(norm_arr)
                norm_img = ImageOps.autocontrast(norm_img, cutoff=0.5)

            if enhance_contrast:
                enhancer = ImageEnhance.Contrast(norm_img)
                boosted = enhancer.enhance(1.20)
                sharpened = boosted.filter(ImageFilter.UnsharpMask(radius=0.8, percent=35, threshold=2))
                return sharpened.convert("RGB")
            return norm_img.convert("RGB")

        # Gentle fallback
        enhanced = ImageOps.autocontrast(pil_image, cutoff=0.5)
        enhancer = ImageEnhance.Contrast(enhanced)
        return enhancer.enhance(1.15)

    except Exception as e:
        logger.warning(f"Handwritten preprocessing fallback: {e}")
        return pil_image


def detect_and_handle_ruled_notebook_lines(gray_arr: np.ndarray) -> Tuple[np.ndarray, bool]:
    """
    Non-destructively detects horizontal ruled notebook lines.
    Suppresses horizontal line bridges so ruled lines do not merge distinct text lines,
    while carefully preserving vertical handwriting strokes.
    """
    try:
        h, w = gray_arr.shape
        mean_val = float(np.mean(gray_arr))
        std_val = float(np.std(gray_arr))
        thresh = mean_val - 0.35 * std_val
        binary = (gray_arr < thresh).astype(np.uint8)

        min_line_len = max(40, int(w * 0.40))
        h_kernel = np.ones((1, min_line_len), dtype=np.uint8)

        eroded = ndimage.binary_erosion(binary, structure=h_kernel)
        ruled_lines = ndimage.binary_dilation(eroded, structure=h_kernel)

        ruled_detected = bool(np.sum(ruled_lines) > (w * 2))

        if ruled_detected:
            v_kernel = np.ones((max(4, int(h * 0.02)), 1), dtype=np.uint8)
            vertical_strokes = ndimage.binary_opening(binary, structure=v_kernel)
            mask_to_suppress = ruled_lines & (~vertical_strokes)

            cleaned_binary = binary.copy()
            cleaned_binary[mask_to_suppress] = 0
            return cleaned_binary, True

        return binary, False
    except Exception as e:
        logger.debug(f"Ruled lines handler warning: {e}")
        return (gray_arr < 180).astype(np.uint8), False


# =====================================================================
# STEP 2: MULTI-LINE DETECTION & SEGMENTATION
# =====================================================================

def segment_handwritten_lines(
    original_image: Image.Image,
    min_line_height: int = 20,
    vertical_pad_ratio: float = 0.35,
    min_vertical_pad: int = 14,
    horizontal_pad: int = 20
) -> Tuple[List[HandwrittenLineCrop], LineSegmentationStats]:
    """
    Robust handwritten line detection and segmentation:
    1. Rescales to standard processing scale for uniform morphological smearing.
    2. Bridges adjacent words on each line using horizontal smearing kernels.
    3. Detects bounding boxes with dynamic ascender/descender margin protection.
    4. Merges overlapping bounding box fragments on the same baseline.
    5. Falls back to horizontal projection profile analysis if morphology fails.
    6. Crops each line directly from the ORIGINAL high-resolution image for maximum TrOCR fidelity.
    7. Sorts lines strictly in top-to-bottom reading order.
    """
    stats = LineSegmentationStats()
    try:
        orig_w, orig_h = original_image.size
        proc_scale = min(1.0, 1000.0 / max(orig_w, orig_h))
        proc_w = max(1, int(orig_w * proc_scale))
        proc_h = max(1, int(orig_h * proc_scale))
        inv_scale = 1.0 / proc_scale

        proc_img = original_image.resize((proc_w, proc_h), Image.Resampling.BILINEAR).convert("L")
        gray_arr = np.array(proc_img, dtype=np.uint8)

        # Handle notebook ruled lines
        binary_ink, had_ruled = detect_and_handle_ruled_notebook_lines(gray_arr)
        stats.ruled_lines_detected = had_ruled

        # Adaptive horizontal smearing kernel
        h_kernel_w = max(14, int(proc_w * 0.055))
        h_struct = np.ones((3, h_kernel_w), dtype=bool)

        smeared = ndimage.binary_dilation(binary_ink, structure=h_struct)
        v_struct = np.ones((4, 3), dtype=bool)
        smeared = ndimage.binary_closing(smeared, structure=v_struct)

        labeled, num_features = ndimage.label(smeared)
        slices = ndimage.find_objects(labeled)

        raw_boxes: List[Tuple[int, int, int, int]] = []
        scaled_min_lh = max(6, int(min_line_height * proc_scale))

        for sl in slices:
            if sl is None:
                continue
            sy1, sy2 = sl[0].start, sl[0].stop
            sx1, sx2 = sl[1].start, sl[1].stop
            sbw = sx2 - sx1
            sbh = sy2 - sy1

            # Discard tiny dust specks or oversized full-page boxes
            if sbw >= int(30 * proc_scale) and sbh >= scaled_min_lh and sbh <= int(proc_h * 0.45):
                y1 = int(sy1 * inv_scale)
                y2 = min(orig_h, int(sy2 * inv_scale))
                x1 = int(sx1 * inv_scale)
                x2 = min(orig_w, int(sx2 * inv_scale))
                bh = y2 - y1

                # Add dynamic vertical margin padding for ascenders (t, d, h, l) and descenders (g, y, p, q)
                pad_y = max(min_vertical_pad, int(bh * vertical_pad_ratio))
                ny1 = max(0, y1 - pad_y)
                ny2 = min(orig_h, y2 + pad_y)
                nx1 = max(0, x1 - horizontal_pad)
                nx2 = min(orig_w, x2 + horizontal_pad)
                raw_boxes.append((nx1, ny1, nx2, ny2))

        # Sort top-to-bottom by vertical center
        raw_boxes.sort(key=lambda b: ((b[1] + b[3]) / 2, b[0]))

        # Merge horizontal line fragments on the same baseline
        merged_boxes: List[Tuple[int, int, int, int]] = []
        for b in raw_boxes:
            if not merged_boxes:
                merged_boxes.append(b)
                continue
            prev = merged_boxes[-1]
            overlap_y = min(prev[3], b[3]) - max(prev[1], b[1])
            min_h = min(prev[3] - prev[1], b[3] - b[1])

            # If vertical overlap > 45% and vertical baseline difference is small
            if overlap_y > 0.45 * min_h and abs(b[1] - prev[1]) < int(orig_h * 0.05):
                stats.merged_lines += 1
                merged_boxes[-1] = (
                    min(prev[0], b[0]),
                    min(prev[1], b[1]),
                    max(prev[2], b[2]),
                    max(prev[3], b[3])
                )
            else:
                merged_boxes.append(b)

        # Fallback to projection profile slicing if morphological smearing missed lines
        if not merged_boxes:
            proj = np.sum(binary_ink.astype(np.float32), axis=1)
            kernel_size = max(5, int(proc_h * 0.015))
            if kernel_size % 2 == 0:
                kernel_size += 1
            smoothed = np.convolve(proj, np.ones(kernel_size) / kernel_size, mode="same")
            line_thresh = float(np.mean(smoothed)) * 0.20

            intervals: List[Tuple[int, int]] = []
            in_line = False
            start_y = 0
            for y in range(proc_h):
                val = smoothed[y]
                if not in_line and val > line_thresh:
                    in_line = True
                    start_y = y
                elif in_line and val <= line_thresh:
                    in_line = False
                    if y - start_y >= scaled_min_lh:
                        intervals.append((start_y, y))
            if in_line and (proc_h - start_y) >= scaled_min_lh:
                intervals.append((start_y, proc_h))

            for s, e in intervals:
                y1 = int(s * inv_scale)
                y2 = min(orig_h, int(e * inv_scale))
                bh = y2 - y1
                pad_y = max(min_vertical_pad, int(bh * vertical_pad_ratio))
                merged_boxes.append((0, max(0, y1 - pad_y), orig_w, min(orig_h, y2 + pad_y)))

        # Slicing line crops directly from original image
        line_crops: List[HandwrittenLineCrop] = []
        heights = []

        for idx, (x1, y1, x2, y2) in enumerate(merged_boxes, start=1):
            lh = y2 - y1
            heights.append(lh)
            if lh < 16:
                stats.tiny_crops_filtered += 1
            elif lh > int(orig_h * 0.40):
                stats.large_crops_flagged += 1

            crop_orig = original_image.crop((x1, y1, x2, y2))
            line_crops.append(HandwrittenLineCrop(
                line_number=idx,
                bbox=(x1, y1, x2, y2),
                center_y=int((y1 + y2) / 2),
                image=crop_orig,
                is_ruled_notebook=had_ruled,
                preprocessing_variant="clahe_illumination"
            ))

        stats.total_detected = len(line_crops)
        stats.avg_line_height = round(float(np.mean(heights)), 1) if heights else 0.0
        stats.warning = (stats.total_detected == 0) or (stats.large_crops_flagged > 0)

        logger.info(f"Line segmentation complete: {len(line_crops)} line(s) extracted (Ruled paper: {had_ruled})")
        return line_crops, stats

    except Exception as e:
        logger.exception(f"Line segmentation exception: {e}")
        stats.warning = True
        return [], stats


# =====================================================================
# STEP 3: TrOCR ONNX INFERENCE ENGINE (CPU / OFFLINE / ZERO-PYTORCH)
# =====================================================================

class TrOCRONNXEngine:
    """
    High-accuracy, 100% offline handwritten text recognition engine
    powered by Microsoft TrOCR ONNX Runtime execution.
    
    Zero PyTorch dependency:
    - Pure NumPy image preprocessing.
    - CPU ONNX Runtime InferenceSession.
    - Autoregressive decoder with greedy generation.
    - Calibrated sequence confidence scoring.
    """

    def __init__(self, weights_dir: Optional[Path] = None):
        self.weights_dir = weights_dir or MODEL_WEIGHTS_DIR
        self.tokenizer = None
        self.encoder_session = None
        self.decoder_session = None
        self.decoder_type = "merged"
        self.is_loaded = False
        self.load_failed = False
        self.active_model_id = "microsoft/trocr-base-handwritten (ONNX)"

    def load_model(self) -> bool:
        """Loads TrOCR ONNX encoder, decoder, and tokenizer."""
        if self.is_loaded:
            return True
        if self.load_failed:
            return False

        try:
            if not self.weights_dir.exists():
                logger.warning(f"TrOCR weights directory not found: {self.weights_dir}")
                self.load_failed = True
                return False

            # 1. Load Tokenizer (pure offline, no PyTorch / Transformers requirement)
            self.tokenizer = Tokenizer.from_file(str(self.weights_dir / "tokenizer.json"))

            # 2. Session Options for high performance on CPU
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = max(1, os.cpu_count() or 4)
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            # 3. Locate Encoder
            enc_candidates = [
                self.weights_dir / "encoder_model_quantized.onnx",
                self.weights_dir / "encoder_model.onnx"
            ]
            enc_path = next((p for p in enc_candidates if p.exists() and p.stat().st_size > 10 * 1024 * 1024), None)
            if not enc_path:
                logger.warning("TrOCR ONNX encoder model not found in weights directory.")
                self.load_failed = True
                return False

            logger.info(f"Loading TrOCR ONNX Encoder: {enc_path.name} ({enc_path.stat().st_size / (1024*1024):.1f} MB)")
            self.encoder_session = ort.InferenceSession(str(enc_path), sess_options=opts, providers=["CPUExecutionProvider"])

            # 4. Locate Decoder
            dec_candidates = [
                (self.weights_dir / "decoder_model_merged_quantized.onnx", "merged"),
                (self.weights_dir / "decoder_model_quantized.onnx", "standard"),
                (self.weights_dir / "decoder_model_merged.onnx", "merged"),
                (self.weights_dir / "decoder_model.onnx", "standard"),
            ]
            
            dec_path = None
            dec_type = "merged"
            for p, dtype in dec_candidates:
                if p.exists() and p.stat().st_size > 50 * 1024 * 1024:
                    dec_path = p
                    dec_type = dtype
                    break

            if not dec_path:
                logger.warning("TrOCR ONNX decoder model not found in weights directory.")
                self.load_failed = True
                return False

            self.decoder_type = dec_type
            logger.info(f"Loading TrOCR ONNX Decoder: {dec_path.name} ({dec_path.stat().st_size / (1024*1024):.1f} MB, mode: {dec_type})")
            self.decoder_session = ort.InferenceSession(str(dec_path), sess_options=opts, providers=["CPUExecutionProvider"])

            self.is_loaded = True
            logger.info("TrOCR ONNX Engine successfully initialized and ready for inference.")
            return True

        except Exception as e:
            logger.exception(f"Failed to initialize TrOCR ONNX Engine: {e}")
            self.load_failed = True
            return False

    def preprocess_image(self, image: Image.Image) -> np.ndarray:
        """Preprocesses PIL image to TrOCR input tensor (1, 3, 384, 384) float32."""
        if image.mode != "RGB":
            image = image.convert("RGB")
        resized = image.resize((384, 384), Image.Resampling.BICUBIC)
        arr = np.array(resized, dtype=np.float32) / 255.0
        # Normalize with mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]
        norm = (arr - 0.5) / 0.5
        # Transpose from (H, W, C) to (1, C, H, W)
        chw = np.transpose(norm, (2, 0, 1))
        return np.expand_dims(chw, axis=0).astype(np.float32)

    def recognize_line(
        self,
        image: Image.Image,
        max_new_tokens: int = 64
    ) -> Tuple[str, float]:
        """
        Runs deterministic ONNX inference on a single handwritten line crop.
        Returns: (recognized_text, confidence_score).
        """
        if not self.is_loaded and not self.load_failed:
            self.load_model()

        if not self.is_loaded or self.encoder_session is None or self.decoder_session is None:
            return ("", 0.0)

        try:
            # 1. Image Preprocessing & Vision Encoder
            pixel_values = self.preprocess_image(image)
            enc_inputs = {self.encoder_session.get_inputs()[0].name: pixel_values}
            enc_outputs = self.encoder_session.run(None, enc_inputs)
            encoder_hidden_states = enc_outputs[0]  # Shape: (1, 577, 768)

            # 2. Autoregressive Greedy Decoding
            decoder_start_token_id = 2  # <s> for RoBERTa
            eos_token_id = 2            # </s> for RoBERTa

            current_tokens = [decoder_start_token_id]
            log_probs = []

            dec_inputs_info = {inp.name: inp for inp in self.decoder_session.get_inputs()}
            has_use_cache = "use_cache_branch" in dec_inputs_info

            # Build dummy past_key_values if required by the static ONNX graph
            past_inputs = {}
            for inp_name, inp_info in dec_inputs_info.items():
                if inp_name.startswith("past_key_values"):
                    shape = [1 if isinstance(dim, str) or dim is None else dim for dim in inp_info.shape]
                    for idx, dim in enumerate(shape):
                        if idx == 2:
                            shape[idx] = 0
                    past_inputs[inp_name] = np.zeros(shape, dtype=np.float32)

            for step in range(max_new_tokens):
                input_ids_tensor = np.array([current_tokens], dtype=np.int64)

                feed = {
                    "input_ids": input_ids_tensor,
                    "encoder_hidden_states": encoder_hidden_states,
                }
                if has_use_cache:
                    feed["use_cache_branch"] = np.array([False], dtype=bool)
                    feed.update(past_inputs)

                dec_outputs = self.decoder_session.run(None, feed)
                logits = dec_outputs[0]  # (1, seq_len, vocab_size)

                last_logits = logits[0, -1, :]
                next_token_id = int(np.argmax(last_logits))

                # Compute log-softmax token probability
                exp_l = np.exp(last_logits - np.max(last_logits))
                prob = exp_l[next_token_id] / np.sum(exp_l)
                log_prob = float(np.log(max(prob, 1e-6)))
                log_probs.append(log_prob)

                if next_token_id == eos_token_id:
                    break

                current_tokens.append(next_token_id)

                # Stop immediately if repetitive loop detected
                if len(current_tokens) >= 5 and len(set(current_tokens[-5:])) == 1:
                    break

            # 3. Decode Tokens
            output_tokens = current_tokens[1:]  # Exclude start token
            decoded_text = self.tokenizer.decode(output_tokens, skip_special_tokens=True).strip()

            # Filter out pathological looping tokens (e.g. "a a a a a a")
            if re.search(r"(\b\w\b\s+){5,}", decoded_text) or re.search(r"(\W+\w\W+){5,}", decoded_text):
                return ("", 0.0)

            # 4. Calibrate confidence score
            mean_log_prob = float(np.mean(log_probs)) if log_probs else -1.0
            conf = round(float(np.clip(np.exp(mean_log_prob), 0.10, 0.99)), 3)

            return decoded_text, conf

        except Exception as e:
            logger.warning(f"TrOCR ONNX line inference error: {e}")
            return ("", 0.0)

    def recognize_lines(
        self,
        crops: List[Image.Image]
    ) -> List[Tuple[str, float]]:
        """Recognizes a sequence of line crops sequentially with progress tracking."""
        results = []
        for crop in crops:
            text, conf = self.recognize_line(crop)
            results.append((text, conf))
        return results


# Global singleton instance of TrOCR ONNX Engine
_trocr_onnx_engine = TrOCRONNXEngine()


# =====================================================================
# STEP 4: POST-PROCESSING & PAGE STRUCTURING
# =====================================================================

def _normalize_search_string(text: str) -> str:
    """Helper for indexing & plagiarism similarity search."""
    return re.sub(r"\s+", " ", text.lower().strip())


def structure_handwritten_page(
    lines: List[HandwrittenLineResult],
    page_number: int,
    engine_name: str,
    diagnostics: Optional[LineSegmentationStats] = None
) -> Dict[str, Any]:
    """
    Assembles recognized lines into reading order and paragraph hierarchy.
    Maintains exact spatial coordinates for plagiarism highlighting.
    """
    # Sort strictly in top-to-bottom reading order
    sorted_lines = sorted(lines, key=lambda l: (l.bbox[1], l.bbox[0]))
    for idx, l in enumerate(sorted_lines, start=1):
        l.line_number = idx

    paragraphs: List[str] = []
    current_para: List[str] = []
    prev_y2 = None
    median_h = 28.0

    if sorted_lines:
        line_heights = [(l.bbox[3] - l.bbox[1]) for l in sorted_lines if (l.bbox[3] - l.bbox[1]) > 5]
        if line_heights:
            median_h = float(np.median(line_heights))

    for l in sorted_lines:
        if not l.text.strip():
            continue
        y1, y2 = l.bbox[1], l.bbox[3]
        # Detect paragraph separation
        if prev_y2 is not None and (y1 - prev_y2) > (1.6 * median_h):
            if current_para:
                paragraphs.append(" ".join(current_para))
                current_para = []
        current_para.append(l.text.strip())
        prev_y2 = y2

    if current_para:
        paragraphs.append(" ".join(current_para))

    full_text = "\n\n".join(paragraphs).strip()
    if not full_text and sorted_lines:
        full_text = "\n".join(l.text.strip() for l in sorted_lines if l.text.strip())

    avg_rec = round(sum(l.recognition_score for l in sorted_lines) / max(len(sorted_lines), 1), 3) if sorted_lines else 0.0
    avg_conf = round(sum(l.confidence for l in sorted_lines) / max(len(sorted_lines), 1), 3) if sorted_lines else 0.0
    flagged_count = sum(1 for l in sorted_lines if l.flagged_for_review)
    needs_review = (flagged_count > 0) or (avg_conf < 0.65) or (diagnostics.warning if diagnostics else False)

    return {
        "page_number": page_number,
        "text": full_text,
        "raw_text": full_text,
        "ocr_engine": engine_name,
        "line_count": len(sorted_lines),
        "doc_type": "handwritten",
        "avg_recognition_score": avg_rec,
        "avg_confidence": avg_conf,
        "flagged_lines_count": flagged_count,
        "needs_review": needs_review,
        "segmentation_diagnostics": diagnostics.to_dict() if diagnostics else {},
        "lines": [l.to_dict() for l in sorted_lines]
    }


# =====================================================================
# STEP 5: MAIN HANDWRITTEN OCR PIPELINE
# =====================================================================

class HandwrittenOCRPipeline:
    """
    Dedicated handwritten OCR pipeline integrating high-resolution preprocessing,
    morphological line segmentation, and pure ONNX TrOCR inference.
    """

    def __init__(self, trocr_engine: Optional[TrOCRONNXEngine] = None):
        self.engine = trocr_engine or _trocr_onnx_engine

    def process_image(
        self,
        pil_image: Image.Image,
        page_number: int = 1
    ) -> Dict[str, Any]:
        """Processes a single handwritten page/image."""
        start_time = time.perf_counter()

        # Step 1: Illumination & Deskew Preprocessing
        preprocessed_img = preprocess_handwritten_page(pil_image)

        # Step 2: Line Detection & High-Res Cropping
        line_crops, diag = segment_handwritten_lines(preprocessed_img)

        # Step 3: TrOCR ONNX Line Recognition
        recognized_lines: List[HandwrittenLineResult] = []
        engine_name = self.engine.active_model_id

        if line_crops:
            crop_images = [crop.image for crop in line_crops]
            raw_results = self.engine.recognize_lines(crop_images)

            for crop, (rec_text, conf_score) in zip(line_crops, raw_results):
                flagged = (conf_score < 0.65) or (not rec_text.strip())

                recognized_lines.append(HandwrittenLineResult(
                    line_number=crop.line_number,
                    page_number=page_number,
                    raw_text=rec_text,
                    text=rec_text,
                    normalized_text=_normalize_search_string(rec_text),
                    recognition_score=conf_score,
                    confidence=conf_score,
                    bbox=crop.bbox,
                    center_y=crop.center_y,
                    doc_type="handwritten",
                    ocr_engine=engine_name,
                    flagged_for_review=flagged,
                    candidate_details={
                        "model": engine_name,
                        "score": conf_score,
                        "ruled_notebook": crop.is_ruled_notebook,
                        "preprocessing_variant": crop.preprocessing_variant
                    }
                ))

        # Step 4: Page Structuring
        page_dict = structure_handwritten_page(recognized_lines, page_number, engine_name, diag)
        elapsed = round(time.perf_counter() - start_time, 3)
        page_dict["processing_time_seconds"] = elapsed

        return page_dict

    def process_document(self, file_path: Union[str, Path]) -> Dict[str, Any]:
        """Main entry point for handwritten multi-page PDF or image files."""
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
                "doc_type": "handwritten",
                "document_type": "handwritten",
                "error": "File not found"
            }

        suffix = path.suffix.lower()
        pages: List[Dict[str, Any]] = []
        all_lines: List[Dict[str, Any]] = []
        full_text: List[str] = []

        try:
            if suffix == ".pdf":
                import pymupdf
                doc = pymupdf.open(str(path))
                for idx in range(len(doc)):
                    page = doc[idx]
                    pix = page.get_pixmap(dpi=300)
                    pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    page_dict = self.process_image(pil_img, page_number=idx + 1)
                    pages.append(page_dict)
                    all_lines.extend(page_dict.get("lines", []))
                    if page_dict.get("text"):
                        full_text.append(page_dict["text"])
            else:
                with Image.open(str(path)) as img:
                    page_dict = self.process_image(img, page_number=1)
                    pages.append(page_dict)
                    all_lines.extend(page_dict.get("lines", []))
                    if page_dict.get("text"):
                        full_text.append(page_dict["text"])

            joined_text = "\n\n".join(full_text).strip()
            words = joined_text.split()
            status = "completed" if words else ("partial" if pages else "failed")
            overall_conf = round(sum(p.get("avg_confidence", 0.0) for p in pages) / max(len(pages), 1), 3) if pages else 0.0
            needs_review = any(p.get("needs_review", False) for p in pages)

            return {
                "extracted_text": joined_text,
                "raw_text": joined_text,
                "text": joined_text,
                "ocr_engine": self.engine.active_model_id,
                "confidence": overall_conf,
                "needs_review": needs_review,
                "pages": pages,
                "lines": all_lines,
                "word_count": len(words),
                "status": status,
                "doc_type": "handwritten",
                "document_type": "handwritten"
            }

        except Exception as e:
            logger.exception(f"Handwritten document processing error: {e}")
            return {
                "extracted_text": "",
                "raw_text": "",
                "text": "",
                "ocr_engine": self.engine.active_model_id,
                "confidence": 0.0,
                "needs_review": True,
                "pages": [],
                "lines": [],
                "word_count": 0,
                "status": "failed",
                "doc_type": "handwritten",
                "document_type": "handwritten",
                "error": str(e)
            }


# Singleton instance
handwritten_ocr_pipeline = HandwrittenOCRPipeline()
