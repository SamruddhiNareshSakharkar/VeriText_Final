"""
Test script for NEW Handwritten OCR Pipeline vs Legacy OCR
===========================================================
1. Evaluates line detection & segmentation on handwritten samples.
2. Evaluates TrOCR recognition on segmented lines.
3. Compares OLD vs NEW handwritten OCR output.
4. Generates structured comparative metrics:
   - processing time
   - number of detected lines
   - confidence scores
   - text extraction comparison
"""

import os
import sys
import time
from pathlib import Path
from PIL import Image

# Ensure project root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.ml.handwritten_ocr_pipeline import (
    handwritten_ocr_pipeline,
    preprocess_handwritten_page,
    segment_handwritten_lines,
    TrOCRHandwrittenEngine
)
from backend.app.ml.ocr_engine import (
    ocr_engine,
    _preprocess_handwritten_image,
    segment_text_lines
)


def run_comparison():
    print("=" * 70)
    print("VERITEXT HANDWRITTEN OCR PIPELINE: OLD vs NEW EVALUATION")
    print("=" * 70)

    # Candidate handwritten samples
    sample_paths = [
        ROOT_DIR / "storage" / "uploads" / "debug_page_1.png",
        ROOT_DIR / "storage" / "uploads" / "debug_page_2.png",
        ROOT_DIR / "backend" / "test_crop1.png",
        ROOT_DIR / "backend" / "ocr_benchmark" / "images" / "line_001.png",
        ROOT_DIR / "backend" / "ocr_benchmark" / "images" / "line_002.png"
    ]

    valid_samples = [p for p in sample_paths if p.exists()]
    if not valid_samples:
        print("[ERROR] No handwritten test samples found.")
        return

    print(f"Found {len(valid_samples)} handwritten sample(s) for benchmarking:\n")

    for sample_path in valid_samples:
        print(f"\n========================================================")
        print(f"TEST SAMPLE: {sample_path.name} ({sample_path.stat().st_size} bytes)")
        print(f"========================================================")

        with Image.open(sample_path) as img:
            orig_size = img.size
            print(f"Image Dimensions: {orig_size[0]}x{orig_size[1]} px")

            # ---------------------------------------------------------
            # 1. EVALUATE LINE SEGMENTATION (OLD vs NEW)
            # ---------------------------------------------------------
            print("\n--- Line Segmentation ---")
            t0 = time.perf_counter()
            old_prep = _preprocess_handwritten_image(img, variant="gentle")
            old_regions, old_diag = segment_text_lines(old_prep)
            t_old_seg = time.perf_counter() - t0

            t0 = time.perf_counter()
            new_prep = preprocess_handwritten_page(img)
            new_crops, new_diag = segment_handwritten_lines(new_prep)
            t_new_seg = time.perf_counter() - t0

            print(f"OLD Segmentation: {len(old_regions)} lines detected ({t_old_seg:.3f}s)")
            print(f"NEW Segmentation: {len(new_crops)} lines detected ({t_new_seg:.3f}s)")
            print(f"NEW Diagnostics: Ruled lines={new_diag.ruled_lines_detected}, Avg Height={new_diag.avg_line_height}px, Merged={new_diag.merged_lines}")

            # ---------------------------------------------------------
            # 2. RUN NEW HANDWRITTEN OCR PIPELINE
            # ---------------------------------------------------------
            print("\n--- Running NEW Handwritten OCR Pipeline ---")
            t0 = time.perf_counter()
            new_res = handwritten_ocr_pipeline.process_image(img, page_number=1)
            t_new_ocr = time.perf_counter() - t0

            # ---------------------------------------------------------
            # 3. RUN OLD OCR PIPELINE (via ocr_engine.process_document)
            # ---------------------------------------------------------
            print("--- Running OLD/Legacy OCR Pipeline ---")
            os.environ["VERITEXT_HANDWRITING_PIPELINE"] = "legacy"
            t0 = time.perf_counter()
            old_res = ocr_engine.process_document(str(sample_path))
            t_old_ocr = time.perf_counter() - t0
            os.environ["VERITEXT_HANDWRITING_PIPELINE"] = "new"

            # ---------------------------------------------------------
            # 4. PRINT DETAILED COMPARISON
            # ---------------------------------------------------------
            print("\n" + "=" * 50)
            print("OLD PIPELINE:")
            print("=" * 50)
            print(f"Engine:       {old_res.get('ocr_engine')}")
            print(f"Confidence:   {old_res.get('confidence')}")
            print(f"Lines Count:  {len(old_res.get('lines', []))}")
            print(f"Word Count:   {old_res.get('word_count')}")
            print(f"Latency:      {t_old_ocr:.3f}s")
            print("Extracted Text:")
            print("-" * 30)
            print(old_res.get("extracted_text", "") or "[No text extracted]")

            print("\n" + "=" * 50)
            print("NEW PIPELINE:")
            print("=" * 50)
            print(f"Engine:       {new_res.get('ocr_engine')}")
            print(f"Confidence:   {new_res.get('avg_confidence')}")
            print(f"Lines Count:  {new_res.get('line_count')}")
            print(f"Latency:      {t_new_ocr:.3f}s")
            print("Extracted Text:")
            print("-" * 30)
            print(new_res.get("text", "") or "[No text extracted]")

            print("\nLine-by-Line Coordinate Breakdown (NEW Pipeline):")
            for line in new_res.get("lines", []):
                print(f"  Line {line['line_number']:02d} | BBox: {line['bbox']} | Conf: {line['confidence']:.2f} | Text: \"{line['text']}\"")

if __name__ == "__main__":
    run_comparison()
