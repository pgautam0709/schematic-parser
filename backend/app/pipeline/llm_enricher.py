from __future__ import annotations
import json
import logging
from app.config import ANTHROPIC_API_KEY
from app.pipeline.spatial_parser import RawBlock

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert at parsing Ford Motor Company electrical schematic PDFs.
The PDF text layer contains device component blocks. Each block has:
- A device label matching patterns like: ECU-XXX, PDB-XXX, SN-XXX, BATT-XXX
- One or more CN: <part-number> entries (connector numbers)
- One or more DT: DT-<part-number>_<suffix> entries (device trees)
- Optional variant labels in parentheses e.g. "(GAS LOW)", "(FHEV)"

Rules for extracting rows:
1. Each CN/DT pair from the same device block produces one output row.
2. When a block lists multiple CNs then multiple DTs separately, pair them positionally (1st CN → 1st DT).
3. When CN and DT appear on the same line, they are one pair.
4. The device label for the first pair is the block label; subsequent pairs from the same block use the SAME device label (not empty).
5. Exception: when a single named block clearly contains entries for two physically separate components with very different part numbers, leave device as "" for the second component's entries.
6. Include the full DT value with its _suffix (e.g. DT-WU5T-14F141-AJX_K).
7. Output ONLY valid JSON, no prose, no markdown code blocks.

OUTPUT FORMAT:
{"rows": [{"page": <int>, "device": "<label or empty>", "cn": "<CN part number>", "dt_raw": "<full DT with _suffix>", "variant": "<variant label or empty>"}]}"""


def enrich_page(raw_text: str, page_num: int) -> list[RawBlock]:
    """
    Call Claude to extract device blocks from a page's raw text.
    Returns a list of RawBlock objects (source='llm').
    Only called when spatial parsing is insufficient.
    """
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set; skipping LLM enrichment")
        return []

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": f"Page {page_num} raw text:\n{raw_text}",
                }
            ],
        )

        content = response.content[0].text
        data = json.loads(content)
        return _parse_llm_response(data, page_num)

    except Exception as e:
        logger.error(f"LLM enrichment failed for page {page_num}: {e}")
        return []


def _parse_llm_response(data: dict, page_num: int) -> list[RawBlock]:
    """Convert LLM JSON response into RawBlock objects grouped by device."""
    rows = data.get("rows", [])
    if not rows:
        return []

    # Group consecutive rows with the same device into blocks
    blocks: list[RawBlock] = []
    current_device: str | None = None
    current_cns: list[str] = []
    current_dts: list[str] = []
    current_variants: list[str] = []

    def flush():
        if current_dts:
            blocks.append(RawBlock(
                page=page_num,
                device=current_device or None,
                cn_list=current_cns[:],
                dt_list=current_dts[:],
                variant_list=current_variants[:],
                x0=0,
                top=0,
                source="llm",
            ))

    for row in rows:
        device = row.get("device", "") or ""
        cn = row.get("cn", "") or ""
        dt_raw = row.get("dt_raw", "") or ""
        variant = row.get("variant", "") or ""

        if not dt_raw:
            continue

        if device != (current_device or "") and current_dts:
            flush()
            current_device = device or None
            current_cns = [cn]
            current_dts = [dt_raw]
            current_variants = [variant]
        else:
            if not current_dts:
                current_device = device or None
            current_cns.append(cn)
            current_dts.append(dt_raw)
            current_variants.append(variant)

    flush()
    return blocks


def merge_spatial_and_llm(
    spatial_blocks: list[RawBlock],
    llm_blocks: list[RawBlock],
) -> list[RawBlock]:
    """
    Merge spatial and LLM blocks, preferring spatial results.
    LLM blocks fill in only DTs not already covered by spatial parsing.
    """
    spatial_dts: set[str] = set()
    for b in spatial_blocks:
        spatial_dts.update(b.dt_list)

    extra_blocks: list[RawBlock] = []
    for block in llm_blocks:
        missing_dts = [dt for dt in block.dt_list if dt not in spatial_dts]
        if missing_dts:
            idx = block.dt_list.index(missing_dts[0])
            extra = RawBlock(
                page=block.page,
                device=block.device,
                cn_list=[block.cn_list[i] if i < len(block.cn_list) else "" for i, dt in enumerate(block.dt_list) if dt in missing_dts],
                dt_list=missing_dts,
                variant_list=[block.variant_list[i] if i < len(block.variant_list) else "" for i, dt in enumerate(block.dt_list) if dt in missing_dts],
                x0=block.x0,
                top=block.top,
                source="llm",
            )
            extra_blocks.append(extra)

    return spatial_blocks + extra_blocks
