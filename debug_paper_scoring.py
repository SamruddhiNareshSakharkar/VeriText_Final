from backend.app.database.session import SessionLocal
from backend.app.models.entities import Submission, OCRResult
from backend.app.ml.ai_detector import ai_detector

db = SessionLocal()
s = db.query(Submission).filter(Submission.file_name.like("%VeriText_plagarism-detector_Reaserch-ppr%")).first()

if s:
    ocr = db.query(OCRResult).filter(OCRResult.submission_id == s.id).first()
    text = ocr.extracted_text
    print(f"Total characters: {len(text)}, Total words: {len(text.split())}")
    
    # Check how sentences are being split
    sentences = ai_detector._sentences_with_spans(text)
    print(f"Total sentences extracted: {len(sentences)}")
    
    # Print first 25 sentences
    for i, (st, start, end) in enumerate(sentences[:25]):
        words = ai_detector._words(st)
        feat = ai_detector._sentence_features(st)
        print(f"\n[{i+1}] ({len(words)} words) AI score: {feat['ai_score']:.3f} | composite: {feat['composite']:.3f} | reasons: {feat['reasons']}")
        print(f"    Text: {st[:100]}...")

db.close()
