"""CaptionCraft Backend - FastAPI Server for Video Caption Processing."""
import os
import uuid
import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from config import get_settings
from models import (
    ProcessRequest, ProcessResponse, UploadResponse, JobStatus,
    CaptionStyle, FontFamily, CaptionPosition, ProcessingStatus
)
from processor import process_video, create_job, get_job, update_job_status
from subtitles import AVAILABLE_STYLES
try:
    import storage
    STORAGE_AVAILABLE = True
except Exception:
    STORAGE_AVAILABLE = False

# Initialize FastAPI app
app = FastAPI(
    title="CaptionCraft API",
    description="Video caption generation service with AI transcription and stylish overlays",
    version="1.0.0",
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()

# Ensure directories exist
os.makedirs(settings.temp_dir, exist_ok=True)
os.makedirs(settings.output_dir, exist_ok=True)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "CaptionCraft API",
        "status": "healthy",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    # Check FFmpeg
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    
    return {
        "status": "healthy" if ffmpeg_ok else "degraded",
        "checks": {
            "ffmpeg": ffmpeg_ok,
            "temp_dir": os.path.isdir(settings.temp_dir),
            "output_dir": os.path.isdir(settings.output_dir),
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/styles")
async def get_styles():
    """Get available caption styles."""
    return {
        "styles": AVAILABLE_STYLES,
        "fonts": [f.value for f in FontFamily],
        "positions": [p.value for p in CaptionPosition],
    }


@app.post("/upload", response_model=UploadResponse)
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a video file for processing.
    
    Max file size: 100MB
    Supported formats: MP4, MOV, AVI, MKV, WebM
    """
    # Validate file type
    allowed_types = ["video/mp4", "video/quicktime", "video/x-msvideo", "video/x-matroska", "video/webm"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )
    
    # Generate unique video ID
    video_id = str(uuid.uuid4())
    extension = Path(file.filename).suffix or ".mp4"
    filename = f"{video_id}{extension}"
    
    # Save to temp directory (in production, upload to R2)
    file_path = os.path.join(settings.temp_dir, filename)
    
    try:
        # Read file in chunks to handle large files
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                buffer.write(chunk)
                
                # Check file size limit
                if os.path.getsize(file_path) > settings.max_file_size_mb * 1024 * 1024:
                    os.remove(file_path)
                    raise HTTPException(
                        status_code=400,
                        detail=f"File too large. Max size: {settings.max_file_size_mb}MB"
                    )
        
        return UploadResponse(
            video_id=video_id,
            message=f"Video uploaded successfully. ID: {video_id}",
        )
        
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/upload/presigned", response_model=UploadResponse)
async def get_presigned_upload_url(filename: str, content_type: str = "video/mp4"):
    """Get a presigned URL for direct upload to R2 storage."""
    if not STORAGE_AVAILABLE:
        raise HTTPException(status_code=503, detail="R2 storage not configured")
    video_id = str(uuid.uuid4())
    extension = Path(filename).suffix or ".mp4"
    key = f"uploads/{video_id}{extension}"
    try:
        upload_url = storage.generate_presigned_upload_url(key, content_type)
        return UploadResponse(
            video_id=video_id,
            upload_url=upload_url,
            message="Use the upload_url to PUT your video file directly to storage",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")


@app.post("/process", response_model=ProcessResponse)
async def start_processing(request: ProcessRequest, background_tasks: BackgroundTasks):
    """
    Start processing a video with captions.
    
    The video will be processed in the background. Use /status/{job_id} to check progress.
    """
    # Find the uploaded video file
    video_path = None
    for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
        path = os.path.join(settings.temp_dir, f"{request.video_id}{ext}")
        if os.path.exists(path):
            video_path = path
            break
    
    if not video_path:
        raise HTTPException(
            status_code=404,
            detail=f"Video not found. Please upload first with /upload"
        )
    
    # Create job
    job = create_job(request.video_id)
    
    # Start processing in background
    background_tasks.add_task(
        process_video,
        job.job_id,
        video_path,
        request,
    )
    
    return ProcessResponse(
        job_id=job.job_id,
        message="Processing started. Check status with /status/{job_id}",
    )


@app.get("/status/{job_id}", response_model=JobStatus)
async def get_processing_status(job_id: str):
    """Get the status of a processing job."""
    job = get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return job


@app.get("/download/{job_id}")
async def download_result(job_id: str):
    """
    Download the processed video with captions.
    
    Only available after processing is complete.
    """
    job = get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Processing not complete. Status: {job.status.value}"
        )
    
    if not job.result_url or not os.path.exists(job.result_url):
        raise HTTPException(status_code=404, detail="Output file not found")
    
    return FileResponse(
        job.result_url,
        media_type="video/mp4",
        filename=f"captioned_{job.video_id}.mp4",
    )


@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated files."""
    job = get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Clean up files
    for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
        path = os.path.join(settings.temp_dir, f"{job.video_id}{ext}")
        if os.path.exists(path):
            os.remove(path)
    
    if job.result_url and os.path.exists(job.result_url):
        os.remove(job.result_url)
    
    # Remove from jobs dict
    from processor import jobs
    del jobs[job_id]
    
    return {"message": "Job and files deleted"}


# Startup and shutdown events

@app.get("/transcript/{job_id}")
async def get_transcript(job_id: str):
    """Get word-level transcript for a job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.words:
        raise HTTPException(status_code=404, detail="No transcript available")
    return {"words": [{"text": w.text, "start": w.start, "end": w.end} for w in job.words]}


@app.post("/reprocess/{job_id}")
async def reprocess_with_edits(job_id: str, body: dict, background_tasks: BackgroundTasks):
    """Regenerate captions with edited words."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    from models import Word
    job.words = [Word(text=w["text"], start=w["start"], end=w["end"], confidence=1.0) for w in body["words"]]
    video_path = None
    for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
        path = os.path.join(settings.temp_dir, f"{job.video_id}{ext}")
        if os.path.exists(path):
            video_path = path
            break
    if not video_path:
        raise HTTPException(status_code=404, detail="Original video not found")
    job.status = ProcessingStatus.PENDING
    job.progress = 0
    from processor import reprocess_with_words
    background_tasks.add_task(
        reprocess_with_words, job_id, video_path, job.words,
        body.get("style", "classic"), body.get("font", "Montserrat"), body.get("position", "bottom")
    )
    return {"job_id": job_id, "message": "Reprocessing with edited transcript"}


@app.get("/video/{job_id}")
async def get_original_video(job_id: str):
    """Stream the original uploaded video."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    for ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"]:
        path = os.path.join(settings.temp_dir, f"{job.video_id}{ext}")
        if os.path.exists(path):
            return FileResponse(path, media_type="video/mp4")
    raise HTTPException(status_code=404, detail="Video not found")


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    print("🎬 CaptionCraft API starting...")
    print(f"   Temp dir: {settings.temp_dir}")
    print(f"   Output dir: {settings.output_dir}")
    print(f"   Fonts dir: {settings.fonts_dir}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    print("🎬 CaptionCraft API shutting down...")


# Run with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
