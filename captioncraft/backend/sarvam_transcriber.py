"""Sarvam AI transcription integration for Hinglish."""
import asyncio
import httpx
import os
import subprocess
import glob
import shutil
import tempfile
from typing import List, Optional
from models import Word, TranscriptResult
from config import get_settings

SARVAM_BASE_URL = "https://api.sarvam.ai"
SARVAM_MODEL = "saarika:v2.5"
CHUNK_DURATION = 28  # seconds — Sarvam API rejects audio > 30s

# Flag to indicate Sarvam module is available
SARVAM_AVAILABLE = True


class SarvamTranscriptionError(Exception):
    """Error during Sarvam transcription."""
    pass


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
        capture_output=True, text=True
    )
    if result.returncode == 0 and result.stdout.strip():
        return float(result.stdout.strip())
    return 0.0


async def _transcribe_single_chunk(
    client: httpx.AsyncClient,
    chunk_path: str,
    language_code: str,
    api_key: str,
) -> dict:
    """Transcribe a single audio chunk via Sarvam API."""
    with open(chunk_path, "rb") as f:
        audio_content = f.read()

    files = {"file": ("audio.wav", audio_content, "audio/wav")}
    data = {"language_code": language_code, "model": SARVAM_MODEL, "with_timestamps": "true"}

    response = await client.post(
        f"{SARVAM_BASE_URL}/speech-to-text",
        headers={"api-subscription-key": api_key},
        data=data,
        files=files,
        timeout=300.0,
    )

    print(f"Sarvam chunk response: {response.status_code}")
    if response.status_code != 200:
        raise SarvamTranscriptionError(
            f"Transcription failed: {response.status_code} - {response.text}"
        )
    return response.json()


