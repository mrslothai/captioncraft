"""Cloudflare R2 storage integration using S3-compatible API."""
import os
from typing import Optional
from config import get_settings

try:
    import boto3
    from botocore.config import Config
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


def get_r2_client():
    """Create an S3 client configured for Cloudflare R2."""
    if not BOTO3_AVAILABLE:
        raise RuntimeError("boto3 not installed. R2 storage unavailable.")
    settings = get_settings()
    
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        config=Config(
            signature_version="s3v4",
            region_name="auto",
        ),
    )


def generate_presigned_upload_url(
    key: str,
    content_type: str = "video/mp4",
    expires_in: int = 3600,
) -> str:
    """Generate a presigned URL for uploading to R2."""
    settings = get_settings()
    client = get_r2_client()
    
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )


def generate_presigned_download_url(
    key: str,
    expires_in: int = 3600,
) -> str:
    """Generate a presigned URL for downloading from R2."""
    settings = get_settings()
    client = get_r2_client()
    
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": key,
        },
        ExpiresIn=expires_in,
    )


def upload_file(file_path: str, key: str, content_type: str = "video/mp4") -> str:
    """Upload a local file to R2."""
    settings = get_settings()
    client = get_r2_client()
    
    with open(file_path, "rb") as f:
        client.put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=f,
            ContentType=content_type,
        )
    
    # Return public URL if configured, otherwise presigned URL
    if settings.r2_public_url:
        return f"{settings.r2_public_url}/{key}"
    
    return generate_presigned_download_url(key)


def download_file(key: str, local_path: str) -> str:
    """Download a file from R2 to local path."""
    settings = get_settings()
    client = get_r2_client()
    
    client.download_file(settings.r2_bucket_name, key, local_path)
    
    return local_path


def delete_file(key: str) -> bool:
    """Delete a file from R2."""
    settings = get_settings()
    client = get_r2_client()
    
    try:
        client.delete_object(Bucket=settings.r2_bucket_name, Key=key)
        return True
    except Exception:
        return False


def file_exists(key: str) -> bool:
    """Check if a file exists in R2."""
    settings = get_settings()
    client = get_r2_client()
    
    try:
        client.head_object(Bucket=settings.r2_bucket_name, Key=key)
        return True
    except Exception:
        return False
