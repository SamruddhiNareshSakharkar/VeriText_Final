"""
VERITEXT LOCAL OCR BENCHMARK TOOL
=================================
Standalone, offline evaluation tool to objectively benchmark handwriting recognition accuracy
against verified human-transcribed ground truth.

Models Compared:
1. TrOCR Base Handwritten: `microsoft/trocr-base-handwritten` (Primary Transformer Model)
2. PaddleOCR Local Recognition: `PaddleOCR(lang='en', det=False, rec=True)` (Alternative Local Model)

Metrics Computed:
- Character Error Rate (CER) = (Substitutions + Deletions + Insertions) / len(reference)
- Word Error Rate (WER) = (Word Substitutions + Deletions + Insertions) / len(reference_words)
- Exact Match Rate (EM)

Zero cloud calls. Zero LLM correction. Zero artificial spelling normalization.
"""

import os
import sys
import csv
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import numpy as np

# Ensure PaddleX / PaddleOCR bypasses external network checks
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_allocator_strategy"] = "auto_growth"
os.environ["OMP_NUM_THREADS"] = "4"

# Pre-import torch before paddle to prevent DLL conflicts on Windows
try:
    import torch
except Exception:
    pass


# =====================================================================
# CER & WER METRICS COMPUTATION (Levenshtein Distance)
# =====================================================================

