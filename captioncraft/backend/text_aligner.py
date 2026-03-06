"""
Align two word lists using dynamic programming (edit distance).
Used to map Sarvam translit words → AssemblyAI timestamps.
Handles word count mismatches caused by number expansion, contractions, etc.
"""
import re
from typing import List, Tuple


def _normalize(word: str) -> str:
    """Lowercase + strip punctuation for comparison."""
    return re.sub(r'[^\w]', '', word.lower())


def align_words(
    source_words: List[str],   # Sarvam translit words (better text)
    target_words: List[dict],  # AssemblyAI words with timestamps {"text", "start", "end"}
) -> List[dict]:
    """
    Align source_words text onto target_words timestamps using DP alignment.
    Returns list of {"text": source_word, "start": ms, "end": ms}.
    Guarantees every source word gets a timestamp — no drift.
    """
    n = len(source_words)
    m = len(target_words)

    if n == 0 or m == 0:
        return []

    # Build DP alignment matrix (Needleman-Wunsch style)
    # dp[i][j] = min cost to align source[:i] with target[:j]
    INF = float('inf')
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0
    for j in range(1, m + 1):
        dp[0][j] = j  # skip target words
    for i in range(1, n + 1):
        dp[i][0] = i  # insert source words

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            # Match/substitute: map source[i-1] to target[j-1]
            s_norm = _normalize(source_words[i - 1])
            t_norm = _normalize(target_words[j - 1]["text"])
            match_cost = 0 if s_norm == t_norm else 1
            dp[i][j] = min(
                dp[i - 1][j - 1] + match_cost,  # match/substitute
                dp[i - 1][j] + 1,                # skip source word (assign to previous target)
                dp[i][j - 1] + 1,                # skip target word
            )

    # Traceback to get alignment
    alignment = []  # list of (source_idx, target_idx_or_None)
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            s_norm = _normalize(source_words[i - 1])
            t_norm = _normalize(target_words[j - 1]["text"])
            match_cost = 0 if s_norm == t_norm else 1
            if dp[i][j] == dp[i - 1][j - 1] + match_cost:
                alignment.append((i - 1, j - 1))
                i -= 1; j -= 1
                continue
        if i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            alignment.append((i - 1, None))  # source word with no target
            i -= 1
        elif j > 0:
            j -= 1  # skip target word
        else:
            i -= 1

    alignment.reverse()

    # Build result: for each source word, assign timestamp from aligned target
    # If source word has no target match, interpolate from neighbors
    result = []
    last_end = 0

    for src_idx, tgt_idx in alignment:
        text = source_words[src_idx]
        if tgt_idx is not None:
            start = target_words[tgt_idx]["start"]
            end = target_words[tgt_idx]["end"]
        else:
            # No timestamp: use last_end + small gap
            start = last_end + 50
            end = start + 200
        result.append({"text": text, "start": start, "end": end, "confidence": 0.9})
        last_end = end

    # Sort by start time and fix any remaining inversions
    result.sort(key=lambda w: w["start"])

    # Ensure end >= start for each word
    for w in result:
        if w["end"] < w["start"]:
            w["end"] = w["start"] + 200

    return result
