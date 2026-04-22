from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Upload
from app.utils.file_store import delete_upload

router = APIRouter()


@router.delete("/jobs")
def delete_all_jobs(db: Session = Depends(get_db)):
    uploads = db.query(Upload).all()
    ids = [u.id for u in uploads]
    for upload in uploads:
        db.delete(upload)
    db.commit()
    for upload_id in ids:
        delete_upload(upload_id)
    return {"deleted": len(ids)}


@router.delete("/jobs/{upload_id}")
def delete_job(upload_id: str, db: Session = Depends(get_db)):
    upload = db.get(Upload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(upload)
    db.commit()
    delete_upload(upload_id)
    return {"deleted": upload_id}
