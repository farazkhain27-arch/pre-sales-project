"""
Storage abstraction. Uses local disk in dev (USE_S3=False) and S3 in
staging/production. Keeping this behind one interface means routers never
care which backend is active.
"""
import os
import uuid
import boto3
from ..config import get_settings

settings = get_settings()
LOCAL_STORAGE_DIR = "/app/storage"


def _s3_client():
    return boto3.client("s3", region_name=settings.AWS_REGION)


def save_upload(file_bytes: bytes, filename: str, project_id: str) -> str:
    """Persist an uploaded file and return its storage path/URI."""
    key = f"{project_id}/{uuid.uuid4()}_{filename}"
    if settings.USE_S3:
        _s3_client().put_object(Bucket=settings.S3_BUCKET, Key=key, Body=file_bytes)
        return f"s3://{settings.S3_BUCKET}/{key}"
    else:
        os.makedirs(f"{LOCAL_STORAGE_DIR}/{project_id}", exist_ok=True)
        path = f"{LOCAL_STORAGE_DIR}/{key}"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(file_bytes)
        return path


def read_file(storage_path: str) -> bytes:
    if storage_path.startswith("s3://"):
        _, _, rest = storage_path.partition("s3://")
        bucket, _, key = rest.partition("/")
        obj = _s3_client().get_object(Bucket=bucket, Key=key)
        return obj["Body"].read()
    with open(storage_path, "rb") as f:
        return f.read()
