"""
Orchestrator — wires all five pipeline stages.

Stage 1: Text extraction     (extractor.py)
Stage 2: Spatial parsing     (spatial_parser.py) — returns blocks + page confidence
Stage 3: Regex cross-check   (regex_pass.py)     — count DT tokens in raw text
Stage 4: LLM enrichment      (llm_enricher.py)   — conditional, batched
Stage 5: Normalization        (normalizer.py)     — component-centric CliRows

LLM is triggered for a page when:
  - page_spatial_confidence < threshold  (configurable, default 0.65), OR
  - spatial_dt_count < regex_dt_count   (spatial parser missed entries)
"""
from __future__ import annotations
import logging
import os
from pathlib import Path

from pipeline.extractor import extract_page_words, words_to_text
from pipeline.spatial_parser import find_device_blocks, RawBlock
from pipeline.regex_pass import regex_pre_pass
from pipeline.llm_enricher import enrich_batch
from pipeline.normalizer import normalize, CliRow

logger = logging.getLogger(__name__)


def run_pipeline(
    pdf_path: Path,
    threshold: float | None = None,
    use_llm: bool = True,
) -> list[CliRow]:
    """
    Run the full parsing pipeline on a single PDF.

    Args:
        pdf_path:  Path to the PDF file
        threshold: Confidence threshold for triggering LLM (0.0–1.0).
                   If None, reads CONFIDENCE_THRESHOLD from env (default 0.65).
        use_llm:   If False, LLM enrichment is skipped entirely.

    Returns:
        List of CliRow objects (one per DT per component per page).
    """
    if threshold is None:
        threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.65"))

    batch_size = int(os.getenv("LLM_BATCH_SIZE", "5"))

    logger.info("Processing %s (threshold=%.2f, llm=%s)", pdf_path.name, threshold, use_llm)

    # Stage 1: Extract words per page
    pages_words = extract_page_words(pdf_path)
    logger.info("  %d pages extracted", len(pages_words))

    # Stages 2 + 3: Spatial parse + regex check for every page
    all_blocks: dict[int, list[RawBlock]] = {}
    pages_needing_llm: dict[int, str] = {}   # page_num → raw_text

    for page_idx, words in enumerate(pages_words, start=1):
        blocks, page_conf = find_device_blocks(words, page_idx)  # Stage 2
        raw_text = words_to_text(words)
        regex_counts = regex_pre_pass(raw_text)                  # Stage 3

        spatial_dt_count = sum(len(b.dt_list) for b in blocks)
        regex_dt_count = regex_counts["dt_count"]

        all_blocks[page_idx] = blocks

        needs_llm = use_llm and (
            page_conf < threshold
            or spatial_dt_count < regex_dt_count
        )

        if needs_llm:
            pages_needing_llm[page_idx] = raw_text
            logger.info(
                "  Page %d: spatial_conf=%.2f, spatial_dts=%d, regex_dts=%d → LLM triggered",
                page_idx, page_conf, spatial_dt_count, regex_dt_count,
            )
        else:
            logger.debug(
                "  Page %d: spatial_conf=%.2f, spatial_dts=%d, regex_dts=%d → spatial only",
                page_idx, page_conf, spatial_dt_count, regex_dt_count,
            )

    # Stage 4: LLM enrichment (batched)
    if pages_needing_llm:
        logger.info("  LLM enrichment for %d page(s)", len(pages_needing_llm))
        llm_results = enrich_batch(pages_needing_llm, batch_size=batch_size)

        for page_num, llm_blocks in llm_results.items():
            existing_dts = {
                dt
                for b in all_blocks.get(page_num, [])
                for dt in b.dt_list
                if dt
            }
            new_blocks = []
            for lb in llm_blocks:
                # Filter to only DTs not already found spatially
                filtered_dts = [dt for dt in lb.dt_list if dt not in existing_dts]
                filtered_cns = [
                    lb.cn_list[i] if i < len(lb.cn_list) else ""
                    for i, dt in enumerate(lb.dt_list)
                    if dt not in existing_dts
                ]
                filtered_variants = [
                    lb.variant_list[i] if i < len(lb.variant_list) else ""
                    for i, dt in enumerate(lb.dt_list)
                    if dt not in existing_dts
                ]
                if filtered_dts:
                    new_blocks.append(RawBlock(
                        page=page_num,
                        device=lb.device,
                        cn_list=filtered_cns,
                        dt_list=filtered_dts,
                        variant_list=filtered_variants,
                        source="llm",
                        confidence=lb.confidence,
                    ))
            all_blocks[page_num].extend(new_blocks)

    # Stage 5: Normalize into CliRows
    all_rows: list[CliRow] = []
    for page_num in sorted(all_blocks.keys()):
        rows = normalize(all_blocks[page_num], page_num)
        all_rows.extend(rows)

    logger.info("  Total rows: %d", len(all_rows))
    return all_rows
