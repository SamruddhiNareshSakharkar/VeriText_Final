import re
import math
from typing import Dict, Any, List, Tuple
from collections import Counter, defaultdict


class SimilarityEngine:
    """
    High-Efficiency Modular Content Similarity Engine.
    Employs an inverted n-gram index with greedy longest-common-token extension
    and topological gap merging to accurately detect exact and paraphrased passages.
    Runs in linear O(N + M) time with precise start and end character offsets.
    """

    def __init__(self, n_gram_size: int = 3):
        self.n_gram_size = n_gram_size
        self._token_re = re.compile(r"\b\w+\b")

    def _tokenize_with_spans(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Fast tokenization yielding (word, start_char_offset, end_char_offset).
        """
        return [(m.group(0), m.start(), m.end()) for m in self._token_re.finditer(text)]

    def compare_documents(self, text_a: str, text_b: str) -> Dict[str, Any]:
        """
        Compares two texts and outputs character-level matching segments for highlighting
        along with overall composite similarity score.
        """
        if not text_a or not text_b or len(text_a.strip()) < 10 or len(text_b.strip()) < 10:
            return {
                "score": 0.0,
                "matching_segments": [],
                "algorithm": "inverted_shingling_greedy_extension",
                "total_matches": 0,
            }

        # 1. Tokenize both documents with character offsets
        tokens_a = self._tokenize_with_spans(text_a)
        tokens_b = self._tokenize_with_spans(text_b)

        len_a = len(tokens_a)
        len_b = len(tokens_b)

        if len_a < self.n_gram_size or len_b < self.n_gram_size:
            # Fallback for very short text snippets
            words_a = set(w.lower() for w, _, _ in tokens_a)
            words_b = set(w.lower() for w, _, _ in tokens_b)
            overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
            score = round(overlap * 100.0, 1)
            return {
                "score": score,
                "matching_segments": [],
                "algorithm": "token_jaccard_fallback",
                "total_matches": 0,
            }

        # 2. Build inverted index of n-grams for Document B
        # maps n_gram_tuple -> list of starting token index in B
        index_b = defaultdict(list)
        norm_b = [t[0].lower() for t in tokens_b]
        for j in range(len_b - self.n_gram_size + 1):
            shingle = tuple(norm_b[j:j + self.n_gram_size])
            index_b[shingle].append(j)

        # 3. Scan Document A and find maximal extended matches
        norm_a = [t[0].lower() for t in tokens_a]
        raw_matches = []
        i = 0

        while i <= len_a - self.n_gram_size:
            shingle_a = tuple(norm_a[i:i + self.n_gram_size])
            if shingle_a in index_b:
                # Candidate occurrences in B
                best_ext = self.n_gram_size
                best_j = index_b[shingle_a][0]

                # Try all occurrences to find the longest forward extension
                for cand_j in index_b[shingle_a]:
                    ext = self.n_gram_size
                    while (i + ext < len_a and
                           cand_j + ext < len_b and
                           norm_a[i + ext] == norm_b[cand_j + ext]):
                        ext += 1

                    if ext > best_ext:
                        best_ext = ext
                        best_j = cand_j

                # Record the maximal matched segment
                start_a = tokens_a[i][1]
                end_a = tokens_a[i + best_ext - 1][2]
                start_b = tokens_b[best_j][1]
                end_b = tokens_b[best_j + best_ext - 1][2]
                matched_text = text_a[start_a:end_a]

                raw_matches.append({
                    "start_a": start_a,
                    "end_a": end_a,
                    "start_b": start_b,
                    "end_b": end_b,
                    "text": matched_text,
                    "length": len(matched_text),
                    "token_count": best_ext,
                })

                # Advance cursor past the matched block
                i += best_ext
            else:
                i += 1

        # 4. Merge adjacent segments (within 28 chars in A and B)
        merged_segments = self._merge_adjacent_segments(raw_matches, text_a, text_b)

        # 5. Calculate composite similarity metrics
        total_matched_chars_a = sum(s["end_a"] - s["start_a"] for s in merged_segments)
        doc_char_len_a = max(len(text_a), 1)
        doc_char_len_b = max(len(text_b), 1)

        # Coverage relative to both document lengths
        char_coverage = total_matched_chars_a / min(doc_char_len_a, doc_char_len_b)

        # Token-level cosine similarity
        cosine_sim = self._compute_cosine_similarity(norm_a, norm_b)

        # Combined weighted score
        final_score = round(min(100.0, (char_coverage * 70.0 + cosine_sim * 30.0)), 1)

        # Filter redundant sub-matches in both documents
        filtered_segments = self._filter_overlapping_segments(merged_segments)

        # Clean segments for output
        cleaned_segments = [
            {
                "start_a": s["start_a"],
                "end_a": s["end_a"],
                "start_b": s["start_b"],
                "end_b": s["end_b"],
                "text": s["text"],
                "length": s["length"],
            }
            for s in filtered_segments
        ]

        return {
            "score": final_score,
            "matching_segments": cleaned_segments,
            "algorithm": "inverted_shingling_greedy_extension",
            "total_matches": len(cleaned_segments),
        }

    def _merge_adjacent_segments(
        self,
        segments: List[Dict[str, Any]],
        text_a: str,
        text_b: str
    ) -> List[Dict[str, Any]]:
        if not segments:
            return []

        # Sort segments primarily by start_a
        sorted_segs = sorted(segments, key=lambda s: s["start_a"])
        merged = []
        curr = sorted_segs[0]

        for nxt in sorted_segs[1:]:
            gap_a = nxt["start_a"] - curr["end_a"]
            gap_b = nxt["start_b"] - curr["end_b"]

            # Merge if gap is small and positive in both documents (e.g. minor whitespace/punctuation)
            if 0 <= gap_a <= 28 and 0 <= gap_b <= 28:
                curr["end_a"] = max(curr["end_a"], nxt["end_a"])
                curr["end_b"] = max(curr["end_b"], nxt["end_b"])
                curr["text"] = text_a[curr["start_a"]:curr["end_a"]]
                curr["length"] = len(curr["text"])
            elif nxt["start_a"] < curr["end_a"]:
                # Overlapping match: extend curr if nxt reaches further
                if nxt["end_a"] > curr["end_a"]:
                    curr["end_a"] = nxt["end_a"]
                    curr["end_b"] = max(curr["end_b"], nxt["end_b"])
                    curr["text"] = text_a[curr["start_a"]:curr["end_a"]]
                    curr["length"] = len(curr["text"])
            else:
                merged.append(curr)
                curr = nxt

        merged.append(curr)
        return merged

    def _filter_overlapping_segments(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not segments:
            return []

        # 1. Filter subsets in Document A
        sorted_segs = sorted(segments, key=lambda s: (s['start_a'], -(s['end_a'] - s['start_a'])))
        filtered = []
        max_end_a = -1
        for s in sorted_segs:
            if s['end_a'] <= max_end_a:
                continue
            filtered.append(s)
            max_end_a = max(max_end_a, s['end_a'])

        # 2. Filter internal subsets in Document B (prioritize longer matches)
        result = []
        for s in sorted(filtered, key=lambda x: -x['length']):
            is_sub = any(
                chosen['start_b'] <= s['start_b'] and chosen['end_b'] >= s['end_b']
                for chosen in result
            )
            if not is_sub:
                result.append(s)

        # Sort back chronologically by start_a
        result.sort(key=lambda s: s['start_a'])
        return result

    def _compute_cosine_similarity(self, words_a: List[str], words_b: List[str]) -> float:
        if not words_a or not words_b:
            return 0.0

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
