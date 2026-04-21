import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Upload
from app.schemas import UploadResponse
from app.utils.file_store import save_pdf
from app.pipeline.orchestrator import run_pipeline
from app.config import MAX_PDF_SIZE_MB

router = APIRouter()


@router.post("/upload", response_model=list[UploadResponse])
async def upload_pdfs(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    responses = []
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"File '{file.filename}' is not a PDF")

        content = await file.read()
        if len(content) > MAX_PDF_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=413, detail=f"File '{file.filename}' exceeds {MAX_PDF_SIZE_MB}MB limit")
        await file.seek(0)

        upload_id = str(uuid.uuid4())
        upload = Upload(
            id=upload_id,
            filename=file.filename,
            original_name=file.filename,
            status="pending",
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)

        saved_path = save_pdf(upload_id, file)

        background_tasks.add_task(_run_async_pipeline, upload_id, db)

        responses.append(UploadResponse(
            upload_id=upload.id,
            filename=upload.filename,
            status=upload.status,
            created_at=upload.created_at,
        ))

    return responses


async def _run_async_pipeline(upload_id: str, db: Session):
    import asyncio
    await run_pipeline(upload_id, db)
