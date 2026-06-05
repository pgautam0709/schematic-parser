"""
Stage 5 — Normalizer (CLI version).

Converts RawBlocks into CliRows:
  - One row per DT per component
  - DT values kept FULL (no suffix stripping)
  - "needs review" comment when a component has more than one DT on the same page
  - Confidence scores carried from source blocks

Note: This normalizer is intentionally different from the web app normalizer.
The web app strips DT suffixes and outputs one row per CN/DT pair.
This CLI normalizer preserves full DT values and is component-centric.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from pipeline.spatial_parser import RawBlock


@dataclass
class CliRow:
    page_number: int
    component_name: str
    dt_full: str            # raw, no stripping (DT-WU5T-14F141-AJX_K, /K, or plain)
    comment: str            # "needs review" if component has >1 DT, else ""
    confidence_spatial: float
    confidence_llm: float   # 0.0 if row was not produced by LLM


def normalize(blocks: list[RawBlock], page_num: int) -> list[CliRow]:
    """
    Convert a list of RawBlocks from one page into CliRows.

    Groups DTs by component name. When a component has >1 DT,
    every row for that component gets comment="needs review".
    """
    # Accumulate: component → list of (dt_full, sp_conf, llm_conf)
    component_dts: dict[str, list[tuple[str, float, float]]] = defaultdict(list)

    for block in blocks:
        if not block.device:
            continue

        sp_conf = block.confidence if block.source == "spatial" else 0.0
        llm_conf = block.confidence if block.source == "llm" else 0.0

        for dt_raw in block.dt_list:
            if dt_raw:
                component_dts[block.device].append((dt_raw, sp_conf, llm_conf))

    rows: list[CliRow] = []
    for component, dt_entries in component_dts.items():
        needs_review = len(dt_entries) > 1
        for dt_raw, sp_conf, llm_conf in dt_entries:
            rows.append(CliRow(
                page_number=page_num,
                component_name=component,
                dt_full=dt_raw,
                comment="needs review" if needs_review else "",
                confidence_spatial=round(sp_conf, 2),
                confidence_llm=round(llm_conf, 2),
            ))

    return rows
