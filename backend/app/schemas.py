from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class JobStatusResponse(BaseModel):
    upload_id: str
    filename: str
    status: str
    progress_pct: int
    error_msg: Optional[str]
    page_count: Optional[int]
    row_count: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ParsedRowOut(BaseModel):
    sr_number: int
    page_number: int
    device: Optional[str]
    dt: str
    raw_cn: Optional[str] = None
    variant: Optional[str] = None
    source: str = "spatial"

    class Config:
        from_attributes = True


class ResultsResponse(BaseModel):
    upload_id: str
    filename: str
    rows: list[ParsedRowOut]
    total: int
