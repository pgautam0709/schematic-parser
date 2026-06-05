"""
Stage 3 — Regex Pre-Pass.

Counts CN:/DT: occurrences in raw page text using regex.
Used to detect when the spatial parser may have missed entries
(spatial_dt_count < regex_dt_count → trigger LLM enrichment).

Handles all three DT suffix formats:
  Underscore:  DT-WU5T-14F141-AJX_K
  Slash:       DT-WU5T-14F141-AJX/K
  None:        DT-W3KT-14D068-AA
"""
from __future__ import annotations
import re

CN_PATTERN = re.compile(r'CN:\s*([A-Z0-9]+-[A-Z0-9-]+)')
# Matches all DT suffix formats: _X, /X, or none
DT_PATTERN = re.compile(r'DT:\s*(DT-[A-Z0-9]+-[A-Z0-9-]+(?:[_/][A-Z0-9]+)?)')
DEVICE_PATTERN = re.compile(r'\b([A-Z]{1,8}[0-9]*-[A-Z0-9]{1,12}(?:-[0-9]+)?)\b')


def regex_pre_pass(raw_text: str) -> dict:
    """
    Extract all CN/DT/Device matches from raw page text.
    Returns counts and deduplicated lists for cross-validation.
    """
    cn_matches = CN_PATTERN.findall(raw_text)
    dt_matches = DT_PATTERN.findall(raw_text)
    device_matches = DEVICE_PATTERN.findall(raw_text)

    def dedup(lst: list[str]) -> list[str]:
        seen: set[str] = set()
        out = []
        for v in lst:
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out

    return {
        "cn_matches": dedup(cn_matches),
        "dt_matches": dedup(dt_matches),
        "device_matches": dedup(device_matches),
        "cn_count": len(set(cn_matches)),
        "dt_count": len(set(dt_matches)),
    }
