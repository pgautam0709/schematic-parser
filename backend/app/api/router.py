from fastapi import APIRouter
from app.api import upload, jobs, results, export, delete

router = APIRouter(prefix="/api")
router.include_router(upload.router)
router.include_router(jobs.router)
router.include_router(results.router)
router.include_router(export.router)
router.include_router(delete.router)
