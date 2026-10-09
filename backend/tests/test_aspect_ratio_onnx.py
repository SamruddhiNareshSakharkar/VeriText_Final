import onnxruntime as ort
import numpy as np
from PIL import Image, ImageOps
from tokenizers import Tokenizer
from pathlib import Path

weights_dir = Path(r"C:\Users\Samruddhi\VERITEXT_AGAIN\backend\app\ml\weights\trocr")
tok = Tokenizer.from_file(str(weights_dir / "tokenizer.json"))
enc = ort.InferenceSession(str(weights_dir / "encoder_model_quantized.onnx"), providers=["CPUExecutionProvider"])
dec = ort.InferenceSession(str(weights_dir / "decoder_model_quantized.onnx"), providers=["CPUExecutionProvider"])

def test_rec(img_path):
    print("\n--- Image:", Path(img_path).name, "---")
    img = Image.open(img_path)

    # 1. Direct Resize (Squished into square)
    img1 = img.convert("RGB").resize((384, 384), Image.Resampling.BICUBIC)
    arr1 = (np.array(img1, dtype=np.float32) / 255.0 - 0.5) / 0.5
    pix1 = np.expand_dims(np.transpose(arr1, (2, 0, 1)), axis=0).astype(np.float32)
    enc_out1 = enc.run(None, {"pixel_values": pix1})[0]

    # 2. Aspect-Ratio Preserved with white padding (TrOCR canonical training mode)
    img2 = ImageOps.pad(img.convert("RGB"), (384, 384), color=(255, 255, 255), centering=(0.5, 0.5))
    arr2 = (np.array(img2, dtype=np.float32) / 255.0 - 0.5) / 0.5
    pix2 = np.expand_dims(np.transpose(arr2, (2, 0, 1)), axis=0).astype(np.float32)
    enc_out2 = enc.run(None, {"pixel_values": pix2})[0]

    for name, enc_out in [("Direct Squish", enc_out1), ("Aspect Ratio Preserved", enc_out2)]:
        tokens = [2]
        for _ in range(40):
            logits = dec.run(None, {"input_ids": np.array([tokens], dtype=np.int64), "encoder_hidden_states": enc_out})[0]
            nxt = int(np.argmax(logits[0, -1, :]))
            if nxt == 2:
                break
            tokens.append(nxt)
        print(f"  {name:25s}: '{tok.decode(tokens[1:])}'")

if __name__ == "__main__":
    test_crops = [
        r"C:\Users\Samruddhi\VERITEXT_AGAIN\debug_handwritten_crops\debug_page_1\line_01.png",
        r"C:\Users\Samruddhi\VERITEXT_AGAIN\debug_handwritten_crops\debug_page_2\line_02.png",
        r"C:\Users\Samruddhi\VERITEXT_AGAIN\debug_handwritten_crops\debug_page_2\line_03.png",
    ]
    for c in test_crops:
        if Path(c).exists():
            test_rec(c)
