import os
import sys
from pathlib import Path
from PIL import Image
import numpy as np

# Set environment
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["FLAGS_allocator_strategy"] = "auto_growth"
os.environ["DEBUG_HANDWRITING_OCR"] = "true"

sys.path.insert(0, r"c:\Users\Samruddhi\VERITEXT_AGAIN")

from backend.app.ml.ocr_engine import ocr_engine

pdf_path = Path(r"C:\Users\Samruddhi\VERITEXT_AGAIN\storage\uploads\1ba3756d9bae456894eaf81acc606be6.pdf")
print(f"Processing handwritten PDF: {pdf_path.name}")

res = ocr_engine.process_document(str(pdf_path))
print(f"\nOCR Processing completed! Status: {res.get('status')}, Engine: {res.get('ocr_engine')}")
print(f"Total pages: {len(res.get('pages', []))}")
print(f"Total recognized lines: {len(res.get('lines', []))}")

# Analyze saved debug crops
debug_base = Path("debug_handwriting")
page_dirs = sorted(list(debug_base.glob("page_*")))
print(f"\nFound {len(page_dirs)} debug page directories:")

for pdir in page_dirs:
    crop_files = sorted(list(pdir.glob("line_*.png")))
    print(f"\n--- Directory: {pdir.name} ({len(crop_files)} crops) ---")
    
    widths = []
    heights = []
    crop_boxes = []
    
    for cf in crop_files:
        with Image.open(cf) as img:
            w, h = img.size
            widths.append(w)
            heights.append(h)
    
    # Check dimensions
    avg_w = np.mean(widths) if widths else 0
    avg_h = np.mean(heights) if heights else 0
    min_w, max_w = (min(widths), max(widths)) if widths else (0, 0)
    min_h, max_h = (min(heights), max(heights)) if heights else (0, 0)
    
    print(f"Saved crops count: {len(crop_files)}")
    print(f"Average dimensions: {avg_w:.1f}px x {avg_h:.1f}px")
    print(f"Width range: {min_w}px - {max_w}px")
    print(f"Height range: {min_h}px - {max_h}px")
    
    # Check for extremely short or tall crops
    short_crops = [crop_files[i].name for i, h in enumerate(heights) if h < 25]
    tall_crops = [crop_files[i].name for i, h in enumerate(heights) if h > 300]
    narrow_crops = [crop_files[i].name for i, w in enumerate(widths) if w < 60]
    
    print(f"Extremely short crops (height < 25px): {len(short_crops)} {short_crops}")
    print(f"Extremely tall crops (height > 300px): {len(tall_crops)} {tall_crops}")
    print(f"Extremely narrow crops (width < 60px): {len(narrow_crops)} {narrow_crops}")
