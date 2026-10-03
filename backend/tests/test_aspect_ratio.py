import os
from pathlib import Path
from PIL import Image, ImageOps
import torch
from transformers import AutoImageProcessor, XLMRobertaTokenizer, TrOCRProcessor, VisionEncoderDecoderModel

snap = str(Path(os.path.expanduser('~/.cache/huggingface/hub/models--microsoft--trocr-small-handwritten/snapshots/b4648cfa171985a6745f37ddd637e98c0da958ac')))
img_proc = AutoImageProcessor.from_pretrained(snap)
tok = XLMRobertaTokenizer.from_pretrained(snap)
processor = TrOCRProcessor(image_processor=img_proc, tokenizer=tok)
model = VisionEncoderDecoderModel.from_pretrained(snap)
model.eval()

# Title line: 'T6 Solution - DPDA Design'
# Width ~800, Height ~90
img = Image.open('../storage/uploads/debug_page_1.png').convert("RGB")
crop = img.crop((220, 25, 1020, 115))

# 1. Direct resizing (what HuggingFace processor does by default)
pix1 = processor(crop, return_tensors='pt').pixel_values
with torch.no_grad():
    g1 = model.generate(pix1, max_new_tokens=48)
t1 = processor.batch_decode(g1, skip_special_tokens=True)[0]
print("Direct resize (squashed):", repr(t1))

# 2. Aspect-ratio preserved padding (pad height to make aspect ratio reasonable, e.g. 1:1 or 2:1)
w, h = crop.size
target_h = max(h, int(w * 0.35))
padded = Image.new("RGB", (w, target_h), (255, 255, 255))
offset_y = (target_h - h) // 2
padded.paste(crop, (0, offset_y))
pix2 = processor(padded, return_tensors='pt').pixel_values
with torch.no_grad():
    g2 = model.generate(pix2, max_new_tokens=48)
t2 = processor.batch_decode(g2, skip_special_tokens=True)[0]
print("Aspect-ratio preserved (padded):", repr(t2))

# 3. Test on individual words or short chunks:
# 'T6 Solution'
w_crop1 = img.crop((220, 25, 520, 115))
pix3 = processor(w_crop1, return_tensors='pt').pixel_values
with torch.no_grad():
    g3 = model.generate(pix3, max_new_tokens=48)
t3 = processor.batch_decode(g3, skip_special_tokens=True)[0]
print("Chunk 'T6 Solution':", repr(t3))

# 'DPDA Design'
w_crop2 = img.crop((530, 25, 1020, 115))
pix4 = processor(w_crop2, return_tensors='pt').pixel_values
with torch.no_grad():
    g4 = model.generate(pix4, max_new_tokens=48)
t4 = processor.batch_decode(g4, skip_special_tokens=True)[0]
print("Chunk 'DPDA Design':", repr(t4))
