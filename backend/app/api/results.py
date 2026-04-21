from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Upload, ParsedRow
from app.schemas import ResultsResponse, ParsedRowOut

router = APIRouter()


@router.get("/results/{upload_id}", response_model=ResultsResponse)
def get_results(upload_id: str, db: Session = Depends(get_db)):
    upload = db.get(Upload, upload_id)
    if not upload:
        raise HTTPException(status_code=404, detail="Job not found")
    if upload.status != "done":
        raise HTTPException(status_code=409, detail=f"Processing not complete (status: {upload.status})")

    rows = (
        db.query(ParsedRow)
        .filter(ParsedRow.upload_id == upload_id)
        .order_by(ParsedRow.sr_number)
        .all()
    )

    return ResultsResponse(
        upload_id=upload_id,
        filename=upload.original_name,
        rows=[ParsedRowOut.model_validate(r) for r in rows],
        total=len(rows),
    )
