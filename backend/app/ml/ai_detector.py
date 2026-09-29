import re
import math
from collections import Counter


class AIContentDetector:
    def __init__(self):
        self.ai_phrases = [
            "in conclusion",
            "it is important to note",
            "furthermore",
            "moreover",
            "in addition",
            "overall",
            "it can be concluded",
            "this highlights the importance",
            "plays a crucial role",
            "it is worth noting",
            "as mentioned earlier",
            "from the above discussion",
        ]

    def _sentences(self, text):
        return [
            s.strip()
            for s in re.split(r"[.!?]+", text)
            if s.strip()
        ]

    def _words(self, text):
        return re.findall(r"\b[a-zA-Z]+\b", text.lower())

    def _sentence_length_variation(self, sentences):
        if not sentences:
            return 0.0

        lengths = [len(self._words(s)) for s in sentences]

        if len(lengths) == 1:
            return 0.0

        mean = sum(lengths) / len(lengths)

        if mean == 0:
            return 0.0

        variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
        std = math.sqrt(variance)

        return min(std / mean, 1.0)

    def _repetition_score(self, words):
        if len(words) < 2:
            return 0.0

        counts = Counter(words)
        repeated = sum(
            count - 1
            for count in counts.values()
            if count > 1
        )

        return min(repeated / len(words), 1.0)

    def _phrase_score(self, text):
        text = text.lower()

        matches = 0

        for phrase in self.ai_phrases:
            if phrase in text:
                matches += 1

        if not self.ai_phrases:
            return 0.0

        return min(matches / 5.0, 1.0)

    def _entropy(self, words):
        if not words:
            return 0.0

        counts = Counter(words)
        total = len(words)

        entropy = 0.0

        for count in counts.values():
            probability = count / total
            entropy -= probability * math.log2(probability)

        return entropy

    def analyze(self, text):
        if not text or not text.strip():
            return {
                "ai_percentage": 0.0,
                "human_percentage": 100.0,
                "confidence": 0.0,
                "classification": "Insufficient Text",
                "evidence": [],
                "features": {},
            }

        sentences = self._sentences(text)
        words = self._words(text)

        if len(words) < 20:
            return {
                "ai_percentage": 0.0,
                "human_percentage": 100.0,
                "confidence": 0.0,
                "classification": "Insufficient Text",
                "evidence": [
                    "At least 20 words are required for analysis."
                ],
                "features": {
                    "word_count": len(words),
                    "sentence_count": len(sentences),
                },
            }

        variation = self._sentence_length_variation(sentences)
        repetition = self._repetition_score(words)
        phrase_score = self._phrase_score(text)
        entropy = self._entropy(words)

        # Normalized entropy.
        max_entropy = math.log2(len(set(words))) if len(set(words)) > 1 else 1
        entropy_score = entropy / max_entropy if max_entropy else 0.0

        # Dynamic heuristic score.
        ai_score = (
            (1.0 - variation) * 0.30
            + repetition * 0.20
            + phrase_score * 0.25
            + entropy_score * 0.25
        )

        ai_percentage = round(
            max(0.0, min(ai_score * 100.0, 100.0)),
            2
        )

        human_percentage = round(100.0 - ai_percentage, 2)

        if ai_percentage >= 70:
            classification = "Likely AI-Generated"
        elif ai_percentage >= 40:
            classification = "Possibly AI-Assisted"
        else:
            classification = "Likely Human-Written"

        evidence = []

        if variation < 0.25:
            evidence.append(
                "Sentence lengths show relatively low variation."
            )

        if repetition > 0.20:
            evidence.append(
                "Repeated vocabulary patterns were detected."
            )

        if phrase_score > 0:
            evidence.append(
                "Common AI-style transitional phrases were detected."
            )

        if entropy_score > 0.75:
            evidence.append(
                "Vocabulary distribution shows relatively high regularity."
            )

        confidence = round(
            min(
                100.0,
                50.0 + abs(ai_percentage - 50.0)
            ),
            2
        )

        return {
            "ai_percentage": ai_percentage,
            "human_percentage": human_percentage,
            "confidence": confidence,
            "classification": classification,
            "evidence": evidence,
            "features": {
                "word_count": len(words),
                "sentence_count": len(sentences),
                "sentence_variation": round(variation, 4),
                "repetition_score": round(repetition, 4),
                "phrase_score": round(phrase_score, 4),
                "entropy": round(entropy, 4),
                "normalized_entropy": round(entropy_score, 4),
            },
        }

    def analyze_text(self, text: str) -> dict:
        result = self.analyze(text)
        words = self._words(text)
        sentences = self._sentences(text)

        detected_spans = []
        for phrase in self.ai_phrases:
            for m in re.finditer(r"\b" + re.escape(phrase) + r"\b", text, re.IGNORECASE):
                detected_spans.append({
                    "start": m.start(),
                    "end": m.end(),
                    "text": text[m.start():m.end()],
                    "confidence": 0.85,
                    "reason": f"Characteristic formulaic transition phrase: '{phrase}'"
                })

        detected_spans.sort(key=lambda s: s["start"])

        features = result.get("features", {})
        variation = features.get("sentence_variation", 0.5)
        entropy_val = features.get("entropy", 3.5)

        perplexity = round(max(1.0, math.exp(min(entropy_val, 6.0) if entropy_val > 0 else 2.5)), 2)
        burstiness = round(variation * 100.0, 2)
        entropy = round(entropy_val, 3)

        return {
            "score": result["ai_percentage"],
            "confidence": result["confidence"],
            "perplexity": perplexity,
            "burstiness": burstiness,
            "entropy": entropy,
            "detected_spans": detected_spans,
            "classification": result["classification"],
            "analysis_metadata": {
                "word_count": len(words),
                "sentence_count": len(sentences),
                "classification": result["classification"],
                "evidence": result["evidence"],
                "features": features
            }
        }


detector = AIContentDetector()
AIDetector = AIContentDetector
ai_detector = detector


def detect_ai_content(text):
    return detector.analyze(text)