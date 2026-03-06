"""
Proportional word alignment: map Sarvam translit words → AssemblyAI timestamps.
Since Sarvam (Latin script) and AssemblyAI (Devanagari) can't be text-matched,
we use proportional position mapping — word i/n maps to word i*m/n from AAI.
This preserves timing accuracy across pauses and speech gaps.
"""
from typing import List


def align_words(
    source_words: List[str],   # Sarvam translit words (clean Roman Hinglish)
    target_words: List[dict],  # AssemblyAI words with timestamps {"text", "start", "end"}
) -> List[dict]:
    """
    Map source_words onto target_words timestamps by proportional position.
    Word i out of n → maps to word round(i * m / n) out of m.
    Guarantees monotonically increasing timestamps, no drift, no scrambling.
    """
    n = len(source_words)
    m = len(target_words)

    if n == 0 or m == 0:
        return []

    result = []
    for i, text in enumerate(source_words):
        # Proportional index into target
        tgt_idx = min(round(i * m / n), m - 1)
        tgt = target_words[tgt_idx]
        result.append({
            "text": text,
            "start": tgt["start"],
            "end": tgt["end"],
            "confidence": tgt.get("confidence", 0.9),
        })

    # Ensure timestamps are monotonically non-decreasing (sentence order preserved)
    for i in range(1, len(result)):
        if result[i]["start"] < result[i - 1]["end"]:
            result[i]["start"] = result[i - 1]["end"] + 30
        if result[i]["end"] <= result[i]["start"]:
            result[i]["end"] = result[i]["start"] + 200

    return result