def compute_cer(reference: str, hypothesis: str) -> float:
    """
    Computes exact Character Error Rate (CER) against ground truth reference text.
    CER = (S + D + I) / len(reference)
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
    Computes exact Word Error Rate (WER) against ground truth reference text.
    WER = (S + D + I) / len(reference_words)
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
# MODEL WRAPPERS
# =====================================================================

class TrOCRBenchmarkRunner:
    def __init__(self, model_id: str = "microsoft/trocr-base-handwritten"):
        self.model_id = model_id
        self.processor = None
        self.model = None
        self.device = "cpu"
        self._load()

    def _load(self):
        print(f"[TrOCR] Loading '{self.model_id}'...")
        import torch
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = TrOCRProcessor.from_pretrained(self.model_id)
        self.model = VisionEncoderDecoderModel.from_pretrained(self.model_id)
        self.model.to(self.device)
        self.model.eval()
        print(f"[TrOCR] Model loaded successfully on device: {self.device}")

    def recognize(self, pil_image: Image.Image) -> Tuple[str, float]:
        """Runs deterministic beam search inference on a single line crop."""
        import torch
        rgb_img = pil_image.convert("RGB") if pil_image.mode != "RGB" else pil_image
        inputs = self.processor(rgb_img, return_tensors="pt")
        pixel_values = inputs.pixel_values.to(self.device)

        start_time = time.perf_counter()
        with torch.no_grad():
            output = self.model.generate(
                pixel_values,
                do_sample=False,
                num_beams=4,
                length_penalty=1.0,
                early_stopping=True,
                max_new_tokens=64,
                repetition_penalty=1.20
            )
        elapsed = time.perf_counter() - start_time
        decoded = self.processor.batch_decode(output, skip_special_tokens=True)
        text = decoded[0].strip() if decoded else ""
        return text, round(elapsed, 3)


class PaddleOCRBenchmarkRunner:
    def __init__(self):
        self.engine = None
        self._load()

    def _load(self):
        print("[PaddleOCR] Initializing local recognition engine...")
        from paddleocr import PaddleOCR
        try:
            self.engine = PaddleOCR(use_angle_cls=False, lang="en", show_log=False)
            print("[PaddleOCR] Local recognition engine loaded successfully.")
        except Exception as e:
            print(f"[PaddleOCR] Initialization error: {e}")
            self.engine = None

    def recognize(self, pil_image: Image.Image) -> Tuple[str, float]:
        """Runs PaddleOCR recognition directly on line crop."""
        if self.engine is None:
            return "", 0.0

        np_img = np.array(pil_image.convert("RGB"))
        start_time = time.perf_counter()
        try:
            # det=False, rec=True executes direct text recognition on crop
            res = self.engine.ocr(np_img, det=False, rec=True)
            elapsed = time.perf_counter() - start_time
            if res and isinstance(res, list) and len(res) > 0:
                first = res[0]
                if isinstance(first, tuple) and len(first) > 0:
                    return str(first[0]).strip(), round(elapsed, 3)
                elif isinstance(first, list) and len(first) > 0:
                    sub = first[0]
                    if isinstance(sub, tuple) and len(sub) > 0:
                        return str(sub[0]).strip(), round(elapsed, 3)
            return "", round(elapsed, 3)
        except Exception as e:
            elapsed = time.perf_counter() - start_time
            return f"[ERROR: {e}]", round(elapsed, 3)


# =====================================================================
# BENCHMARK ENGINE
# =====================================================================

def run_benchmark(
    base_dir: Optional[Path] = None,
    preprocess_mode: str = "gentle"
):
    if base_dir is None:
        base_dir = Path(__file__).resolve().parent

    images_dir = base_dir / "images"
    gt_dir = base_dir / "ground_truth"
    results_dir = base_dir / "results"
    inputs_debug_dir = results_dir / "inputs"

    images_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    inputs_debug_dir.mkdir(parents=True, exist_ok=True)

    # Find candidate image files
    valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
    image_files = sorted([f for f in images_dir.iterdir() if f.is_file() and f.suffix.lower() in valid_exts])

    if not image_files:
        print(f"\n[WARNING] No test images found in '{images_dir}'.")
        print("Please place handwritten line crops in:")
        print(f"  {images_dir}/line_001.png")
        print("And corresponding ground-truth text in:")
        print(f"  {gt_dir}/line_001.txt")
        return

    print(f"\n==================================================", flush=True)
    print(f"VERITEXT LOCAL OCR BENCHMARK", flush=True)
    print(f"Found {len(image_files)} line image(s) to benchmark.", flush=True)
    print(f"==================================================\n", flush=True)

    # Load Models
    trocr_runner = TrOCRBenchmarkRunner()
    paddle_runner = PaddleOCRBenchmarkRunner()

    benchmark_rows = []
    trocr_cers = []
    trocr_wers = []
    paddle_cers = []
    paddle_wers = []

    for idx, img_path in enumerate(image_files, start=1):
        stem = img_path.stem
        gt_file = gt_dir / f"{stem}.txt"

        if not gt_file.exists():
            print(f"[{idx}/{len(image_files)}] Ground truth missing for '{img_path.name}' -> Skipped (ground_truth/{stem}.txt not found).", flush=True)
            continue

        with open(gt_file, "r", encoding="utf-8", errors="replace") as f:
            ground_truth = f.read().strip()

        # Load and prepare input image
        with Image.open(img_path) as raw_img:
            try:
                img_proc = ImageOps.exif_transpose(raw_img)
            except Exception:
                img_proc = raw_img

            if img_proc.mode != "RGB":
                img_proc = img_proc.convert("RGB")

            if preprocess_mode == "gentle":
                enhanced = ImageOps.autocontrast(img_proc, cutoff=0.5)
                enhancer = ImageEnhance.Contrast(enhanced)
                img_to_feed = enhancer.enhance(1.15).filter(ImageFilter.UnsharpMask(radius=0.8, percent=30, threshold=2))
            else:
                img_to_feed = img_proc

            debug_input_path = inputs_debug_dir / f"{stem}_input.png"
            img_to_feed.save(debug_input_path)

        # 1. Run TrOCR
        trocr_text, trocr_time = trocr_runner.recognize(img_to_feed)
        t_cer = compute_cer(ground_truth, trocr_text)
        t_wer = compute_wer(ground_truth, trocr_text)
        trocr_cers.append(t_cer)
        trocr_wers.append(t_wer)

        # 2. Run PaddleOCR
        paddle_text, paddle_time = paddle_runner.recognize(img_to_feed)
        p_cer = compute_cer(ground_truth, paddle_text)
        p_wer = compute_wer(ground_truth, paddle_text)
        paddle_cers.append(p_cer)
        paddle_wers.append(p_wer)

        row = {
            "filename": img_path.name,
            "ground_truth": ground_truth,
            "trocr_output": trocr_text,
            "paddle_output": paddle_text,
            "trocr_cer": t_cer,
            "trocr_wer": t_wer,
            "paddle_cer": p_cer,
            "paddle_wer": p_wer,
            "trocr_latency_sec": trocr_time,
            "paddle_latency_sec": paddle_time
        }
        benchmark_rows.append(row)

        print(f"[{idx}/{len(image_files)}] {img_path.name}:", flush=True)
        print(f"  GT:     '{ground_truth}'", flush=True)
        print(f"  TrOCR:  '{trocr_text}' [CER={t_cer:.3f}, WER={t_wer:.3f}, {trocr_time}s]", flush=True)
        print(f"  Paddle: '{paddle_text}' [CER={p_cer:.3f}, WER={p_wer:.3f}, {paddle_time}s]", flush=True)
        print("-" * 50, flush=True)

    if not benchmark_rows:
        print("\n[ERROR] No valid image/ground_truth pairs were evaluated.")
        return

    # Aggregate Statistics
    avg_trocr_cer = round(float(np.mean(trocr_cers)), 4)
    avg_trocr_wer = round(float(np.mean(trocr_wers)), 4)
    avg_paddle_cer = round(float(np.mean(paddle_cers)), 4)
    avg_paddle_wer = round(float(np.mean(paddle_wers)), 4)

    trocr_exact_matches = sum(1 for r in benchmark_rows if r["trocr_cer"] == 0.0)
    paddle_exact_matches = sum(1 for r in benchmark_rows if r["paddle_cer"] == 0.0)
    total_samples = len(benchmark_rows)

    summary_stats = {
        "total_samples": total_samples,
        "trocr": {
            "model_id": "microsoft/trocr-base-handwritten",
            "avg_cer": avg_trocr_cer,
            "avg_wer": avg_trocr_wer,
            "exact_match_count": trocr_exact_matches,
            "exact_match_rate": round(trocr_exact_matches / total_samples, 4)
        },
        "paddleocr": {
            "model_id": "PaddleOCR-en-local",
            "avg_cer": avg_paddle_cer,
            "avg_wer": avg_paddle_wer,
            "exact_match_count": paddle_exact_matches,
            "exact_match_rate": round(paddle_exact_matches / total_samples, 4)
        }
    }

    # Save CSV Report
    csv_path = results_dir / "benchmark_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "filename",
            "ground_truth",
            "trocr_output",
            "paddle_output",
            "trocr_cer",
            "trocr_wer",
            "paddle_cer",
            "paddle_wer",
            "trocr_latency_sec",
            "paddle_latency_sec"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(benchmark_rows)

    # Save JSON Report
    json_path = results_dir / "benchmark_report.json"
    full_json_data = {
        "summary": summary_stats,
        "rows": benchmark_rows
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_json_data, f, indent=2, ensure_ascii=False)

    # Save Human-Readable TXT Report
    txt_path = results_dir / "benchmark_report.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("VERITEXT LOCAL OCR BENCHMARK REPORT\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Total Evaluated Samples: {total_samples}\n\n")
        f.write("--- SUMMARY METRICS ---\n")
        f.write(f"1. TrOCR (microsoft/trocr-base-handwritten):\n")
        f.write(f"   • Mean Character Error Rate (CER): {avg_trocr_cer:.4f} ({avg_trocr_cer*100:.2f}%)\n")
        f.write(f"   • Mean Word Error Rate (WER):      {avg_trocr_wer:.4f} ({avg_trocr_wer*100:.2f}%)\n")
        f.write(f"   • Exact Match Accuracy:            {trocr_exact_matches}/{total_samples} ({trocr_exact_matches/total_samples*100:.2f}%)\n\n")

        f.write(f"2. PaddleOCR Local Recognition:\n")
        f.write(f"   • Mean Character Error Rate (CER): {avg_paddle_cer:.4f} ({avg_paddle_cer*100:.2f}%)\n")
        f.write(f"   • Mean Word Error Rate (WER):      {avg_paddle_wer:.4f} ({avg_paddle_wer*100:.2f}%)\n")
        f.write(f"   • Exact Match Accuracy:            {paddle_exact_matches}/{total_samples} ({paddle_exact_matches/total_samples*100:.2f}%)\n\n")

        f.write("=" * 70 + "\n")
        f.write("DETAILED LINE-BY-LINE EVALUATION\n")
        f.write("=" * 70 + "\n")
        for r in benchmark_rows:
            f.write(f"\n[File: {r['filename']}]\n")
            f.write(f"  Ground Truth: '{r['ground_truth']}'\n")
            f.write(f"  TrOCR Output: '{r['trocr_output']}' (CER={r['trocr_cer']:.3f}, WER={r['trocr_wer']:.3f})\n")
            f.write(f"  Paddle Output:'{r['paddle_output']}' (CER={r['paddle_cer']:.3f}, WER={r['paddle_wer']:.3f})\n")

    print("\n==================================================")
    print("BENCHMARK COMPLETED SUCCESSFULLY!")
    print(f"Results saved to:")
    print(f"  • CSV:  {csv_path}")
    print(f"  • JSON: {json_path}")
    print(f"  • TXT:  {txt_path}")
    print(f"  • Image Inputs: {inputs_debug_dir}")
    print("==================================================\n")
    print(f"TrOCR Mean CER:     {avg_trocr_cer:.4f} | Mean WER: {avg_trocr_wer:.4f}")
    print(f"PaddleOCR Mean CER: {avg_paddle_cer:.4f} | Mean WER: {avg_paddle_wer:.4f}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run local OCR benchmark comparing TrOCR and PaddleOCR.")
    parser.add_argument("--preprocess", choices=["gentle", "raw"], default="gentle", help="Image preprocessing mode")
    args = parser.parse_args()
    run_benchmark(preprocess_mode=args.preprocess)
