"""AssemblyAI transcription for word-level timestamps."""
import assemblyai as aai
from typing import List


def get_word_timestamps(audio_path: str, api_key: str) -> List[dict]:
    """
    Transcribe audio with AssemblyAI to get exact word-level timestamps.
    Returns list of {"text": str, "start": int (ms), "end": int (ms)}
    """
    aai.settings.api_key = api_key
    config = aai.TranscriptionConfig(
        language_code="hi",  # Hindi (works for Hinglish)
    )
    transcriber = aai.Transcriber(config=config)
    transcript = transcriber.transcribe(audio_path)

    if transcript.status == aai.TranscriptStatus.error:
        raise Exception(f"AssemblyAI error: {transcript.error}")

    words = []
    if transcript.words:
        for w in transcript.words:
            words.append({
                "text": w.text,
                "start": w.start,  # already in ms
                "end": w.end,      # already in ms
                "confidence": w.confidence,
            })
    return words
