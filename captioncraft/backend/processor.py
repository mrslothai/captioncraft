"""Video processing pipeline with FFmpeg."""
import os
import asyncio
import subprocess
import uuid
import json
from typing import Optional, Tuple
from datetime import datetime
from pathlib import Path

from config import get_settings
from models import (
    ProcessRequest, JobStatus, ProcessingStatus,
    Word, CaptionStyle, CaptionPosition, FontFamily
)
from subtitles import generate_ass_subtitle
from transcriber import transcribe_audio

# Import Sarvam AI transcriber for Hinglish
try:
    from sarvam_transcriber import (
        transcribe_audio_sarvam,
        correct_common_hinglish_misspellings,
    )
    SARVAM_AVAILABLE = True
except ImportError:
    SARVAM_AVAILABLE = False

# Import legacy Hinglish transliterator (fallback)
try:
    from hinglish_transliterator import devanagari_to_hinglish
    HINGLISH_AVAILABLE = True
except ImportError:
    HINGLISH_AVAILABLE = False


class ProcessingError(Exception):
    """Error during video processing."""
    pass


# In-memory job storage (use Redis in production)
jobs: dict[str, JobStatus] = {}


def get_video_info(video_path: str) -> dict:
    """Get video dimensions and duration using FFprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise ProcessingError(f"FFprobe failed: {result.stderr}")
    
    info = json.loads(result.stdout)
    
    # Find video stream
    video_stream = None
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break
    
    if not video_stream:
        raise ProcessingError("No video stream found")
    
    return {
        "width": int(video_stream.get("width", 1080)),
        "height": int(video_stream.get("height", 1920)),
        "duration": float(info.get("format", {}).get("duration", 0)),
        "codec": video_stream.get("codec_name", "unknown"),
    }


async def extract_audio(video_path: str, output_path: str) -> str:
    """Extract audio from video using FFmpeg."""
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",                    # No video
        "-acodec", "pcm_s16le",   # PCM audio for best transcription
        "-ar", "16000",           # 16kHz sample rate (optimal for speech)
        "-ac", "1",               # Mono
        "-y",                     # Overwrite output
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise ProcessingError(f"Audio extraction failed: {stderr.decode()}")
    
    return output_path


async def burn_captions(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    fonts_dir: str = "/fonts"
) -> str:
    """Burn ASS subtitles onto video using FFmpeg."""
    
    # Use ass filter (requires libass, which you now have!)
    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-vf", f"ass={subtitle_path}",
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", "fast",
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        raise ProcessingError(f"Caption burning failed: {stderr.decode()}")
    
    return output_path


def update_job_status(
    job_id: str,
    status: ProcessingStatus,
    progress: int = 0,
    message: str = "",
    result_url: Optional[str] = None,
    error: Optional[str] = None
):
    """Update job status in storage."""
    if job_id not in jobs:
        return
    
    job = jobs[job_id]
    job.status = status
    job.progress = progress
    job.message = message
    job.updated_at = datetime.utcnow()
    
    if result_url:
        job.result_url = result_url
    if error:
        job.error = error


async def process_video(
    job_id: str,
    video_path: str,
    request: ProcessRequest,
) -> str:
    """
    Complete video processing pipeline:
    1. Extract audio from video
    2. Transcribe audio with AssemblyAI
    3. Generate ASS subtitle file
    4. Burn captions onto video
    
    Returns the path to the processed video.
    """
    settings = get_settings()
    
    # Create unique filenames
    base_name = Path(video_path).stem
    audio_path = os.path.join(settings.temp_dir, f"{base_name}_audio.wav")
    subtitle_path = os.path.join(settings.temp_dir, f"{base_name}.ass")
    output_path = os.path.join(settings.output_dir, f"{base_name}_captioned.mp4")
    
    try:
        # Step 1: Get video info
        video_info = get_video_info(video_path)
        
        # Step 2: Extract audio
        update_job_status(job_id, ProcessingStatus.EXTRACTING_AUDIO, 10, "Extracting audio...")
        await extract_audio(video_path, audio_path)
        
        # Step 3: Transcribe
        update_job_status(job_id, ProcessingStatus.TRANSCRIBING, 30, "Transcribing audio...")
        
        # Use Sarvam AI for Hinglish, AssemblyAI for other languages
        if request.language == 'hinglish':
            if not SARVAM_AVAILABLE:
                raise ProcessingError("Sarvam AI not available. Please check SARVAM_API_KEY configuration.")
            
            update_job_status(job_id, ProcessingStatus.TRANSCRIBING, 32, "Using Sarvam AI for Hinglish...")
            try:
                transcript = await transcribe_audio_sarvam(audio_path, language_code="hi-IN", output_script="hinglish")
            except Exception as e:
                raise ProcessingError(f"Sarvam transcription failed: {str(e)}")
            
            # Apply misspelling correction
            update_job_status(job_id, ProcessingStatus.TRANSCRIBING, 38, "Applying Hinglish corrections...")
            corrected_words = []
            for word in transcript.words:
                corrected_text = correct_common_hinglish_misspellings(word.text)
                corrected_words.append(Word(
                    text=corrected_text,
                    start=word.start,
                    end=word.end,
                    confidence=word.confidence
                ))
            transcript.words = corrected_words
            transcript.text = correct_common_hinglish_misspellings(transcript.text)
            
        else:
            # Use AssemblyAI for other languages
            transcript = await transcribe_audio(audio_path, request.get_transcription_language())
        
        if not transcript.words:
            raise ProcessingError("No speech detected in video")
        
        # Store words in job for transcript editor
        jobs[job_id].words = transcript.words
        
        # Step 4: Generate subtitles
        update_job_status(job_id, ProcessingStatus.GENERATING_SUBTITLES, 60, "Generating captions...")
        ass_content = generate_ass_subtitle(
            words=transcript.words,
            style=request.style,
            font=request.font,
            position=request.position,
            words_per_line=request.words_per_line,
            video_width=video_info["width"],
            video_height=video_info["height"],
        )
        
        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write(ass_content)
        
        # Step 5: Burn captions
        update_job_status(job_id, ProcessingStatus.BURNING_CAPTIONS, 80, "Burning captions onto video...")
        
        # Use local fonts dir or /fonts in Docker
        fonts_dir = settings.fonts_dir
        if os.path.isdir("/fonts"):
            fonts_dir = "/fonts"
        
        await burn_captions(video_path, subtitle_path, output_path, fonts_dir)
        
        # Cleanup temp files
        for temp_file in [audio_path, subtitle_path]:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        
        update_job_status(job_id, ProcessingStatus.COMPLETED, 100, "Processing complete!", output_path)
        
        return output_path
        
    except Exception as e:
        update_job_status(job_id, ProcessingStatus.FAILED, 0, str(e), error=str(e))
        raise


def create_job(video_id: str) -> JobStatus:
    """Create a new processing job."""
    job_id = str(uuid.uuid4())
    now = datetime.utcnow()
    
    job = JobStatus(
        job_id=job_id,
        video_id=video_id,
        status=ProcessingStatus.PENDING,
        progress=0,
        message="Job created",
        created_at=now,
        updated_at=now,
    )
    
    jobs[job_id] = job
    return job


def get_job(job_id: str) -> Optional[JobStatus]:
    """Get job status by ID."""
    return jobs.get(job_id)


async def reprocess_with_words(job_id: str, video_path: str, words, style: str, font: str, position: str):
    """Regenerate captions with edited words (skip transcription)."""
    settings = get_settings()
    base_name = Path(video_path).stem
    subtitle_path = os.path.join(settings.temp_dir, f"{base_name}_edited.ass")
    output_path = os.path.join(settings.output_dir, f"{base_name}_captioned.mp4")
    try:
        update_job_status(job_id, ProcessingStatus.GENERATING_SUBTITLES, 60, "Regenerating captions...")
        video_info = get_video_info(video_path)
        # Convert string values to enums (generate_ass_subtitle expects enum objects)
        style_enum = CaptionStyle(style) if isinstance(style, str) else style
        font_enum = FontFamily(font) if isinstance(font, str) else font
        position_enum = CaptionPosition(position) if isinstance(position, str) else position
        ass_content = generate_ass_subtitle(
            words=words,
            style=style_enum,
            font=font_enum,
            position=position_enum,
            words_per_line=4,
            video_width=video_info["width"],
            video_height=video_info["height"],
        )
        with open(subtitle_path, "w", encoding="utf-8") as f:
            f.write(ass_content)
        update_job_status(job_id, ProcessingStatus.BURNING_CAPTIONS, 80, "Burning captions...")
        fonts_dir = settings.fonts_dir
        if os.path.isdir("/fonts"):
            fonts_dir = "/fonts"
        await burn_captions(video_path, subtitle_path, output_path, fonts_dir)
        if os.path.exists(subtitle_path):
            os.remove(subtitle_path)
        update_job_status(job_id, ProcessingStatus.COMPLETED, 100, "Done!", output_path)
    except Exception as e:
        update_job_status(job_id, ProcessingStatus.FAILED, 0, str(e), error=str(e))
