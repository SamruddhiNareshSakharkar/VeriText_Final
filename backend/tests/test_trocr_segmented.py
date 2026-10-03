import os
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage
import torch
from transformers import AutoImageProcessor, XLMRobertaTokenizer, TrOCRProcessor, VisionEncoderDecoderModel

# Load TrOCR model and tokenizer
snap = str(Path(os.path.expanduser('~/.cache/huggingface/hub/models--microsoft--trocr-small-handwritten/snapshots/b4648cfa171985a6745f37ddd637e98c0da958ac')))
img_proc = AutoImageProcessor.from_pretrained(snap)
tok = XLMRobertaTokenizer.from_pretrained(snap)
processor = TrOCRProcessor(image_processor=img_proc, tokenizer=tok)
model = VisionEncoderDecoderModel.from_pretrained(snap)
model.eval()

# Segmentation logic
def segment_lines(img: Image.Image):
    w, h = img.size
    gray = np.array(img.convert("L"), dtype=np.uint8)
    mean_val = np.mean(gray)
    std_val = np.std(gray)
    thresh = max(40, mean_val - 0.45 * std_val)
    ink = (gray < thresh)
    h_kernel_w = max(25, int(w * 0.04))
    h_struct = np.ones((3, h_kernel_w), dtype=bool)
    smeared = ndimage.binary_dilation(ink, structure=h_struct)
    v_struct = np.ones((5, 3), dtype=bool)
    smeared = ndimage.binary_closing(smeared, structure=v_struct)
    labeled, _ = ndimage.label(smeared)
    slices = ndimage.find_objects(labeled)
    boxes = []
    for sl in slices:
        if sl is None:
            continue
        y1, y2 = sl[0].start, sl[0].stop
        x1, x2 = sl[1].start, sl[1].stop
        bw = x2 - x1
        bh = y2 - y1
        if bw >= 80 and bh >= 18 and bh <= 200:
            pad_y = int(bh * 0.20)
            ny1 = max(0, y1 - pad_y)
            ny2 = min(h, y2 + pad_y)
            nx1 = max(0, x1 - 10)
            nx2 = min(w, x2 + 10)
            boxes.append((nx1, ny1, nx2, ny2))
    boxes.sort(key=lambda b: (b[1], b[0]))
    merged = []
    for b in boxes:
        if not merged:
            merged.append(b)
            continue
        prev = merged[-1]
        overlap_y = min(prev[3], b[3]) - max(prev[1], b[1])
        min_h = min(prev[3] - prev[1], b[3] - b[1])
        if overlap_y > 0.6 * min_h and abs(b[1] - prev[1]) < 30:
            merged[-1] = (min(prev[0], b[0]), min(prev[1], b[1]), max(prev[2], b[2]), max(prev[3], b[3]))
        else:
            merged.append(b)
    return merged

img = Image.open('../storage/uploads/debug_page_1.png').convert("RGB")
boxes = segment_lines(img)
print(f"Total lines to recognize: {len(boxes)}")

results = []
for idx, (x1, y1, x2, y2) in enumerate(boxes[:10]):
    crop = img.crop((x1, y1, x2, y2))
    pixel_values = processor(crop, return_tensors='pt').pixel_values
    with torch.no_grad():
        gen = model.generate(pixel_values, max_new_tokens=64)
    pred = processor.batch_decode(gen, skip_special_tokens=True)[0].strip()
    print(f"Line {idx+1:02d} [{y1}:{y2}]: {pred}")
    results.append(pred)
