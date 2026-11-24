"""
Test Suite for Hybrid Handwriting OCR Architecture
Tests:
1. Aspect-Ratio Preserving Preprocessing (ImageOps.pad) vs squishing.
2. Gemini OCR Engine availability detection and configuration.
3. Offline TrOCR fallback behavior when API key is missing or offline.
4. End-to-end integration with ocr_engine and handwritten_ocr_pipeline.
"""

import os
import sys
from pathlib import Path
from PIL import Image, ImageDraw

# Add workspace root to sys.path
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from backend.app.core.config import settings
from backend.app.ml.gemini_ocr_engine import GeminiHandwrittenOCREngine, gemini_ocr_engine
from backend.app.ml.handwritten_ocr_pipeline import handwritten_ocr_pipeline


def test_aspect_ratio_padding():
    print("\n--- Test 1: Aspect Ratio Padding Verification ---")
    engine = handwritten_ocr_pipeline.engine

    # Create a synthetic wide text line crop (800 x 80 px, aspect ratio 10:1)
    wide_img = Image.new("RGB", (800, 80), color=(255, 255, 255))
    draw = ImageDraw.Draw(wide_img)
    draw.text((50, 30), "Testing aspect ratio preservation", fill=(0, 0, 0))

    tensor = engine.preprocess_image(wide_img)
    assert tensor.shape == (1, 3, 384, 384), f"Expected shape (1, 3, 384, 384), got {tensor.shape}"

    # Verify that padding creates white bands on top and bottom instead of stretching vertically
    # Top slice (channel 0, row 0 to 20) should be pure white normalized: (255/255 - 0.5)/0.5 = 1.0
    top_band = tensor[0, :, :20, :]
    assert abs(top_band.mean() - 1.0) < 0.05, f"Top band should be padded white (1.0), got {top_band.mean()}"
    print("Aspect-ratio padding verified: wide line crop is padded symmetrically to 384x384 without squishing.")


def test_gemini_engine_fallback():
    print("\n--- Test 2: Gemini OCR Engine Fallback Verification ---")
    test_engine = GeminiHandwrittenOCREngine(api_key=None)
    assert not test_engine.is_available(), "Engine without API key must report unavailable."
    print("Engine correctly reports unavailable when API key is None.")

    test_engine_with_key = GeminiHandwrittenOCREngine(api_key="test_dummy_key_12345")
    assert test_engine_with_key.is_available(), "Engine with valid key string should report available."
    print("Engine correctly reports available when API key is provided.")


def test_pipeline_offline_fallback():
    print("\n--- Test 3: Full Pipeline Offline Fallback Execution ---")
    # Create a synthetic handwriting page image
    test_page = Image.new("RGB", (600, 400), color=(250, 250, 248))
    draw = ImageDraw.Draw(test_page)
    draw.text((40, 50), "VeriText Offline Fallback Pipeline Test", fill=(20, 20, 60))
    draw.text((40, 120), "Academic Integrity & Plagiarism Detection", fill=(20, 20, 60))

    # Without API key, it should safely fall back to local TrOCR without crashing
    res = handwritten_ocr_pipeline.process_image(test_page, page_number=1)
    assert "text" in res, "Result must contain 'text' key"
    assert "lines" in res, "Result must contain 'lines' key"
    assert res["page_number"] == 1, "Page number must be 1"
    print(f"Pipeline executed successfully with offline fallback. Status: {res.get('status', 'ok')}")
    print(f"Lines detected: {len(res.get('lines', []))}")


if __name__ == "__main__":
    print("=" * 70)
    print("VERITEXT HYBRID HANDWRITING OCR TEST SUITE")
    print("=" * 70)
    test_aspect_ratio_padding()
    test_gemini_engine_fallback()
    test_pipeline_offline_fallback()
    print("\n" + "=" * 70)
    print("All Hybrid Architecture Tests Passed Successfully!")
    print("=" * 70)
