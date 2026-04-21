from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Upload
from app.schemas import JobStatusResponse

router = APIRouter()


@router.get("/jobs", response_model=list[JobStatusResponse])
def list_jobs(db: Session = Depends(get_db)):
    uploads = db.query(Upload).order_by(Upload.created_at.desc()).all()
    return [_to_response(u) for u in uploads]


@router.get("/jobs/{upload_id}", response_model=JobStatusResponse)
def get_job(upload_id: str, db: Session = Depends(get_db)):
    upload = db.get(Upload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(upload)


def _to_response(upload: Upload) -> JobStatusResponse:
    return JobStatusResponse(
        upload_id=upload.id,
        filename=upload.original_name,
        status=upload.status,
        progress_pct=upload.progress_pct,
        error_msg=upload.error_msg,
        page_count=upload.page_count,
        row_count=upload.row_count,
        created_at=upload.created_at,
    )
