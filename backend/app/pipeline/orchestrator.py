from __future__ import annotations
import asyncio
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from app.models import Upload, ParsedRow
from app.pipeline import extractor, spatial_parser, regex_pass, normalizer, validator, llm_enricher
from app.utils.file_store import get_pdf_path
from app.config import MAX_CONCURRENT_JOBS

logger = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None
# Thread pool sized to MAX_CONCURRENT_JOBS — each pipeline run gets its own thread
# so blocking pdfplumber / OpenAI calls never freeze the event loop
_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_JOBS)


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
    return _semaphore


async def run_pipeline(upload_id: str) -> None:
    """
    Enqueue a pipeline run from FastAPI BackgroundTasks.
    Runs the blocking pipeline in a thread-pool worker so the event loop
    stays free to serve status-poll requests while PDFs are being parsed.
    """
    async with _get_semaphore():
        await asyncio.get_event_loop().run_in_executor(
            _executor, _run_pipeline_sync, upload_id
        )


def _run_pipeline_sync(upload_id: str) -> None:
    """
    Synchronous pipeline — executes in a thread-pool worker.
    Creates its own DB session (SQLAlchemy sessions are not thread-safe).
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        _execute_pipeline(upload_id, db)
    finally:
        db.close()


def _execute_pipeline(upload_id: str, db) -> None:
    upload = db.get(Upload, upload_id)
    if not upload:
        logger.error(f"Upload {upload_id} not found")
        return

    try:
        upload.status = "processing"
        upload.progress_pct = 0
        db.commit()

        pdf_path = get_pdf_path(upload_id, upload.original_name)
        pages_words = extractor.extract_page_words(pdf_path)
        upload.page_count = len(pages_words)
        db.commit()

        all_blocks = []

        for page_idx, words in enumerate(pages_words, start=1):
            raw_text = extractor.words_to_text(words)
            blocks = spatial_parser.find_device_blocks(words, page_idx)
            regex_stats = regex_pass.regex_pre_pass(raw_text)

            spatial_dt_count = sum(len(b.dt_list) for b in blocks)
            regex_dt_count = regex_stats["dt_count"]

            if spatial_dt_count < regex_dt_count:
                logger.info(
                    f"Page {page_idx}: spatial found {spatial_dt_count} DTs, "
                    f"regex found {regex_dt_count} — invoking LLM"
                )
                llm_blocks = llm_enricher.enrich_page(raw_text, page_idx)
                blocks = llm_enricher.merge_spatial_and_llm(blocks, llm_blocks)

            all_blocks.extend(blocks)

            pct = int((page_idx / len(pages_words)) * 90)
            upload.progress_pct = pct
            db.commit()

        all_rows = normalizer.normalize_blocks(all_blocks, start_sr=1)

        for i, row in enumerate(all_rows, start=1):
            row.sr_number = i

        val_result = validator.validate_rows(all_rows)
        if val_result.warnings:
            logger.warning(f"Upload {upload_id} validation warnings: {val_result.warnings}")

        db_rows = [ParsedRow(**row.to_db_dict(upload_id)) for row in all_rows]
        db.bulk_save_objects(db_rows)

        upload.status = "done"
        upload.row_count = len(all_rows)
        upload.progress_pct = 100
        db.commit()

        logger.info(f"Upload {upload_id}: completed with {len(all_rows)} rows")

    except Exception as e:
        logger.exception(f"Pipeline failed for upload {upload_id}: {e}")
        upload.status = "error"
        upload.error_msg = str(e)
        db.commit()


async def run_pipeline_from_path(pdf_path: str | Path) -> list[normalizer.NormalizedRow]:
    """Convenience wrapper for tests — runs pipeline without DB."""
    pages_words = extractor.extract_page_words(pdf_path)
    all_blocks = []

    for page_idx, words in enumerate(pages_words, start=1):
        raw_text = extractor.words_to_text(words)
        blocks = spatial_parser.find_device_blocks(words, page_idx)
        regex_stats = regex_pass.regex_pre_pass(raw_text)

        spatial_dt_count = sum(len(b.dt_list) for b in blocks)
        if spatial_dt_count < regex_stats["dt_count"]:
            llm_blocks = llm_enricher.enrich_page(raw_text, page_idx)
            blocks = llm_enricher.merge_spatial_and_llm(blocks, llm_blocks)

        all_blocks.extend(blocks)

    rows = normalizer.normalize_blocks(all_blocks, start_sr=1)
    for i, row in enumerate(rows, start=1):
        row.sr_number = i
    return rows
