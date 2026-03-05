# CaptionCraft Backend Dockerfile
# Optimized for Railway deployment

FROM python:3.11-slim

# Install FFmpeg with full features including libass for subtitle support
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libass-dev \
    fontconfig \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy fonts to /fonts (accessible by FFmpeg)
COPY fonts/ /fonts/

# Update font cache
RUN fc-cache -fv

# Copy application code
COPY . .

# Create directories for temp and output files
RUN mkdir -p temp output

# Expose port (Railway uses PORT env variable)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Run the server (Railway sets PORT env var dynamically)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
