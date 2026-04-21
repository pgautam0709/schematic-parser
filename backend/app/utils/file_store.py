import shutil
from pathlib import Path
from fastapi import UploadFile
from app.config import UPLOAD_DIR


def get_upload_dir(upload_id: str) -> Path:
    path = UPLOAD_DIR / upload_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_pdf(upload_id: str, file: UploadFile) -> Path:
    dest = get_upload_dir(upload_id) / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest


def get_pdf_path(upload_id: str, original_name: str) -> Path:
    return get_upload_dir(upload_id) / original_name


def delete_upload(upload_id: str) -> None:
    path = UPLOAD_DIR / upload_id
    if path.exists():
        shutil.rmtree(path)
