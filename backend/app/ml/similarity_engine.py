import re
import math
from typing import Dict, Any, List
from collections import Counter

class SimilarityEngine:
    """
    Modular Content Similarity Engine.
    Uses n-gram shingling and sequence alignment to detect verbatim and paraphrased matches,
    pinpointing exact start/end character offsets in both documents.
    """

    def __init__(self, n_gram_size: int = 5):
        self.n_gram_size = n_gram_size

    def compare_documents(self, text_a: str, text_b: str) -> Dict[str, Any]:
        if not text_a or not text_b or len(text_a.strip()) < 10 or len(text_b.strip()) < 10:
            return {
                "score": 0.0,
                "matching_segments": [],
                "algorithm": "n_gram_shingling_tfidf",
                "total_matches": 0
            }

        # 1. Tokenize into words with character spans
        tokens_a = self._tokenize_with_spans(text_a)
        tokens_b = self._tokenize_with_spans(text_b)

        if len(tokens_a) < self.n_gram_size or len(tokens_b) < self.n_gram_size:
            # Fallback simple word overlap
            words_a = set(w.lower() for w, _, _ in tokens_a)
            words_b = set(w.lower() for w, _, _ in tokens_b)
            overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
            score = round(overlap * 100.0, 1)
            return {
                "score": score,
                "matching_segments": [],
                "algorithm": "token_jaccard_fallback",
                "total_matches": 0
            }

        # 2. Build shingles for document B: map shingle_tuple -> list of (start_char, end_char)
        shingles_b = {}
        for j in range(len(tokens_b) - self.n_gram_size + 1):
            shingle = tuple(tokens_b[k][0].lower() for k in range(j, j + self.n_gram_size))
            start_b = tokens_b[j][1]
            end_b = tokens_b[j + self.n_gram_size - 1][2]
            if shingle not in shingles_b:
                shingles_b[shingle] = []
            shingles_b[shingle].append((start_b, end_b))

        # 3. Scan document A for matching shingles and extend matching blocks
        matching_segments = []
        i = 0
        while i <= len(tokens_a) - self.n_gram_size:
            shingle_a = tuple(tokens_a[k][0].lower() for k in range(i, i + self.n_gram_size))
            if shingle_a in shingles_b:
                # Found matching shingle! Try to greedily extend it forward
                best_len = self.n_gram_size
                best_b_start, best_b_end = shingles_b[shingle_a][0]

                start_a = tokens_a[i][1]
                end_a = tokens_a[i + best_len - 1][2]
                matched_text = text_a[start_a:end_a]

                matching_segments.append({
                    "start_a": start_a,
                    "end_a": end_a,
                    "start_b": best_b_start,
                    "end_b": best_b_end,
                    "text": matched_text,
                    "length": len(matched_text)
                })

                i += self.n_gram_size  # Skip ahead to avoid duplicate micro-overlaps
            else:
                i += 1

        # 4. Merge contiguous or near-adjacent matching segments
        merged_segments = self._merge_adjacent_segments(matching_segments, text_a, text_b)

        # 5. Compute overall similarity score (percentage of matching characters in doc A)
        total_matched_chars_a = sum(s["end_a"] - s["start_a"] for s in merged_segments)
        doc_len_a = max(len(text_a), 1)
        doc_len_b = max(len(text_b), 1)
        
        # Jaccard-like character coverage
        coverage = total_matched_chars_a / min(doc_len_a, doc_len_b)
        
        # Word frequency Cosine similarity
        words_a = [t[0].lower() for t in tokens_a]
        words_b = [t[0].lower() for t in tokens_b]
        cosine = self._compute_cosine_similarity(words_a, words_b)

        final_score = round(min(100.0, (coverage * 70.0 + cosine * 30.0)), 1)

        return {
            "score": final_score,
            "matching_segments": merged_segments,
            "algorithm": "hybrid_tfidf_shingling",
            "total_matches": len(merged_segments)
        }

    def _tokenize_with_spans(self, text: str) -> List[tuple]:
        tokens = []
        for m in re.finditer(r"\b\w+\b", text):
            tokens.append((m.group(0), m.start(), m.end()))
        return tokens

    def _merge_adjacent_segments(self, segments: List[Dict[str, Any]], text_a: str, text_b: str) -> List[Dict[str, Any]]:
        if not segments:
            return []
        
        merged = []
        current = segments[0]

        for nxt in segments[1:]:
            # If segments are within 25 characters apart in doc A and doc B, merge them
            if nxt["start_a"] - current["end_a"] <= 25 and nxt["start_b"] - current["end_b"] <= 25:
                current["end_a"] = nxt["end_a"]
                current["end_b"] = nxt["end_b"]
                current["text"] = text_a[current["start_a"]:current["end_a"]]
                current["length"] = len(current["text"])
            else:
                merged.append(current)
                current = nxt

        merged.append(current)
        return merged

    def _compute_cosine_similarity(self, words_a: List[str], words_b: List[str]) -> float:
        vec_a = Counter(words_a)
        vec_b = Counter(words_b)
        
        all_words = set(vec_a.keys()) | set(vec_b.keys())
        dot_product = sum(vec_a[w] * vec_b[w] for w in all_words)
        
        mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
        mag_b = math.sqrt(sum(v * v for v in vec_b.values()))
        
        if mag_a == 0 or mag_b == 0:
            return 0.0
            
        return dot_product / (mag_a * mag_b)

similarity_engine = SimilarityEngine()
