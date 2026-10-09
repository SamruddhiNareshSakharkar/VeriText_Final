import os
import sys
import urllib.request
import time

WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "weights", "trocr")
os.makedirs(WEIGHTS_DIR, exist_ok=True)

BASE_URL = "https://huggingface.co/Xenova/trocr-base-handwritten/resolve/main"

FILES = [
    ("config.json", f"{BASE_URL}/config.json", 4536),
    ("generation_config.json", f"{BASE_URL}/generation_config.json", 185),
    ("preprocessor_config.json", f"{BASE_URL}/preprocessor_config.json", 378),
    ("tokenizer.json", f"{BASE_URL}/tokenizer.json", 2108614),
    ("tokenizer_config.json", f"{BASE_URL}/tokenizer_config.json", 1376),
    ("special_tokens_map.json", f"{BASE_URL}/special_tokens_map.json", 957),
    ("vocab.json", f"{BASE_URL}/vocab.json", 798293),
    ("merges.txt", f"{BASE_URL}/merges.txt", 456318),
    ("encoder_model_quantized.onnx", f"{BASE_URL}/onnx/encoder_model_quantized.onnx", 88082928),
    ("decoder_model_merged_quantized.onnx", f"{BASE_URL}/onnx/decoder_model_merged_quantized.onnx", 249586419),
    ("decoder_model_quantized.onnx", f"{BASE_URL}/onnx/decoder_model_quantized.onnx", 248858277),
]

def download_file(filename, url, expected_size):
    dest_path = os.path.join(WEIGHTS_DIR, filename)
    if os.path.exists(dest_path):
        actual_size = os.path.getsize(dest_path)
        if expected_size > 0 and abs(actual_size - expected_size) < 1000:
            print(f"[EXISTS & VALID] {filename} ({actual_size} bytes)")
            return True
        else:
            print(f"[CORRUPT/PARTIAL] {filename} has {actual_size} bytes, expected {expected_size}. Redownloading...")
            os.remove(dest_path)

    print(f"[DOWNLOADING] {filename}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as f:
        total_size = int(resp.info().get("Content-Length", expected_size))
        downloaded = 0
        chunk_size = 1024 * 1024
        t0 = time.time()
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            mb = downloaded / (1024 * 1024)
            tot_mb = total_size / (1024 * 1024)
            speed = mb / max(time.time() - t0, 0.1)
            pct = (downloaded / max(total_size, 1)) * 100
            print(f"\r  -> {filename}: {mb:.1f}/{tot_mb:.1f} MB ({pct:.1f}%) @ {speed:.2f} MB/s", end="", flush=True)
        print()
    print(f"[SUCCESS] Saved {filename} ({os.path.getsize(dest_path)} bytes)")
    return True

def main():
    print(f"=== DOWNLOADING TrOCR ONNX WEIGHTS TO {WEIGHTS_DIR} ===")
    for filename, url, size in FILES:
        download_file(filename, url, size)
    print("=== ALL WEIGHTS DOWNLOADED & VERIFIED ===")

if __name__ == "__main__":
    main()
