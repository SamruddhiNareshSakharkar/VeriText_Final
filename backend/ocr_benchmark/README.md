# VERITEXT Local OCR Benchmark Tool

A standalone, 100% offline evaluation tool to benchmark local handwriting recognition models against human-transcribed ground truth using exact Character Error Rate (CER) and Word Error Rate (WER).

---

## 📁 Folder Structure

```text
backend/ocr_benchmark/
├── images/                  # Place your handwritten line crops here (.png, .jpg)
│   ├── line_001.png
│   ├── line_002.png
│   └── ...
├── ground_truth/            # Place corresponding ground truth text files here
│   ├── line_001.txt
│   ├── line_002.txt
│   └── ...
├── results/                 # Automatically populated with reports & inputs
│   ├── inputs/              # Preprocessed images actually sent to models
│   ├── benchmark_results.csv# Tabular metric comparison
│   ├── benchmark_report.json# Machine-readable evaluation report
│   └── benchmark_report.txt # Human-readable evaluation summary
├── benchmark.py             # Standalone evaluation engine
└── README.md                # Guide and instructions
```

---

## ⚙️ How to Add Test Data

1. **Add Line Crops:**
   Save each handwritten line image inside `backend/ocr_benchmark/images/`:
   - `images/line_001.png`
   - `images/line_002.png`

2. **Add Ground Truth:**
   For every image, save the exact manually transcribed text in `backend/ocr_benchmark/ground_truth/` with the **same base filename**:
   - `ground_truth/line_001.txt` (e.g. containing `The quick brown fox`)
   - `ground_truth/line_002.txt` (e.g. containing `jumped over the lazy dog`)

---

## 🚀 How to Run the Benchmark

From the project root:

```powershell
venv\Scripts\python.exe backend/ocr_benchmark/benchmark.py
```

### Optional Options:
- `--preprocess gentle` (Default: EXIF fix + mild autocontrast + sharpening)
- `--preprocess raw` (Feeds verbatim raw image without extra contrast adjustments)

Example:
```powershell
venv\Scripts\python.exe backend/ocr_benchmark/benchmark.py --preprocess raw
```

---

## 📊 Models Evaluated

1. **TrOCR Base Handwritten (`microsoft/trocr-base-handwritten`):**
   - Vision Transformer Encoder-Decoder with RoBERTa tokenizer.
   - Deterministic Beam Search (`num_beams=4`, `length_penalty=1.0`).
2. **PaddleOCR Local Recognition:**
   - Lightweight local convolutional/recurrent OCR engine (`det=False, rec=True`).

---

## 📈 Output Metrics

- **CER (Character Error Rate):**
  $$\text{CER} = \frac{\text{Substitutions} + \text{Deletions} + \text{Insertions}}{\text{Length of Reference String}}$$
- **WER (Word Error Rate):**
  $$\text{WER} = \frac{\text{Word Substitutions} + \text{Word Deletions} + \text{Word Insertions}}{\text{Number of Reference Words}}$$
- **Latency:** Execution time in seconds per line.
- **Exact Match Rate:** Percentage of lines with $\text{CER} = 0.0$.
