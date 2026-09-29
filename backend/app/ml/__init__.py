from backend.app.ml.ocr_engine import ocr_engine, OCREngine
from backend.app.ml.ai_detector import ai_detector, AIDetector
from backend.app.ml.similarity_engine import similarity_engine, SimilarityEngine
from backend.app.ml.handwriting_engine import handwriting_engine, HandwritingEngine

__all__ = [
    "ocr_engine", "OCREngine",
    "ai_detector", "AIDetector",
    "similarity_engine", "SimilarityEngine",
    "handwriting_engine", "HandwritingEngine"
]
