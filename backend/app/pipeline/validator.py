from __future__ import annotations
import re
from dataclasses import dataclass
from app.pipeline.normalizer import NormalizedRow

DT_VALID_RE = re.compile(r'^DT-[A-Z0-9]+-[A-Z0-9]+-[A-Z0-9]+$')


@dataclass
class ValidationResult:
    ok: bool
    warnings: list[str]


def validate_rows(rows: list[NormalizedRow]) -> ValidationResult:
    warnings: list[str] = []

    if not rows:
        return ValidationResult(ok=True, warnings=[])

    # Check DT format
    for row in rows:
        if not DT_VALID_RE.match(row.dt):
            warnings.append(f"SR#{row.sr_number}: invalid DT format '{row.dt}'")

    # Check for duplicate (page, device, dt) triples
    seen: set[tuple] = set()
    for row in rows:
        key = (row.page_number, row.device, row.dt)
        if key in seen:
            warnings.append(f"SR#{row.sr_number}: duplicate (page={row.page_number}, device={row.device}, dt={row.dt})")
        seen.add(key)

    # Check SR numbers are contiguous from 1
    sr_nums = [r.sr_number for r in rows]
    expected = list(range(1, len(rows) + 1))
    if sr_nums != expected:
        warnings.append(f"SR numbers not contiguous: {sr_nums[:5]}...")

    return ValidationResult(ok=len(warnings) == 0, warnings=warnings)
