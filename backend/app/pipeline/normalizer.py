from __future__ import annotations
import re
from dataclasses import dataclass
from app.pipeline.spatial_parser import RawBlock

DT_SUFFIX_RE = re.compile(r'^(DT-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+)_[A-Z0-9]{1,3}$')


@dataclass
class NormalizedRow:
    sr_number: int
    page_number: int
    device: str | None
    dt: str
    raw_cn: str | None
    raw_dt_full: str | None
    variant: str | None
    confidence: float
    source: str

    def to_db_dict(self, upload_id: str) -> dict:
        return {
            "upload_id": upload_id,
            "sr_number": self.sr_number,
            "page_number": self.page_number,
            "device": self.device,
            "dt": self.dt,
            "raw_cn": self.raw_cn,
            "raw_dt_full": self.raw_dt_full,
            "variant": self.variant,
            "confidence": self.confidence,
            "source": self.source,
        }


def strip_dt_suffix(dt_raw: str) -> str:
    """
    Strip trailing _SUFFIX from DT values.
    DT-WU5T-14F141-AJX_K  →  DT-WU5T-14F141-AJX
    DT-PZ3T-10C652-AX_E   →  DT-PZ3T-10C652-AX
    DT-W3KT-14D068-AA     →  DT-W3KT-14D068-AA  (no-op, no suffix)
    """
    m = DT_SUFFIX_RE.match(dt_raw.strip())
    return m.group(1) if m else dt_raw.strip()


def _same_dt_family(dt_list: list[str]) -> bool:
    """
    Returns True if all DT values share the same base part number.

    Comparison uses the 3rd hyphen-segment (part base number) only, ignoring
    the manufacturer prefix (2nd segment). This correctly handles dual-source
    variants where the same physical component has different manufacturer codes:

      DT-R1MT-10655-AA  (70AH battery, mfr R1MT)
      DT-DS7T-10655-AA  (80AH battery, mfr DS7T)
      → both share part base "10655" → same device (BATT-POSTIVE) on all rows.

      DT-W3KT-14D068-AA / EA / GA / PA / HA  (PDB-EXT variants)
      → all share part base "14D068" → same device on all rows.
    """
    dt_vals = [d for d in dt_list if d]
    if len(dt_vals) <= 1:
        return True
    part_bases = set()
    for dt in dt_vals:
        parts = dt.split("-")
        # DT-<mfr>-<part_base>-<variant> → index 2 is the part base number
        if len(parts) >= 3:
            part_bases.add(parts[2])  # e.g. "10655", "14D068"
        else:
            part_bases.add(dt)
    return len(part_bases) == 1


def normalize_blocks(blocks: list[RawBlock], start_sr: int = 1) -> list[NormalizedRow]:
    """Expand each RawBlock into one NormalizedRow per CN/DT pair."""
    rows: list[NormalizedRow] = []
    sr = start_sr

    for block in blocks:
        cn_list = block.cn_list
        dt_list = block.dt_list
        variant_list = block.variant_list

        # Pad shorter list with empty strings so zip doesn't truncate
        max_len = max(len(cn_list), len(dt_list))
        cn_list = cn_list + [""] * (max_len - len(cn_list))
        dt_list = dt_list + [""] * (max_len - len(dt_list))
        variant_list = variant_list + [""] * (max_len - len(variant_list))

        # If all DTs share the same part family, repeat device on every row.
        # Otherwise (different physical devices in same block), only first row gets device.
        repeat_device = _same_dt_family(dt_list)

        for i, (cn, dt_raw, variant) in enumerate(zip(cn_list, dt_list, variant_list)):
            if not dt_raw:
                continue
            dt_clean = strip_dt_suffix(dt_raw)
            row = NormalizedRow(
                sr_number=sr,
                page_number=block.page,
                device=block.device if (i == 0 or repeat_device) else None,
                dt=dt_clean,
                raw_cn=cn or None,
                raw_dt_full=dt_raw,
                variant=variant or None,
                confidence=1.0,
                source=block.source,
            )
            rows.append(row)
            sr += 1

    return rows
