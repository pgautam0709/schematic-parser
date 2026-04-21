from __future__ import annotations
import re

CN_PATTERN = re.compile(r'CN:\s*([A-Z0-9]+-[A-Z0-9-]+)')
DT_PATTERN = re.compile(r'DT:\s*(DT-[A-Z0-9]+-[A-Z0-9-]+(?:_[A-Z0-9]+)?)')
DEVICE_PATTERN = re.compile(r'\b([A-Z]{2,8}-[A-Z0-9]{2,12})\b')


def regex_pre_pass(raw_text: str) -> dict:
    """
    Extract all CN/DT/Device matches from raw page text.
    Returns counts for cross-validation against spatial parser results.
    """
    cn_matches = CN_PATTERN.findall(raw_text)
    dt_matches = DT_PATTERN.findall(raw_text)
    device_matches = DEVICE_PATTERN.findall(raw_text)

    # Deduplicate while preserving order
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
