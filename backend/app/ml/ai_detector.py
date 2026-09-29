import re
import math
from collections import Counter
from typing import Dict, Any, List, Tuple


class AIContentDetector:
    """
    Advanced Multi-Feature AI Content Stylometry & Highlighting Engine.
    Combines sentence-level burstiness, perplexity heuristics, vocabulary predictability,
    and syntactic formulaic markers to identify AI-generated passages with exact character offsets.
    """

    def __init__(self):
        # AI formulaic transitional phrases (multi-word patterns)
        self.ai_phrases = [
            "in conclusion",
            "it is important to note",
            "it is worth noting",
            "furthermore",
            "moreover",
            "in addition",
            "overall",
            "it can be concluded",
            "this highlights the importance",
            "plays a crucial role",
            "plays a pivotal role",
            "as mentioned earlier",
            "from the above discussion",
            "to summarize",
            "in summary",
            "on the other hand",
            "it is evident that",
            "it should be emphasized",
            "stands as a testament",
            "serves as a testament",
            "sheds light on",
            "delve deeper into",
            "delving into",
            "a multifaceted approach",
            "in today's rapidly evolving",
            "in an increasingly digital world",
            "a cornerstone of",
            "vital component in",
        ]

        # Lexical markers heavily overrepresented in contemporary LLM generations
        self.ai_keywords = {
            "delve", "delving", "testament", "tapestry", "crucial", "paramount",
            "beacon", "foster", "fostering", "imperative", "underscore", "underscores",
            "underscoring", "seamlessly", "harnessing", "multifaceted", "plethora",
            "myriad", "cornerstone", "transformative", "nuanced", "pivotal",
            "intricate", "paramount", "ubiquitous", "intertwined", "catalyst",
            "exemplifies", "indispensable", "overarching", "encompasses"
        }

        # Precompiled regexes for high performance
        self._compiled_phrases = [
            (phrase, re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE))
            for phrase in self.ai_phrases
        ]
        self._word_re = re.compile(r"\b[a-zA-Z]+\b")
        self._sentence_split_re = re.compile(r"([.!?]+(?:\s+|$))")

    def _words(self, text: str) -> List[str]:
        return self._word_re.findall(text.lower())

    def _sentences_with_spans(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Splits text into sentences while retaining exact character start and end offsets.
        """
        sentences = []
        start = 0
        # Use regex to find sentence boundaries (. ! ? followed by whitespace or end of string)
        for match in re.finditer(r"[^.!?\n]+(?:[.!?]+(?=[\s\n]|$)|$)", text):
            raw_s = match.group(0)
            if not raw_s.strip():
                continue
            s_start = match.start()
            # Trim leading whitespace for clean bounds
            l_strip = len(raw_s) - len(raw_s.lstrip())
            r_strip = len(raw_s) - len(raw_s.rstrip())
            clean_start = s_start + l_strip
            clean_end = match.end() - r_strip
            clean_text = text[clean_start:clean_end]
            if clean_text:
                sentences.append((clean_text, clean_start, clean_end))
        return sentences

    def _sentence_length_variation(self, sentences: List[str]) -> float:
        if not sentences:
            return 0.0

        lengths = [len(self._words(s)) for s in sentences]
        if len(lengths) <= 1:
            return 0.0

        mean = sum(lengths) / len(lengths)
        if mean == 0:
            return 0.0

        variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
        std = math.sqrt(variance)
        return min(std / mean, 1.0)

    def _repetition_score(self, words: List[str]) -> float:
        if len(words) < 2:
            return 0.0

        counts = Counter(words)
        repeated = sum(count - 1 for count in counts.values() if count > 1)
        return min(repeated / len(words), 1.0)

    def _phrase_score(self, text: str) -> float:
        text_lower = text.lower()
        matches = sum(1 for _, pattern in self._compiled_phrases if pattern.search(text_lower))
        return min(matches / 4.0, 1.0)

    def _entropy(self, words: List[str]) -> float:
        if not words:
            return 0.0

        counts = Counter(words)
        total = len(words)
        entropy = 0.0
        for count in counts.values():
            prob = count / total
            entropy -= prob * math.log2(prob)
        return entropy

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Global stylometric evaluation of the entire document.
        """
        if not text or not text.strip():
            return {
                "ai_percentage": 0.0,
                "human_percentage": 100.0,
                "confidence": 0.0,
                "classification": "Insufficient Text",
                "evidence": [],
                "features": {},
            }

        sentences_spans = self._sentences_with_spans(text)
        sentences = [s[0] for s in sentences_spans]
        words = self._words(text)

        if len(words) < 20:
            return {
                "ai_percentage": 0.0,
                "human_percentage": 100.0,
                "confidence": 0.0,
                "classification": "Insufficient Text",
                "evidence": ["At least 20 words are required for analysis."],
                "features": {
                    "word_count": len(words),
                    "sentence_count": len(sentences),
                },
            }

        variation = self._sentence_length_variation(sentences)
        repetition = self._repetition_score(words)
        phrase_score = self._phrase_score(text)
        entropy = self._entropy(words)

        # Keyword density check
        keyword_hits = sum(1 for w in words if w in self.ai_keywords)
        keyword_density = keyword_hits / max(len(words), 1)

        # Normalized entropy
        max_entropy = math.log2(len(set(words))) if len(set(words)) > 1 else 1.0
        entropy_score = entropy / max_entropy if max_entropy else 0.0

        # Dynamic heuristic score
        ai_score = (
            (1.0 - variation) * 0.25
            + repetition * 0.15
            + phrase_score * 0.25
            + entropy_score * 0.20
            + min(keyword_density * 8.0, 0.15)
        )

        ai_percentage = round(max(0.0, min(ai_score * 100.0, 100.0)), 2)
        human_percentage = round(100.0 - ai_percentage, 2)

        if ai_percentage >= 70:
            classification = "Likely AI-Generated"
        elif ai_percentage >= 40:
            classification = "Possibly AI-Assisted"
        else:
            classification = "Likely Human-Written"

        evidence = []
        if variation < 0.25:
            evidence.append("Sentence cadence exhibits uniform, low stylistic burstiness.")
        if repetition > 0.20:
            evidence.append("Repetitive vocabulary patterns detected across paragraphs.")
        if phrase_score > 0:
            evidence.append("Multiple characteristic AI transitional markers detected.")
        if keyword_hits >= 2:
            evidence.append(f"High concentration of LLM-characteristic vocabulary ({keyword_hits} signature terms).")
        if entropy_score > 0.75:
            evidence.append("Vocabulary distribution shows high predictable uniformity.")

        confidence = round(min(100.0, 50.0 + abs(ai_percentage - 50.0)), 2)

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
                "keyword_hits": keyword_hits
            },
        }

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Main entry point for pipeline. Performs global analysis and detailed
        sentence-level AI span detection and consolidation.
        """
        result = self.analyze(text)
        words = self._words(text)
        sentences_with_spans = self._sentences_with_spans(text)

        detected_spans = []

        # 1. Sentence-level analysis: score each sentence individually
        for sentence_text, start_idx, end_idx in sentences_with_spans:
            s_words = self._words(sentence_text)
            if len(s_words) < 5:
                continue

            # Check phrases in this sentence
            matched_phrases = [
                phrase for phrase, pattern in self._compiled_phrases
                if pattern.search(sentence_text)
            ]

            # Check keywords in this sentence
            matched_keywords = [w for w in s_words if w in self.ai_keywords]

            # Calculate local sentence score
            local_score = 0.0
            reasons = []

            if matched_phrases:
                local_score += 0.45 * min(len(matched_phrases), 2)
                reasons.append(f"Transition marker: '{matched_phrases[0]}'")

            if matched_keywords:
                local_score += 0.25 * min(len(matched_keywords), 2)
                reasons.append(f"Signature lexical markers: {', '.join(matched_keywords[:2])}")

            # AI sentences typically have 15-32 words with smooth balanced clauses
            if 14 <= len(s_words) <= 34:
                local_score += 0.15

            # Global bias: if the document as a whole has high AI percentage, calibrate sentences
            if result["ai_percentage"] >= 60.0:
                local_score += 0.20
            elif result["ai_percentage"] >= 40.0:
                local_score += 0.10

            # Threshold for flagging an AI sentence span
            if local_score >= 0.40 or len(matched_phrases) > 0 or len(matched_keywords) >= 2:
                conf = round(min(0.98, max(0.65, local_score)), 2)
                reason_str = " • ".join(reasons) if reasons else "Formulaic sentence cadence and predictable lexical entropy"
                detected_spans.append({
                    "start": start_idx,
                    "end": end_idx,
                    "text": sentence_text,
                    "confidence": conf,
                    "reason": reason_str
                })

        # 2. Also check any standalone phrase occurrences if not covered by sentence spans
        for phrase, pattern in self._compiled_phrases:
            for m in pattern.finditer(text):
                p_start, p_end = m.start(), m.end()
                # Check if already covered by an existing sentence span
                already_covered = any(
                    s["start"] <= p_start and s["end"] >= p_end
                    for s in detected_spans
                )
                if not already_covered:
                    detected_spans.append({
                        "start": p_start,
                        "end": p_end,
                        "text": text[p_start:p_end],
                        "confidence": 0.85,
                        "reason": f"Characteristic formulaic transition phrase: '{phrase}'"
                    })

        # 3. Sort spans chronologically by start offset
        detected_spans.sort(key=lambda s: s["start"])

        # 4. Merge adjacent/overlapping spans within 4 characters (e.g. whitespace between sentences)
        merged_spans = []
        if detected_spans:
            curr = detected_spans[0]
            for nxt in detected_spans[1:]:
                if nxt["start"] <= curr["end"] + 4:
                    # Merge contiguous spans
                    new_end = max(curr["end"], nxt["end"])
                    new_text = text[curr["start"]:new_end]
                    new_conf = round(max(curr["confidence"], nxt["confidence"]), 2)
                    new_reason = curr["reason"] if curr["reason"] == nxt["reason"] else f"{curr['reason']}; {nxt['reason']}"
                    curr = {
                        "start": curr["start"],
                        "end": new_end,
                        "text": new_text,
                        "confidence": new_conf,
                        "reason": new_reason[:150]
                    }
                else:
                    merged_spans.append(curr)
                    curr = nxt
            merged_spans.append(curr)
        else:
            merged_spans = []

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
            "detected_spans": merged_spans,
            "classification": result["classification"],
            "analysis_metadata": {
                "word_count": len(words),
                "sentence_count": len(sentences_with_spans),
                "classification": result["classification"],
                "evidence": result["evidence"],
                "features": features
            }
        }


detector = AIContentDetector()
AIDetector = AIContentDetector
ai_detector = detector


def detect_ai_content(text: str) -> Dict[str, Any]:
    return detector.analyze(text)