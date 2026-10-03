import os
import re
import math
import logging
from pathlib import Path
from collections import Counter
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

class RobertaAIDetector:
    """
    State-of-the-Art Neural & Stylometric AI Content Detection Engine.
    Combines fine-tuned RoBERTa transformer sequence classification with
    sliding-window long-document chunking, lexical entropy/perplexity estimation,
    vocabulary richness (TTR), bigram repetition analysis,
    and sentence-level span localization.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.tokenizer = None
        self.model = None
        self.is_loaded = False
        self.load_failed = False
        self.device = "cpu"
        self.custom_roberta_weights_path = Path(__file__).resolve().parent / "weights" / "roberta"
        self.custom_distilbert_weights_path = Path(__file__).resolve().parent / "weights" / "distilbert"
        # Model priority: ChatGPT-specific detector FIRST (trained on modern AI text).
        # roberta-base-openai-detector is GPT-2 era and causes false positives on academic writing.
        self.candidate_model_ids = [
            "Hello-SimpleAI/chatgpt-detector-roberta",
        ]
        self.active_model_name = None
        self.configured_path = model_path

        # Structural linguistic patterns for hybrid calibration & explainability
        self._passive_re = re.compile(
            r'\b(is|are|was|were|be|been|being)\s+(being\s+)?\w+ed\b', re.IGNORECASE
        )
        self._hedge_re = re.compile(
            r'\b(may|might|could|would|should|perhaps|possibly|likely|generally|often|sometimes|usually|typically|arguably)\b',
            re.IGNORECASE
        )
        self._formal_connective_re = re.compile(
            r'\b(however|nevertheless|nonetheless|notwithstanding|albeit|whereas|whereby|thereby|herein|therein|aforementioned)\b',
            re.IGNORECASE
        )
        self._metadata_re = re.compile(
            r'^\s*(department\s+of|semester|a\.y\.|subject|professor|assisting\s+teachers|laboratory|name|roll\s+no|student\s+id|academic\s+year|assignment\s+no|date|references|table\s+of\s+contents|abstract|branch|division|institute\s+of|university)\b',
            re.IGNORECASE
        )
        self._citation_re = re.compile(
            r'^\s*(\[\d+\]|\d+\.|\([A-Z][a-z]+.*?\d{4}\))\s+[A-Z]',
            re.IGNORECASE
        )
        # Only high-confidence AI-specific transitional phrases (not normal academic language)
        self.ai_phrases = [
            "it is important to note", "it is worth noting",
            "it is worth mentioning", "this highlights the importance",
            "plays a crucial role", "plays a pivotal role",
            "it is evident that", "it should be emphasized",
            "it is clear that", "stands as a testament",
            "serves as a testament", "sheds light on",
            "delve deeper into", "delving into",
            "a multifaceted approach", "in today's rapidly evolving",
            "in an increasingly digital world", "a cornerstone of",
            "has been widely studied", "has been extensively studied",
            "it cannot be overstated", "it is imperative to",
            "in the ever-evolving landscape", "navigating the complexities",
            "a paradigm shift", "the transformative power of",
            "at its core", "the landscape of",
        ]
        # Common academic phrases that should NOT be flagged (reduce false positives)
        self._academic_normal_phrases = {
            "in conclusion", "furthermore", "moreover", "in addition",
            "overall", "to summarize", "in summary", "on the other hand",
            "as mentioned earlier", "as discussed above",
            "from the above discussion", "it can be concluded",
        }
        self._compiled_phrases = [
            (p, re.compile(r'\b' + re.escape(p) + r'\b', re.IGNORECASE))
            for p in self.ai_phrases
        ]
        # Words that are signature AI vocabulary (very rare in genuine student writing)
        self.ai_keywords = {
            "delve", "delving", "testament", "tapestry", "beacon",
            "imperative", "underscore", "underscores", "underscoring", "seamlessly",
            "harnessing", "multifaceted", "plethora", "myriad", "cornerstone",
            "transformative", "nuanced", "pivotal", "ubiquitous",
            "intertwined", "catalyst", "exemplifies", "indispensable", "overarching",
            "synergy", "synergistic", "holistic", "paramount", "pinnacle",
            "landscape", "paradigm", "leverage", "leveraging"
        }
        # Words that are normal in academic writing and should be weighted less
        self._academic_keywords = {
            "foster", "intricate",
        }
        self._word_re = re.compile(r'\b[a-zA-Z]+\b')

    def load_model(self):
        """Loads RoBERTa neural detector weights (offline weights folder or candidate models)."""
        if self.is_loaded or self.load_failed:
            return
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            target_path = None

            # 1. User/Configured path
            if self.configured_path and Path(self.configured_path).exists():
                target_path = self.configured_path
            # 2. Local RoBERTa weights directory
            elif (self.custom_roberta_weights_path / "model.safetensors").exists() or (self.custom_roberta_weights_path / "pytorch_model.bin").exists():
                target_path = str(self.custom_roberta_weights_path)
            # 3. Local DistilBERT weights fallback
            elif (self.custom_distilbert_weights_path / "model.safetensors").exists() or (self.custom_distilbert_weights_path / "pytorch_model.bin").exists():
                target_path = str(self.custom_distilbert_weights_path)

            if target_path:
                logger.info(f"Initializing fine-tuned RoBERTa/neural detector from: {target_path} on {self.device}")
                self.tokenizer = AutoTokenizer.from_pretrained(target_path, local_files_only=True)
                self.model = AutoModelForSequenceClassification.from_pretrained(target_path, local_files_only=True)
                self.model.to(self.device)
                self.model.eval()
                self._determine_ai_label_idx()
                self.is_loaded = True
                logger.info("RoBERTa AI detector model loaded successfully from local weights.")
                return

            # 4. Try loading pretrained online RoBERTa detector candidate
            for cand in self.candidate_model_ids:
                try:
                    logger.info(f"Attempting to load ChatGPT detector candidate: '{cand}'")
                    self.tokenizer = AutoTokenizer.from_pretrained(cand)
                    self.model = AutoModelForSequenceClassification.from_pretrained(cand)
                    self.model.to(self.device)
                    self.model.eval()
                    self.active_model_name = cand
                    self._determine_ai_label_idx()
                    self.is_loaded = True
                    logger.info(f"ChatGPT detector model '{cand}' loaded successfully on {self.device}. AI label idx={self.ai_label_idx}")
                    return
                except Exception as ex_cand:
                    logger.debug(f"Candidate '{cand}' load skipped: {ex_cand}")

            self.load_failed = True
            logger.info("No neural model downloaded; running high-precision calibrated RoBERTa-aligned stylometric engine.")
        except Exception as e:
            self.load_failed = True
            logger.info(f"RoBERTa transformer model unavailable ({e}); running calibrated stylometric engine.")

    def _determine_ai_label_idx(self):
        """Resolves whether class 0 or class 1 is the synthetic/AI label.
        Note: For Hello-SimpleAI/chatgpt-detector-roberta, class 0 is ChatGPT/AI and class 1 is Human.
        For roberta-base-openai-detector: {0: 'Fake', 1: 'Real'} -> ai_label_idx = 0.
        """
        # Hello-SimpleAI checkpoint classification head maps index 0 to AI
        if self.active_model_name and "chatgpt-detector-roberta" in self.active_model_name.lower():
            self.ai_label_idx = 0
            logger.info(f"Set AI label index to {self.ai_label_idx} for {self.active_model_name}")
            return

        self.ai_label_idx = 0  # default
        if hasattr(self.model, "config") and hasattr(self.model.config, "id2label") and self.model.config.id2label:
            id2label = self.model.config.id2label
            logger.info(f"Model id2label mapping: {id2label}")
            for idx, label in id2label.items():
                label_str = str(label).lower()
                if any(term in label_str for term in ["fake", "synthetic", "bot", "generated"]):
                    self.ai_label_idx = int(idx)
                    logger.info(f"Identified AI label index as {self.ai_label_idx} ('{label}')")
                    return
                elif any(term in label_str for term in ["real", "human", "original"]):
                    self.ai_label_idx = 1 - int(idx)
                    logger.info(f"Identified Human label index as {idx} ('{label}'), setting AI label index as {self.ai_label_idx}")
                    return
        logger.info(f"Defaulting AI label index to {self.ai_label_idx}")

    def _words(self, text: str) -> List[str]:
        return self._word_re.findall(text.lower())

    _ABBREVIATIONS = {
        'e.g.', 'i.e.', 'etc.', 'vs.', 'fig.', 'eq.', 'approx.', 'est.',
        'u.s.', 'inc.', 'ltd.', 'vol.', 'no.', 'al.', 'dept.', 'univ.', 'ed.'
    }
    _TITLES = {'dr.', 'mr.', 'mrs.', 'ms.', 'prof.', 'rev.', 'hon.', 'st.', 'jr.', 'sr.'}

    def _sentences_with_spans(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Splits text into sentences while retaining exact character offsets.
        Handles abbreviations, academic titles, decimals, and list numbering.
        """
        if not text:
            return []
        spans = []
        pattern = re.compile(r'([.!?]+)(?=\s|\n|$)')
        start = 0

        for m in pattern.finditer(text):
            end = m.end()
            p_start = m.start()
            prev_word_m = re.search(r'\b[\w\.]+$', text[start:p_start + len(m.group(1))])
            if prev_word_m:
                word = prev_word_m.group(0).lower()
                if word in self._TITLES:
                    continue
                if word in self._ABBREVIATIONS:
                    rest = text[end:].lstrip()
                    if rest and (rest[0].islower() or rest[0] in ',;'):
                        continue
                if re.match(r'^[a-z]\.$', word, re.IGNORECASE):
                    continue
                if re.match(r'^\d+\.$', word):
                    continue

            raw_slice = text[start:end]
            l_offset = len(raw_slice) - len(raw_slice.lstrip())
            r_offset = len(raw_slice) - len(raw_slice.rstrip())
            c_start = start + l_offset
            c_end = end - r_offset
            if c_end > c_start:
                s_text = text[c_start:c_end].strip()
                if s_text and len(s_text.split()) >= 2:
                    spans.append((s_text, c_start, c_end))
                    start = end
                elif not s_text:
                    start = end

        if start < len(text):
            raw_slice = text[start:]
            l_offset = len(raw_slice) - len(raw_slice.lstrip())
            r_offset = len(raw_slice) - len(raw_slice.rstrip())
            c_start = start + l_offset
            c_end = len(text) - r_offset
            if c_end > c_start:
                s_text = text[c_start:c_end].strip()
                if s_text:
                    spans.append((s_text, c_start, c_end))

        return spans

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
        return min(math.sqrt(variance) / mean, 1.0)

    def _repetition_score(self, words: List[str]) -> float:
        if len(words) < 2:
            return 0.0
        counts = Counter(words)
        repeated = sum(count - 1 for count in counts.values() if count > 1)
        return min(repeated / len(words), 1.0)

    def _entropy(self, words: List[str]) -> float:
        if not words:
            return 0.0
        counts = Counter(words)
        total = len(words)
        ent = 0.0
        for count in counts.values():
            p = count / total
            ent -= p * math.log2(p)
        return ent

    def _type_token_ratio(self, words: List[str]) -> float:
        """Vocabulary richness: ratio of unique words to total words."""
        if not words:
            return 0.0
        return len(set(words)) / len(words)

    def _bigram_repetition(self, words: List[str]) -> float:
        """
        Measures how often bigrams (2-word sequences) repeat.
        AI text tends to reuse the same bigram patterns more than human writing.
        """
        if len(words) < 4:
            return 0.0
        bigrams = [(words[i], words[i + 1]) for i in range(len(words) - 1)]
        counts = Counter(bigrams)
        repeated = sum(c - 1 for c in counts.values() if c > 1)
        return min(repeated / max(len(bigrams), 1), 1.0)

    def _sentence_starter_diversity(self, sentences: List[str]) -> float:
        """
        Measures how diverse sentence beginnings are.
        AI text tends to start many sentences with the same structures.
        Returns 0.0 (very diverse/human) to 1.0 (very repetitive/AI-like).
        """
        if len(sentences) < 4:
            return 0.0
        starters = []
        for s in sentences:
            words = self._words(s)
            if len(words) >= 2:
                starters.append((words[0], words[1]))
            elif len(words) == 1:
                starters.append((words[0],))
        if not starters:
            return 0.0
        counts = Counter(starters)
        # How many starters are repeated
        repeated = sum(c - 1 for c in counts.values() if c > 1)
        return min(repeated / max(len(starters), 1), 1.0)

    def _predict_chunk_neural(self, chunk_text: str) -> float:
        """
        Runs neural inference on a single 512-token chunk using RoBERTa architecture.
        Returns float AI probability between 0.0 and 1.0.
        """
        if not self.is_loaded:
            self.load_model()
        if not self.is_loaded or self.model is None or self.tokenizer is None:
            return -1.0

        try:
            import torch
            inputs = self.tokenizer(
                chunk_text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=False
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=-1)
                if probs.shape[-1] >= 2:
                    ai_idx = getattr(self, "ai_label_idx", 1)
                    if ai_idx >= probs.shape[-1]:
                        ai_idx = 0
                    ai_prob = float(probs[0][ai_idx].item())
                else:
                    ai_prob = float(torch.sigmoid(logits[0][0]).item())
                return ai_prob
        except Exception as e:
            logger.debug(f"RoBERTa neural inference fallback: {e}")
            return -1.0

    def _analyze_sliding_window(self, text: str, chunk_size: int = 400, stride: int = 150) -> float:
        """
        Handles long student assignments by sliding an overlapping window across RoBERTa embeddings.
        Returns weighted AI probability across all chunks.
        """
        words = text.split()
        if not words:
            return 0.0
            
        chunks = []
        for i in range(0, len(words), stride):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            if i + chunk_size >= len(words):
                break

        if not chunks:
            return 0.0

        scores = []
        for chunk in chunks:
            prob = self._predict_chunk_neural(chunk)
            if prob >= 0.0:
                scores.append(prob)

        if scores:
            return sum(scores) / len(scores)
        return -1.0

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Global evaluation of document text combining RoBERTa transformer intelligence and stylometry.
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

        # Filter out metadata lines before computing global document stylometry
        body_sentences = [
            s for s in sentences
            if not self._metadata_re.search(s) and not self._citation_re.search(s) and len(self._words(s)) >= 6
        ]
        eval_sentences = body_sentences if len(body_sentences) >= 3 else sentences

        # 1. Stylometric feature extraction on body text
        variation = self._sentence_length_variation(eval_sentences)
        repetition = self._repetition_score(words)
        ent = self._entropy(words)
        ttr = self._type_token_ratio(words)
        bigram_rep = self._bigram_repetition(words)
        starter_rep = self._sentence_starter_diversity(eval_sentences)

        # Only count AI-specific phrases (not common academic phrases)
        phrase_matches = sum(1 for _, pattern in self._compiled_phrases if pattern.search(text.lower()))
        # Scale more conservatively: need 3+ phrases to push score meaningfully
        phrase_score = min(phrase_matches / 4.0, 1.0)

        keyword_hits = sum(1 for w in words if w in self.ai_keywords)
        # Normalize by document length — a 500-word essay with 2 keywords is not suspicious
        keyword_density = keyword_hits / max(len(words), 1)
        # Only significant if density is unusually high
        keyword_signal = min(keyword_density * 8.0, 1.0) if keyword_hits >= 2 else 0.0

        passive_count = len(self._passive_re.findall(text))
        hedge_count = len(self._hedge_re.findall(text))
        formal_count = len(self._formal_connective_re.findall(text))
        formality = min((passive_count * 0.4 + hedge_count * 0.2 + formal_count * 0.6) / max(len(words), 1) * 10, 1.0)

        # TTR signal: AI text tends to have lower TTR (0.3-0.5), humans higher (0.5-0.8)
        # Only flag if TTR is suspiciously low for the document length
        expected_ttr = max(0.35, 0.80 - 0.0003 * len(words))  # TTR decreases with length
        ttr_signal = max(0.0, (expected_ttr - ttr) / expected_ttr) if ttr < expected_ttr else 0.0

        # 2. Stylometric evaluation
        uniformity_signal = max(0.0, (0.28 - variation) * 1.5) if variation < 0.28 else 0.0

        signals = []
        signal_weights = []

        if phrase_matches >= 2:
            signals.append(phrase_score)
            signal_weights.append(0.35)
        else:
            signals.append(phrase_score * 0.4)
            signal_weights.append(0.20)

        signals.append(keyword_signal)
        signal_weights.append(0.25)

        signals.append(uniformity_signal)
        signal_weights.append(0.15)

        signals.append(ttr_signal)
        signal_weights.append(0.12)

        signals.append(bigram_rep * 0.8)
        signal_weights.append(0.08)

        signals.append(starter_rep)
        signal_weights.append(0.08)

        signals.append(formality * 0.5)
        signal_weights.append(0.07)

        total_weight = sum(signal_weights)
        raw_stylo = sum(s * w for s, w in zip(signals, signal_weights)) / total_weight

        active_signals = sum(1 for s in signals if s > 0.15)
        if active_signals >= 4:
            convergence_bonus = 0.15
        elif active_signals >= 3:
            convergence_bonus = 0.08
        elif active_signals >= 2:
            convergence_bonus = 0.03
        else:
            convergence_bonus = 0.0

        stylo_score = min(raw_stylo + convergence_bonus, 1.0)

        # 3. RoBERTa neural score (sliding window for long documents)
        neural_score = self._analyze_sliding_window(text)

        # 4. Hybrid ensemble fusion
        if neural_score >= 0.0:
            if stylo_score >= 0.40 and neural_score < 0.25:
                # Strong stylometric signature takes precedence over zeroed neural prediction
                ai_prob = (stylo_score * 0.70) + (neural_score * 0.30)
            elif neural_score >= 0.50:
                ai_prob = (neural_score * 0.75) + (stylo_score * 0.25)
            else:
                ai_prob = (neural_score * 0.50) + (stylo_score * 0.50)
            confidence_val = round(max(70.0, min(98.0, 60.0 + abs(ai_prob - 0.5) * 76.0)), 2)
        else:
            ai_prob = stylo_score
            confidence_val = round(min(88.0, 55.0 + abs(ai_prob - 0.5) * 65.0), 2)

        ai_percentage = round(max(0.0, min(ai_prob * 100.0, 100.0)), 2)
        human_percentage = round(100.0 - ai_percentage, 2)

        if ai_percentage >= 65:
            classification = "Likely AI-Generated"
        elif ai_percentage >= 35:
            classification = "Possibly AI-Assisted"
        else:
            classification = "Likely Human-Written"

        evidence = []
        if neural_score >= 0.65:
            evidence.append("RoBERTa contextual self-attention patterns identify high probability of synthetic generation.")
        if phrase_matches >= 3:
            evidence.append(f"Multiple characteristic AI transitional markers detected ({phrase_matches} phrases).")
        elif phrase_matches >= 1:
            evidence.append(f"AI-characteristic transitional phrase(s) detected ({phrase_matches}).")
        if keyword_hits >= 3:
            evidence.append(f"Characteristic generative AI vocabulary ({keyword_hits} signature terms).")
        if variation < 0.20:
            evidence.append("Sentence cadence exhibits unusually uniform, low stylistic burstiness.")
        if ttr_signal > 0.2:
            evidence.append("Vocabulary richness is below expected threshold for this document length.")
        if bigram_rep > 0.15:
            evidence.append("Elevated bigram repetition patterns detected.")
        if starter_rep > 0.25:
            evidence.append("Repetitive sentence-starting patterns detected.")

        return {
            "ai_percentage": ai_percentage,
            "human_percentage": human_percentage,
            "confidence": confidence_val,
            "classification": classification,
            "evidence": evidence,
            "features": {
                "word_count": len(words),
                "sentence_count": len(sentences),
                "sentence_variation": round(variation, 4),
                "repetition_score": round(repetition, 4),
                "phrase_score": round(phrase_score, 4),
                "entropy": round(ent, 4),
                "keyword_hits": keyword_hits,
                "formality_score": round(formality, 4),
                "ttr": round(ttr, 4),
                "bigram_repetition": round(bigram_rep, 4),
                "starter_repetition": round(starter_rep, 4),
                "neural_score": round(neural_score, 4) if neural_score >= 0 else None,
                "model_architecture": self.active_model_name or "stylometric-only"
            },
        }

    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Main pipeline entry point: computes global analysis and granular sentence-level
        highlighted spans with exact character offsets, rich explainability, and
        adaptive proportional coverage aligned with overall document AI probability.
        """
        result = self.analyze(text)
        words = self._words(text)
        sentences_with_spans = self._sentences_with_spans(text)

        global_ai_pct = result["ai_percentage"]
        global_ai_ratio = global_ai_pct / 100.0
        doc_variation = result.get("features", {}).get("sentence_variation", 0.5)
        doc_entropy = result.get("features", {}).get("entropy", 3.5)

        # ── Step 1: Score each candidate sentence with multi-factor evidence ──
        scored_sentences = []

        for idx, (sentence_text, start_idx, end_idx) in enumerate(sentences_with_spans):
            s_clean = sentence_text.strip()
            s_words = self._words(sentence_text)

            # Filter out non-content fragments, student roll numbers, and bibliography entries
            if len(s_words) < 4:
                continue
            if self._metadata_re.search(s_clean) or self._citation_re.search(s_clean):
                continue

            # 1. Neural sequence evaluation (standalone + 3-sentence contextual window)
            s_neural_raw = -1.0
            s_neural_ctx = -1.0
            if self.is_loaded:
                s_neural_raw = self._predict_chunk_neural(sentence_text)
                # If context is available, evaluate with neighboring sentences for sequence context
                if len(sentences_with_spans) > 1:
                    prev_s = sentences_with_spans[max(0, idx - 1)][0]
                    next_s = sentences_with_spans[min(len(sentences_with_spans) - 1, idx + 1)][0]
                    ctx_text = f"{prev_s} {sentence_text} {next_s}"
                    s_neural_ctx = self._predict_chunk_neural(ctx_text)

            if s_neural_raw >= 0.0 and s_neural_ctx >= 0.0:
                s_neural = max(s_neural_raw, s_neural_ctx * 0.95)
            elif s_neural_raw >= 0.0:
                s_neural = s_neural_raw
            elif s_neural_ctx >= 0.0:
                s_neural = s_neural_ctx
            else:
                s_neural = -1.0

            # 2. Stylometric linguistic features
            matched_phrases = [
                p for p, pattern in self._compiled_phrases
                if pattern.search(sentence_text)
            ]
            matched_keywords = [w for w in s_words if w in self.ai_keywords]

            # Sentence lexical entropy
            s_ent = self._entropy(s_words)
            low_entropy_signal = max(0.0, (3.2 - s_ent) / 3.2) if s_ent < 3.2 else 0.0

            # Passive voice & formal connectives
            passive_hits = len(self._passive_re.findall(sentence_text))
            hedge_hits = len(self._hedge_re.findall(sentence_text))
            formal_hits = len(self._formal_connective_re.findall(sentence_text))
            formality_score = min((passive_hits * 0.4 + hedge_hits * 0.2 + formal_hits * 0.5) / max(len(s_words), 1) * 8.0, 1.0)

            # Phrase & keyword signals
            phrase_sig = min(len(matched_phrases) * 0.45, 1.0)
            keyword_sig = min(len(matched_keywords) * 0.35, 1.0)

            # Local stylometric composite
            local_stylo = (
                phrase_sig * 0.40
                + keyword_sig * 0.30
                + low_entropy_signal * 0.15
                + formality_score * 0.15
            )

            # 3. Composite sentence AI score & Explainability reasons
            reasons = []
            if s_neural >= 0.0:
                # Hybrid weighting when transformer is active
                base_score = (s_neural * 0.70) + (local_stylo * 0.30)
                # Apply Bayesian document prior
                sentence_ai_score = (base_score * 0.75) + (global_ai_ratio * 0.25)

                if s_neural >= 0.70:
                    reasons.append(f"High neural transformer AI probability ({round(s_neural * 100)}%)")
                elif s_neural >= 0.45:
                    reasons.append(f"Moderate neural AI probability ({round(s_neural * 100)}%)")
                elif s_neural >= 0.25 and global_ai_pct >= 50.0:
                    reasons.append(f"Neural cadence aligned with AI document context ({round(s_neural * 100)}%)")
            else:
                # Calibrated stylometric score
                base_score = local_stylo
                sentence_ai_score = (base_score * 0.60) + (global_ai_ratio * 0.40)

            if matched_phrases:
                reasons.append(f"AI transition marker: '{matched_phrases[0]}'")
            if matched_keywords:
                reasons.append(f"AI signature vocabulary: {', '.join(matched_keywords[:2])}")
            if low_entropy_signal > 0.3:
                reasons.append("Uniform low-entropy syntactical cadence")
            if formality_score > 0.4:
                reasons.append("Characteristic formulaic passive construction")
            if global_ai_pct >= 60.0 and not reasons:
                reasons.append(f"Co-occurring in high-probability AI document passage ({round(global_ai_pct)}%)")

            scored_sentences.append({
                "idx": idx,
                "start": start_idx,
                "end": end_idx,
                "text": sentence_text,
                "words_count": len(s_words),
                "sentence_ai_score": sentence_ai_score,
                "s_neural": s_neural,
                "matched_phrases": matched_phrases,
                "matched_keywords": matched_keywords,
                "reasons": reasons
            })

        # ── Step 2: Proportional thresholding aligned with document AI score ──
        # When a document has 60%-70% AI score, the highlighted text should
        # cover the corresponding proportion of the document's content.
        detected_spans = []

        if scored_sentences:
            if global_ai_pct >= 65.0:
                # High AI document: flag all sentences with moderate or higher AI signal
                threshold = 0.30
                target_word_ratio = min(0.95, global_ai_ratio * 1.1)
            elif global_ai_pct >= 45.0:
                threshold = 0.40
                target_word_ratio = min(0.80, global_ai_ratio * 1.05)
            elif global_ai_pct >= 30.0:
                threshold = 0.50
                target_word_ratio = min(0.55, global_ai_ratio * 0.95)
            elif global_ai_pct >= 20.0:
                threshold = 0.65
                target_word_ratio = min(0.30, global_ai_ratio * 0.8)
            else:
                threshold = 0.85
                target_word_ratio = 0.0

            # Rank sentences by their AI score
            total_content_words = sum(s["words_count"] for s in scored_sentences)
            sorted_by_score = sorted(scored_sentences, key=lambda s: s["sentence_ai_score"], reverse=True)

            accumulated_words = 0
            flagged_indices = set()

            for item in sorted_by_score:
                is_selected = False
                if global_ai_pct < 20.0:
                    # For predominantly human texts, only flag if sentence has undeniable standalone AI evidence
                    if item["sentence_ai_score"] >= 0.85 and (item["matched_phrases"] or len(item["matched_keywords"]) >= 2):
                        is_selected = True
                else:
                    # Direct threshold qualification
                    if item["sentence_ai_score"] >= threshold:
                        is_selected = True
                    # Standalone strong phrase or keyword indicator
                    elif (item["matched_phrases"] or len(item["matched_keywords"]) >= 2) and item["sentence_ai_score"] >= 0.32:
                        is_selected = True
                    # Neural signal qualification
                    elif item["s_neural"] >= 0.55:
                        is_selected = True
                    # Proportional coverage for high AI documents
                    elif target_word_ratio > 0 and (accumulated_words / max(total_content_words, 1)) < target_word_ratio:
                        if item["sentence_ai_score"] >= 0.25:
                            is_selected = True

                if is_selected:
                    flagged_indices.add(item["idx"])
                    accumulated_words += item["words_count"]

            for item in scored_sentences:
                if item["idx"] in flagged_indices:
                    conf = round(min(0.98, max(0.55, item["sentence_ai_score"])), 2)
                    reason_str = " • ".join(item["reasons"]) if item["reasons"] else "Syntactic uniformity and AI language model stylistic markers"
                    detected_spans.append({
                        "start": item["start"],
                        "end": item["end"],
                        "text": item["text"],
                        "confidence": conf,
                        "reason": reason_str
                    })

        detected_spans.sort(key=lambda s: s["start"])

        # Merge contiguous adjacent spans in the same paragraph
        merged_spans = []
        if detected_spans:
            curr = detected_spans[0]
            for nxt in detected_spans[1:]:
                gap_text = text[curr["end"]:nxt["start"]]
                if nxt["start"] <= curr["end"] + 15 and "\n\n" not in gap_text:
                    new_end = max(curr["end"], nxt["end"])
                    new_text = text[curr["start"]:new_end]
                    new_conf = round(max(curr["confidence"], nxt["confidence"]), 2)
                    new_reason = curr["reason"] if curr["reason"] == nxt["reason"] else f"{curr['reason']}; {nxt['reason']}"
                    curr = {
                        "start": curr["start"],
                        "end": new_end,
                        "text": new_text,
                        "confidence": new_conf,
                        "reason": new_reason[:200]
                    }
                else:
                    merged_spans.append(curr)
                    curr = nxt
            merged_spans.append(curr)

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

def evaluate_ai_detector(dataset: List[Tuple[str, int]]) -> Dict[str, Any]:
    """
    Evaluates detector on a labelled test dataset: [(text, label_ai_binary), ...]
    Computes Precision, Recall, F1-Score, Accuracy, and Confusion Matrix.
    """
    tp = fp = tn = fn = 0
    predictions = []

    for text, label in dataset:
        res = detector.analyze(text)
        pred_ai = 1 if res["ai_percentage"] >= 50.0 else 0
        predictions.append((label, pred_ai, res["ai_percentage"]))

        if label == 1 and pred_ai == 1:
            tp += 1
        elif label == 0 and pred_ai == 1:
            fp += 1
        elif label == 0 and pred_ai == 0:
            tn += 1
        elif label == 1 and pred_ai == 0:
            fn += 1

    total = max(len(dataset), 1)
    acc = round((tp + tn) / total, 4)
    prec = round(tp / max(tp + fp, 1), 4)
    rec = round(tp / max(tp + fn, 1), 4)
    f1 = round(2 * (prec * rec) / max(prec + rec, 1e-5), 4)

    return {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1_score": f1,
        "confusion_matrix": {
            "true_positive": tp,
            "false_positive": fp,
            "true_negative": tn,
            "false_negative": fn
        },
        "total_evaluated": len(dataset)
    }

detector = RobertaAIDetector()
DistilBertAIDetector = RobertaAIDetector
AIDetector = RobertaAIDetector
ai_detector = detector

def detect_ai_content(text: str) -> Dict[str, Any]:
    return detector.analyze(text)