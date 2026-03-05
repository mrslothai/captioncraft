"""Pydantic models for API requests and responses."""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from datetime import datetime


class CaptionStyle(str, Enum):
    CLASSIC = "classic"
    HIGHLIGHT = "highlight"
    COLORFUL = "colorful"
    MINIMAL = "minimal"


class CaptionPosition(str, Enum):
    TOP = "top"
    CENTER = "center"
    BOTTOM = "bottom"


class FontFamily(str, Enum):
    MONTSERRAT = "Montserrat"
    POPPINS = "Poppins"
    INTER = "Inter"
    ROBOTO = "Roboto"
    BEBAS_NEUE = "Bebas Neue"
    OSWALD = "Oswald"
    PLAYFAIR = "Playfair Display"
    PERMANENT_MARKER = "Permanent Marker"
    ANTON = "Anton"
    ARCHIVO_BLACK = "Archivo Black"


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    GENERATING_SUBTITLES = "generating_subtitles"
    BURNING_CAPTIONS = "burning_captions"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


class Word(BaseModel):
    """A single word with timing information."""
    text: str
    start: int  # milliseconds
    end: int  # milliseconds
    confidence: float = 1.0


class TranscriptResult(BaseModel):
    """Complete transcript with word-level timing."""
    words: List[Word]
    text: str
    language: Optional[str] = None


class ProcessRequest(BaseModel):
    """Request to process a video with captions."""
    video_id: str
    style: CaptionStyle = CaptionStyle.CLASSIC
    font: FontFamily = FontFamily.MONTSERRAT
    position: CaptionPosition = CaptionPosition.BOTTOM
    language: str = "hi"  # hi, en, or hinglish
    words_per_line: int = Field(default=4, ge=1, le=10)
    
    def get_transcription_language(self) -> str:
        """Get language for AssemblyAI API."""
        # For Hinglish, we transcribe in Hindi first, then convert
        return 'hi' if self.language == 'hinglish' else self.language
    
    @validator('language')
    def validate_language(cls, v):
        if v not in ['hi', 'en', 'hinglish']:
            raise ValueError('Language must be hi, en, or hinglish')
        return v


class JobStatus(BaseModel):
    """Status of a processing job."""
    job_id: str
    video_id: str
    status: ProcessingStatus
    progress: int = 0  # 0-100
    message: str = ""
    result_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    error: Optional[str] = None
    words: Optional[List[Word]] = None


class UploadResponse(BaseModel):
    """Response after video upload."""
    video_id: str
    upload_url: Optional[str] = None  # For presigned URL uploads
    message: str


class ProcessResponse(BaseModel):
    """Response after starting processing."""
    job_id: str
    message: str


class StyleInfo(BaseModel):
    """Information about a caption style."""
    name: str
    description: str
    preview_color: str
    font_default: str