async def transcribe_audio_sarvam(
    audio_path: str,
    language_code: str = "hi-IN",
    output_script: str = "hinglish",
) -> TranscriptResult:
    """
    Transcribe audio using Sarvam AI.
    Automatically chunks audio > 28 seconds to comply with API limits.

    Args:
        audio_path: Path to local audio file
        language_code: Language code (default 'hi-IN' for Hindi/Hinglish)
        output_script: "hinglish" for Roman script, "devanagari" for Hindi script

    Returns:
        TranscriptResult with word-level timestamps
    """
    settings = get_settings()

    if not settings.sarvam_api_key:
        raise SarvamTranscriptionError("SARVAM_API_KEY not configured")

    # Import transliterator for Hinglish conversion
    from hinglish_transliterator import devanagari_to_hinglish, transliterate_batch

    # Determine if chunking is needed
    duration = get_audio_duration(audio_path)
    print(f"Audio duration: {duration:.1f}s")

    chunk_paths = []
    chunk_offsets = []
    tmp_dir = None

    if duration > CHUNK_DURATION:
        print(f"Audio > {CHUNK_DURATION}s — splitting into chunks...")
        tmp_dir = tempfile.mkdtemp(prefix="sarvam_chunks_")
        chunk_pattern = os.path.join(tmp_dir, "chunk_%03d.wav")
        split_result = subprocess.run(
            ["ffmpeg", "-i", audio_path, "-f", "segment",
             "-segment_time", str(CHUNK_DURATION), "-c", "copy", chunk_pattern],
            capture_output=True, text=True
        )
        if split_result.returncode != 0:
            print(f"ffmpeg split error: {split_result.stderr}")
            chunk_paths = [audio_path]
            chunk_offsets = [0.0]
        else:
            chunk_paths = sorted(glob.glob(os.path.join(tmp_dir, "chunk_*.wav")))
            chunk_offsets = [i * CHUNK_DURATION for i in range(len(chunk_paths))]
            print(f"Split into {len(chunk_paths)} chunks")
    else:
        chunk_paths = [audio_path]
        chunk_offsets = [0.0]

    all_texts = []
    all_word_data = []

    try:
        async with httpx.AsyncClient() as client:
            for chunk_path, offset_sec in zip(chunk_paths, chunk_offsets):
                chunk_result = await _transcribe_single_chunk(
                    client, chunk_path, language_code, settings.sarvam_api_key
                )
                print(f"Sarvam chunk result (offset={offset_sec}s): {str(chunk_result)[:200]}")

                chunk_text = chunk_result.get("transcript", chunk_result.get("text", ""))
                all_texts.append(chunk_text)

                if "timestamped_transcript" in chunk_result and chunk_result["timestamped_transcript"]:
                    for item in chunk_result["timestamped_transcript"]:
                        all_word_data.append({
                            "text": item.get("word", ""),
                            "start": int((item.get("start_time", 0) + offset_sec) * 1000),
                            "end": int((item.get("end_time", 0) + offset_sec) * 1000),
                            "confidence": item.get("confidence", 1.0),
                        })
                elif "words" in chunk_result and chunk_result["words"]:
                    for wd in chunk_result["words"]:
                        t_start = wd.get("start", wd.get("start_time", 0))
                        t_end = wd.get("end", wd.get("end_time", 0))
                        all_word_data.append({
                            "text": wd.get("word", wd.get("text", "")),
                            "start": int((t_start + offset_sec) * 1000),
                            "end": int((t_end + offset_sec) * 1000),
                            "confidence": wd.get("confidence", 1.0),
                        })
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    full_text = " ".join(t for t in all_texts if t)
    word_data_list = all_word_data

    print(f"Sarvam combined transcript: {full_text[:200]}")

    # --- HYBRID: Use AssemblyAI for timestamps if Sarvam gave no word timestamps ---
    settings_obj = get_settings()
    assemblyai_key = getattr(settings_obj, 'assemblyai_api_key', None)

    if not word_data_list and assemblyai_key:
        try:
            print("Using AssemblyAI for word-level timestamps + Hinglish transliteration...")
            from assemblyai_transcriber import get_word_timestamps
            aai_words = get_word_timestamps(audio_path, assemblyai_key)
            print(f"AssemblyAI returned {len(aai_words)} words")

            if aai_words:
                # Use AssemblyAI word TEXTS directly — transliterate them to Hinglish
                # This guarantees text and timestamps always stay in sync (no index drift)
                aai_texts = [w["text"] for w in aai_words]
                if output_script == "hinglish":
                    aai_texts = transliterate_batch(aai_texts)

                for i, wd in enumerate(aai_words):
                    word_data_list.append({
                        "text": aai_texts[i],
                        "start": wd["start"],
                        "end": wd["end"],
                        "confidence": wd.get("confidence", 1.0),
                    })
                print(f"Final word_data_list: {len(word_data_list)} words, first={word_data_list[0]['start']}ms last={word_data_list[-1]['end']}ms")

        except Exception as e:
            print(f"AssemblyAI alignment failed: {e} — falling back to syllable estimation")
            word_data_list = []  # reset to trigger syllable fallback

    # Convert Devanagari to Hinglish if requested
    if output_script == "hinglish":
        print(f"Converting Devanagari to Hinglish...")
        full_text = devanagari_to_hinglish(full_text)
        print(f"Converted text: {full_text[:100]}...")

    # Batch transliterate word texts if needed
    words = []
    if word_data_list and output_script == "hinglish":
        word_texts = [w["text"] for w in word_data_list]
        transliterated_texts = transliterate_batch(word_texts)
        for i, wd in enumerate(word_data_list):
            words.append(Word(
                text=transliterated_texts[i],
                start=wd["start"],
                end=wd["end"],
                confidence=wd["confidence"],
            ))
    elif word_data_list:
        for wd in word_data_list:
            words.append(Word(
                text=wd["text"],
                start=wd["start"],
                end=wd["end"],
                confidence=wd["confidence"],
            ))

    # If no word timestamps from API, distribute by syllable count (more accurate than uniform)
    if not words and full_text:
        import re
        import unicodedata

        audio_duration_ms = int(duration * 1000) if duration > 0 else 60000
        text_words = re.findall(r'\S+', full_text)

        def count_syllables(word: str) -> int:
            """Estimate syllable count for Devanagari/Hinglish words."""
            # Devanagari: count vowel matras + independent vowels
            devanagari_vowels = set('\u0905\u0906\u0907\u0908\u0909\u090a\u090b\u090c\u090d\u090e\u090f\u0910\u0911\u0912\u0913\u0914')
            devanagari_matras = set('\u093e\u093f\u0940\u0941\u0942\u0943\u0944\u0945\u0946\u0947\u0948\u0949\u094a\u094b\u094c')
            # Count inherent 'a' vowels (consonants not followed by matra/halant)
            count = 0
            for i, ch in enumerate(word):
                if ch in devanagari_vowels or ch in devanagari_matras:
                    count += 1
                elif '\u0900' <= ch <= '\u097F':  # Devanagari consonant
                    # Check if followed by halant (virama) - if not, has inherent 'a'
                    next_ch = word[i+1] if i+1 < len(word) else ''
                    if next_ch != '\u094d':  # not halant
                        count += 1
            # Fallback for Latin/Hinglish words: count vowel clusters
            if count == 0:
                count = len(re.findall(r'[aeiouAEIOU]+', word)) or 1
            return max(1, count)

        # Calculate total syllables for proportional timing
        syllable_counts = [count_syllables(w) for w in text_words]
        total_syllables = sum(syllable_counts)

        if text_words and total_syllables > 0:
            current_ms = 0
            for idx, (word_text, syllables) in enumerate(zip(text_words, syllable_counts)):
                duration_ms = int((syllables / total_syllables) * audio_duration_ms)
                duration_ms = max(150, duration_ms)  # min 150ms per word
                # Clamp to audio duration
                start_ms = min(current_ms, audio_duration_ms - 100)
                end_ms = min(current_ms + duration_ms, audio_duration_ms)
                if start_ms >= end_ms:
                    end_ms = start_ms + 100
                words.append(Word(
                    text=word_text,
                    start=start_ms,
                    end=end_ms,
                    confidence=0.8,
                ))
                current_ms += duration_ms

    if not words:
        words = [Word(text=full_text or "No transcription", start=0, end=60000, confidence=1.0)]

    return TranscriptResult(
        words=words,
        text=full_text,
        language=language_code,
    )


