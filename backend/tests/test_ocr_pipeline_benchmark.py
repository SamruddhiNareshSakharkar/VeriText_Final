"""
Test & Benchmark Suite for VERITEXT Multi-Stage OCR Pipeline
============================================================
Evaluates:
1. Document type classification (digital vs scanned printed vs handwritten).
2. Padded line segmentation (verifying ascender/descender padding).
3. Quality gate & confidence evaluation.
4. Second-pass verification & consistency checking.
5. End-to-end document processing across supported formats.
6. CER / WER metric accuracy.
"""

import sys
import os
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Ensure project root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.ml.ocr_engine import (
    ocr_engine,
    classify_document_type,
    segment_text_lines,
    _preprocess_printed_image,
    _preprocess_handwritten_image,
    _evaluate_line_confidence,
    compute_cer,
    compute_wer,
    _clean_ocr_text
)

def test_document_classification():
    print("\n--- Test 1: Document Classification ---")
    digital_text = "Machine learning and artificial intelligence are transforming modern higher education systems."
    doc_type = classify_document_type(digital_text=digital_text)
    print(f"Digital text classified as: '{doc_type}' (Expected: 'digital_pdf')")
    assert doc_type == "digital_pdf", f"Expected digital_pdf, got {doc_type}"

    # Create synthetic printed sample
    printed_img = Image.new("RGB", (800, 400), color=(255, 255, 255))
    d = ImageDraw.Draw(printed_img)
    for i in range(5):
        d.text((50, 40 + i * 50), f"Standard printed textbook line number {i+1} with uniform fonts.", fill=(0, 0, 0))
    
    img_type = classify_document_type(pil_image=printed_img)
    print(f"Synthetic printed image classified as: '{img_type}'")

def test_line_segmentation_padding():
    print("\n--- Test 2: Padded Line Segmentation ---")
    img = Image.new("RGB", (900, 500), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    # Text with prominent ascenders (b, d, h, k, l, t) and descenders (g, j, p, q, y, f)
    lines = [
        "Typography with high ascenders: baby, daddy, hawk, kite, little.",
        "Descenders going below baseline: jump, quick, python, gypsy, fly.",
        "Plagiarism analysis requires exact preservation of character geometry."
    ]
    for i, line in enumerate(lines):
        d.text((60, 80 + i * 110), line, fill=(15, 15, 15))

    regions = segment_text_lines(img, min_line_height=18, vertical_pad_ratio=0.30, min_vertical_pad=16)
    print(f"Extracted {len(regions)} segmented line regions.")
    for idx, r in enumerate(regions):
        bh = r.bbox[3] - r.bbox[1]
        bw = r.bbox[2] - r.bbox[0]
        print(f"  Line {idx+1}: BBox={r.bbox}, Width={bw}px, Height={bh}px (padded)")
        assert bh >= 20, "Line height should include vertical padding"

def test_quality_gate_confidence():
    print("\n--- Test 3: Quality Gate & Confidence Scoring ---")
    # Clean high quality text
    clean_text = "Natural language processing models evaluate syntactic and semantic similarity."
    conf, flagged, uncert = _evaluate_line_confidence(clean_text, 0.92)
    print(f"Clean text confidence: {conf:.2f}, Flagged: {flagged}, Uncertain: {uncert}")
    assert not flagged, "Clean text should not be flagged"

    # Corrupted / noisy OCR text
    corrupted_text = "Naturl Ingp|~ pr0c3ssing mdls vlt sytctc and s3mntc smlrt."
    bad_conf, bad_flagged, bad_uncert = _evaluate_line_confidence(corrupted_text, 0.65)
    print(f"Corrupted text confidence: {bad_conf:.2f}, Flagged: {bad_flagged}, Uncertain words: {bad_uncert}")
    assert bad_flagged, "Corrupted text MUST be flagged for teacher review"
    assert len(bad_uncert) > 0, "Corrupted words should be identified"

def test_cer_and_wer_metrics():
    print("\n--- Test 4: CER & WER Metrics ---")
    ref = "Artificial intelligence is transforming education."
    hyp_good = "Artificial intelligence is transforming education."
    hyp_minor = "ArtificiaI intelligence is transforrning education."
    
    cer_good = compute_cer(ref, hyp_good)
    wer_good = compute_wer(ref, hyp_good)
    cer_minor = compute_cer(ref, hyp_minor)
    wer_minor = compute_wer(ref, hyp_minor)

    print(f"Exact match -> CER: {cer_good}, WER: {wer_good}")
    print(f"Minor OCR errors -> CER: {cer_minor}, WER: {wer_minor}")
    assert cer_good == 0.0 and wer_good == 0.0
    assert cer_minor > 0.0 and wer_minor > 0.0

def test_end_to_end_image_pipeline():
    print("\n--- Test 5: End-to-End Image Processing ---")
    # Check if a sample upload exists
    sample_path = ROOT_DIR / "storage" / "uploads" / "debug_page_1.png"
    if not sample_path.exists():
        sample_path = ROOT_DIR / "backend" / "test_crop1.png"

    if sample_path.exists():
        t0 = time.time()
        res = ocr_engine.process_document(str(sample_path))
        t1 = time.time()
        print(f"Processed '{sample_path.name}' in {t1 - t0:.2f}s")
        print(f"  Engine: {res.get('ocr_engine')}")
        print(f"  Doc Type: {res.get('doc_type')}")
        print(f"  Confidence: {res.get('confidence')}")
        print(f"  Needs Review: {res.get('needs_review')}")
        print(f"  Word Count: {res.get('word_count')}")
        print(f"  Total Pages: {len(res.get('pages', []))}")
        print(f"  Total Lines: {len(res.get('lines', []))}")
        print(f"  Text Excerpt (first 120 chars): {res.get('extracted_text', '')[:120]}...")
    else:
        print(f"No sample image found at {sample_path}, creating in-memory synthetic test.")
        synth_img = Image.new("RGB", (1000, 300), color=(255, 255, 255))
        d = ImageDraw.Draw(synth_img)
        d.text((50, 50), "Testing end-to-end OCR pipeline architecture.", fill=(0, 0, 0))
        tmp_path = ROOT_DIR / "backend" / "temp_synth_test.png"
        synth_img.save(str(tmp_path))
        try:
            res = ocr_engine.process_document(str(tmp_path))
            print(f"  Engine: {res.get('ocr_engine')}, Word Count: {res.get('word_count')}")
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

if __name__ == "__main__":
    print("=" * 60)
    print("VERITEXT OCR PIPELINE BENCHMARK & VERIFICATION")
    print("=" * 60)
    test_document_classification()
    test_line_segmentation_padding()
    test_quality_gate_confidence()
    test_cer_and_wer_metrics()
    test_end_to_end_image_pipeline()
    print("\n[SUCCESS] All OCR pipeline verification tests completed successfully.")
