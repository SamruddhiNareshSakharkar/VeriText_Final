import os
import sys
import time
from pathlib import Path
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.ml.handwritten_ocr_pipeline import (
    handwritten_ocr_pipeline,
    preprocess_handwritten_page,
    segment_handwritten_lines,
    _trocr_onnx_engine
)
from backend.app.ml.ocr_engine import classify_document_type, ocr_engine

def test_handwritten_evaluation():
    print("=" * 75)
    print("VERITEXT LOCAL ONNX TrOCR HANDWRITTEN OCR PIPELINE EVALUATION")
    print("=" * 75)

    # Search for candidate handwritten files (PDFs and images)
    upload_dir = ROOT_DIR / "storage" / "uploads"
    benchmark_dir = ROOT_DIR / "backend" / "ocr_benchmark" / "images"

    test_candidates = []
    
    # Check sample benchmark line images
    if benchmark_dir.exists():
        for img_p in list(benchmark_dir.glob("*.png"))[:5]:
            test_candidates.append(img_p)

    # Check images in storage/uploads
    if upload_dir.exists():
        for p in upload_dir.glob("*.png"):
            test_candidates.append(p)
        for p in upload_dir.glob("*.pdf"):
            test_candidates.append(p)

    # Also check project root for test images
    for p in ROOT_DIR.glob("*.png"):
        test_candidates.append(p)

    print(f"Total potential test documents/images found: {len(test_candidates)}")

    # Test individual line recognition first on benchmark images
    line_images = [p for p in test_candidates if "line_" in p.name.lower() or "crop" in p.name.lower()]
    if line_images:
        print("\n--- BENCHMARK LINE CROPS RECOGNITION ---")
        for lip in line_images[:5]:
            try:
                img = Image.open(lip)
                t0 = time.perf_counter()
                text, conf = _trocr_onnx_engine.recognize_line(img)
                el = round(time.perf_counter() - t0, 3)
                print(f"[{lip.name}] -> Text: '{text}' | Conf: {conf:.3f} | Latency: {el}s")
            except Exception as e:
                print(f"[{lip.name}] -> Error: {e}")

    # Test full page documents
    page_candidates = [p for p in test_candidates if p.suffix.lower() == ".pdf" or ("page" in p.name.lower())]
    print(f"\n--- EVALUATING FULL HANDWRITTEN PAGES & ASSIGNMENTS ({len(page_candidates)} files) ---")

    tested_count = 0
    debug_crop_dir = ROOT_DIR / "debug_handwritten_crops"
    debug_crop_dir.mkdir(parents=True, exist_ok=True)

    for doc_path in page_candidates:
        if tested_count >= 5:
            break
        print("\n" + "=" * 75)
        print(f"PROCESSING DOCUMENT: {doc_path.name}")
        print("=" * 75)

        try:
            if doc_path.suffix.lower() == ".pdf":
                import pymupdf
                doc = pymupdf.open(str(doc_path))
                num_pages = len(doc)
                print(f"PDF Pages: {num_pages}")
                
                for p_idx in range(min(num_pages, 3)):
                    page = doc[p_idx]
                    pix = page.get_pixmap(dpi=300)
                    pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    # Classification
                    doc_type = classify_document_type(pil_img)
                    print(f"\n[Page {p_idx + 1}] Classification: '{doc_type}' | Resolution: {pil_img.size}")

                    # Run line segmentation
                    preprocessed = preprocess_handwritten_page(pil_img)
                    crops, diag = segment_handwritten_lines(preprocessed)
                    print(f"[Page {p_idx + 1}] Lines Detected: {len(crops)} | Ruled Notebook: {diag.ruled_lines_detected} | Avg Line Height: {diag.avg_line_height}px")

                    # Save debug line crops
                    page_crop_dir = debug_crop_dir / f"{doc_path.stem}_page{p_idx+1}"
                    page_crop_dir.mkdir(parents=True, exist_ok=True)
                    for c_idx, c in enumerate(crops[:10], start=1):
                        c.image.save(str(page_crop_dir / f"line_{c_idx:02d}.png"))

                    # Run full pipeline
                    t0 = time.perf_counter()
                    result = handwritten_ocr_pipeline.process_image(pil_img, page_number=p_idx + 1)
                    el = round(time.perf_counter() - t0, 3)

                    print(f"[Page {p_idx + 1}] Processed in {el}s | Avg Confidence: {result.get('avg_confidence')}")
                    print(f"[Page {p_idx + 1}] Flagged Lines for Review: {result.get('flagged_lines_count')}")
                    print("\nEXTRACTED LINES:")
                    for line in result.get("lines", []):
                        flag_str = " [FLAGGED/UNCERTAIN]" if line.get("flagged_for_review") else ""
                        print(f"  Line {line['line_number']:02d} (BBox: {line['bbox']}) [Conf: {line['confidence']:.2f}]: '{line['text']}'{flag_str}")
                    
                    print("\nFULL ASSEMBLED TEXT:")
                    print("-" * 50)
                    print(result.get("text", ""))
                    print("-" * 50)

                tested_count += 1

            elif doc_path.suffix.lower() in (".png", ".jpg", ".jpeg"):
                with Image.open(doc_path) as pil_img:
                    doc_type = classify_document_type(pil_img)
                    print(f"Classification: '{doc_type}' | Resolution: {pil_img.size}")

                    preprocessed = preprocess_handwritten_page(pil_img)
                    crops, diag = segment_handwritten_lines(preprocessed)
                    print(f"Lines Detected: {len(crops)} | Ruled Notebook: {diag.ruled_lines_detected} | Avg Line Height: {diag.avg_line_height}px")

                    # Save debug line crops
                    page_crop_dir = debug_crop_dir / doc_path.stem
                    page_crop_dir.mkdir(parents=True, exist_ok=True)
                    for c_idx, c in enumerate(crops[:10], start=1):
                        c.image.save(str(page_crop_dir / f"line_{c_idx:02d}.png"))

                    t0 = time.perf_counter()
                    result = handwritten_ocr_pipeline.process_image(pil_img, page_number=1)
                    el = round(time.perf_counter() - t0, 3)

                    print(f"Processed in {el}s | Avg Confidence: {result.get('avg_confidence')}")
                    print(f"Flagged Lines for Review: {result.get('flagged_lines_count')}")
                    print("\nEXTRACTED LINES:")
                    for line in result.get("lines", []):
                        flag_str = " [FLAGGED/UNCERTAIN]" if line.get("flagged_for_review") else ""
                        print(f"  Line {line['line_number']:02d} (BBox: {line['bbox']}) [Conf: {line['confidence']:.2f}]: '{line['text']}'{flag_str}")

                    print("\nFULL ASSEMBLED TEXT:")
                    print("-" * 50)
                    print(result.get("text", ""))
                    print("-" * 50)

                tested_count += 1

        except Exception as e:
            print(f"Error evaluating {doc_path.name}: {e}")

    print("\n" + "=" * 75)
    print("EVALUATION COMPLETE - Debug line crops saved to:", debug_crop_dir)
    print("=" * 75)

if __name__ == "__main__":
    test_handwritten_evaluation()
