"""
VeriText Quick OCR Test Runner
Usage:
    python run_ocr.py [path_to_image_or_pdf]
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Add workspace root to sys.path
root_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(root_dir))

from backend.app.ml.ocr_engine import ocr_engine
from backend.app.ml.gemini_ocr_engine import gemini_ocr_engine

def main():
    print("=" * 70)
    print("VERITEXT OCR ENGINE RUNNER")
    print("=" * 70)

    # Check Gemini API status
    has_gemini = gemini_ocr_engine.is_available()
    print(f"Hybrid Gemini API status: {'ENABLED (Active)' if has_gemini else 'OFFLINE FALLBACK MODE (No API key found in .env)'}")
    if has_gemini:
        print(f"Primary Model:   {gemini_ocr_engine.primary_model}")
        print(f"Fallback Model:  {gemini_ocr_engine.fallback_model}")
    else:
        print("Note: To enable Gemini cloud transcription, add GEMINI_API_KEY to your .env file.")
    print("=" * 70)

    # Determine input file
    if len(sys.argv) > 1:
        target_path = Path(sys.argv[1])
    else:
        # Default test candidates
        candidates = [
            Path(r"storage/uploads/1ba3756d9bae456894eaf81acc606be6.pdf"),
            Path(r"debug_ace_page1.png"),
            Path(r"test_crop_line1.png"),
        ]
        target_path = next((p for p in candidates if p.exists()), None)

    if not target_path or not target_path.exists():
        print("Error: No test file specified or found.")
        print("Usage: python run_ocr.py path/to/document.pdf (or .png / .jpg)")
        return

    print(f"\nProcessing file: {target_path} ...")
    result = ocr_engine.process_document(str(target_path))

    print("\n--- RESULTS ---")
    print(f"Status:       {result.get('status')}")
    print(f"Doc Type:     {result.get('doc_type') or result.get('document_type')}")
    print(f"Engine Used:  {result.get('ocr_engine')}")
    print(f"Confidence:   {result.get('confidence')}")
    print(f"Word Count:   {result.get('word_count')}")
    print(f"Total Lines:  {len(result.get('lines', []))}")
    print("\n--- EXTRACTED TEXT PREVIEW ---")
    text = result.get("extracted_text") or result.get("text") or ""
    print(text[:1500] if text else "[No text extracted]")
    if len(text) > 1500:
        print(f"\n... [{len(text) - 1500} characters truncated for preview]")
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