async def transcribe_from_url_sarvam(
    audio_url: str,
    language_code: str = "hi-IN",
    output_script: str = "hinglish",
) -> TranscriptResult:
    """
    Transcribe audio from a URL using Sarvam AI.
    Note: Sarvam requires file upload, so we download first then upload.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(audio_url, timeout=60.0)
        if response.status_code != 200:
            raise SarvamTranscriptionError(f"Failed to download audio: {response.status_code}")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(response.content)
        tmp_path = tmp.name

    try:
        result = await transcribe_audio_sarvam(tmp_path, language_code, output_script)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return result


async def batch_transcribe_sarvam(
    audio_paths: List[str],
    language_code: str = "hi-IN",
    output_script: str = "hinglish",
) -> List[TranscriptResult]:
    """Transcribe multiple audio files concurrently."""
    tasks = [
        transcribe_audio_sarvam(path, language_code, output_script)
        for path in audio_paths
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)


def correct_common_hinglish_misspellings(text: str) -> str:
    """
    Post-process Hinglish text to fix common misspellings.
    """
    corrections = {
        "mein": "main", "hoon": "hun", "tumhara": "tumara", "aapka": "apka",
        "kyun": "kyu", "kyunki": "kyuki", "kyoki": "kyuki",
        "jyada": "zyada", "fir": "phir", "accha": "acha", "achha": "acha",
        "bahut": "bahut", "jindagi": "zindagi",
    }

    import re

    def replace_word(match):
        word = match.group(0)
        word_lower = word.lower()
        if word_lower in corrections:
            corrected = corrections[word_lower]
            if word.isupper():
                return corrected.upper()
            elif word[0].isupper():
                return corrected.capitalize()
            return corrected
        return word

    pattern = r'\b(' + '|'.join(re.escape(k) for k in corrections.keys()) + r')\b'
    return re.sub(pattern, replace_word, text, flags=re.IGNORECASE)


if __name__ == "__main__":
    import asyncio

    async def test():
        test_text = "mein tumhara kaam kar raha hoon kyunki yeh zaroori hai"
        print(f"Original: {test_text}")
        print(f"Corrected: {correct_common_hinglish_misspellings(test_text)}")

    asyncio.run(test())
