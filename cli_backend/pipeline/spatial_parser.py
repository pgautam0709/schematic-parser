"""
Stage 2 — Spatial Block Detection.

Detects device component blocks from PDF word coordinates.

Three block patterns found in Ford schematics:

Pattern A — Stack (ECU-BCM, SN-BMS):
  Device label
  CN: <value>
  DT: <value>         <- DT ~12pt below CN:

Pattern B — Same-line (BATT-POSTIVE):
  Device label
  CN: <cn1>  DT: <dt1>
  CN: <cn2>  DT: <dt2>

Pattern C — Grouped (PDB-EXT):
  Device label
  CN: <cn1>
  CN: <cn2>    <- all CNs stacked
  ...
  DT: <dt1>
  DT: <dt2>    <- all DTs stacked below
  ...

Returns (blocks, page_confidence) where page_confidence is 0.0–1.0.

Confidence per block:
  1.0  - perfect stack (label + CN: + DT: same x0, DT within 15pt of CN)
  0.9  - same-line pair (BATT-POSITIVE pattern)
  0.9  - grouped CN/DT no ambiguity (count matches)
  0.85 - stack with slight x-offset tolerance applied
  0.6  - label found but CN/DT at loose proximity
  0.5  - grouped but CN count != DT count (partial match)
  0.3  - no label found (orphan CN/DT tokens)

Page-level confidence = weighted mean over block confidences (weight = DT count per block).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pipeline.extractor import WordToken

# Extended DEVICE_RE covers:
#   Named:         ECU-BCM, PDB-EXT, SN-BMS, BATT-POSTIVE, GWM-XXX, IPC-XXX
#   Alphanumeric:  E515-1, E820-1, CF02, HP01, BB01, BA01
DEVICE_RE = re.compile(r'^[A-Z]{1,8}[0-9]*-[A-Z0-9]{1,12}(?:-[0-9]+)?$')

# Matches DT values with underscore suffix (_K), slash suffix (/K), or no suffix
DT_VALUE_RE = re.compile(r'^DT-[A-Z0-9]+-[A-Z0-9-]+(?:[_/][A-Z0-9]+)?$')

# Matches CN part numbers (not DT)
PART_RE = re.compile(r'^[A-Z0-9]{2,6}-[A-Z0-9]{4,12}(?:-[A-Z0-9]+)*$')

X_SAME = 8        # pt tolerance for "same x0" column
X_VALUE = 5       # tolerance when scanning for value token to the right of label
LABEL_Y_GAP = 50  # pt: device label must be within this above first CN:


@dataclass
class RawBlock:
    page: int
    device: str | None
    cn_list: list[str]
    dt_list: list[str]
    variant_list: list[str]
    x0: float = 0.0
    top: float = 0.0
    source: str = "spatial"
    confidence: float = 1.0  # block-level confidence score


def find_device_blocks(tokens: list[WordToken], page_num: int) -> tuple[list[RawBlock], float]:
    """
    Parse all device blocks from a page's word tokens.

    Returns:
        blocks: list of RawBlock
        page_confidence: float (0.0–1.0), weighted mean of block confidences
    """
    blocks = _find_labeled_blocks(tokens, page_num)
    blocks.sort(key=lambda b: b.top)

    if not blocks:
        return blocks, 0.0

    # Weighted mean: weight = number of DT entries per block
    total_weight = sum(len(b.dt_list) for b in blocks)
    if total_weight == 0:
        return blocks, 0.0

    page_conf = sum(b.confidence * len(b.dt_list) for b in blocks) / total_weight
    return blocks, round(page_conf, 3)


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------

def _find_labeled_blocks(tokens: list[WordToken], page_num: int) -> list[RawBlock]:
    cn_toks = [t for t in tokens if t.text == "CN:"]
    if not cn_toks:
        return []

    cn_rows: list[dict] = []
    for tok in cn_toks:
        val = _right_value(tok, tokens, "cn")
        if val:
            cn_rows.append({
                "top": tok.top, "x0": tok.x0,
                "cn_val": val, "dt_val": None,
                "dt_strategy": None,  # track how DT was found
                "exact_x0_match": False,
            })

    groups = _group_by_x0(cn_rows, tol=X_SAME)
    used_dt_tops: set[float] = set()
    blocks: list[RawBlock] = []

    for group in groups:
        group.sort(key=lambda r: r["top"])
        _assign_dts(group, tokens, used_dt_tops)

        dt_list = [r["dt_val"] or "" for r in group]
        if not any(dt_list):
            continue

        device, device_found = _device_above(group[0]["top"], group[0]["x0"], tokens)
        confidence = _block_confidence(group, device_found)

        blocks.append(RawBlock(
            page=page_num,
            device=device,
            cn_list=[r["cn_val"] for r in group],
            dt_list=dt_list,
            variant_list=[""] * len(group),
            x0=group[0]["x0"],
            top=group[0]["top"],
            source="spatial",
            confidence=confidence,
        ))

    return blocks


def _block_confidence(group: list[dict], device_found: bool) -> float:
    """Compute block confidence based on how cleanly patterns matched."""
    dt_strategies = [r.get("dt_strategy") for r in group if r.get("dt_val")]

    if not dt_strategies:
        return 0.3 if not device_found else 0.5

    # All strategies resolved cleanly
    if all(s == "stacked_exact" for s in dt_strategies):
        base = 1.0
    elif all(s == "sameline" for s in dt_strategies):
        base = 0.9
    elif all(s in ("grouped_full",) for s in dt_strategies):
        base = 0.9
    elif any(s == "grouped_partial" for s in dt_strategies):
        base = 0.5
    elif all(s == "stacked_loose" for s in dt_strategies):
        base = 0.85
    else:
        base = 0.6

    # Penalise if device label was not found
    if not device_found:
        base = min(base, 0.4)

    return round(base, 2)


def _assign_dts(group: list[dict], tokens: list[WordToken], used_tops: set[float]) -> None:
    """
    Assign DT values to CN rows using three strategies in order:
    1. Same-line DT  (BATT-POSTIVE pattern)
    2. Stacked DT within 15pt  (ECU-BCM / SN-BMS, single-CN only)
    3. DT group below last CN  (PDB-EXT pattern)
    """
    # Strategy 1: same-line
    for row in group:
        dt, strategy = _sameline_dt(row["top"], row["x0"], tokens, used_tops)
        if dt:
            row["dt_val"] = dt
            row["dt_strategy"] = strategy

    # Strategy 2: stacked — only for single-CN groups
    if len(group) == 1 and group[0]["dt_val"] is None:
        dt, strategy = _stacked_dt(group[0]["top"], group[0]["x0"], tokens, used_tops, max_gap=15)
        if dt:
            group[0]["dt_val"] = dt
            group[0]["dt_strategy"] = strategy

    # Strategy 3: DT group below last CN
    if any(r["dt_val"] is None for r in group):
        last_top = max(r["top"] for r in group)
        x0 = group[0]["x0"]
        dt_group = _dt_group_below(last_top, x0, tokens, used_tops)
        if dt_group:
            if len(dt_group) == len(group):
                group.sort(key=lambda r: r["top"])
                for row, dt_val in zip(group, dt_group):
                    row["dt_val"] = dt_val
                    row["dt_strategy"] = "grouped_full"
            else:
                missing = [r for r in group if r["dt_val"] is None]
                for row, dt_val in zip(missing, dt_group):
                    row["dt_val"] = dt_val
                    row["dt_strategy"] = "grouped_partial"


def _sameline_dt(
    cn_top: float, cn_x0: float, tokens: list[WordToken], used_tops: set[float]
) -> tuple[str | None, str | None]:
    dt_labels = [
        t for t in tokens
        if t.text == "DT:"
        and abs(t.top - cn_top) < 5
        and t.x0 > cn_x0
        and t.top not in used_tops
    ]
    for dt_tok in sorted(dt_labels, key=lambda t: t.x0):
        val = _right_value(dt_tok, tokens, "dt")
        if val:
            used_tops.add(dt_tok.top)
            return val, "sameline"
    return None, None


def _stacked_dt(
    cn_top: float, cn_x0: float, tokens: list[WordToken], used_tops: set[float], max_gap: float = 15
) -> tuple[str | None, str | None]:
    dt_exact = [
        t for t in tokens
        if t.text == "DT:"
        and 0 < t.top - cn_top <= max_gap
        and abs(t.x0 - cn_x0) < X_SAME
        and t.top not in used_tops
    ]
    for dt_tok in sorted(dt_exact, key=lambda t: t.top):
        val = _right_value(dt_tok, tokens, "dt")
        if val:
            used_tops.add(dt_tok.top)
            return val, "stacked_exact"

    # Loose proximity fallback: up to 30pt gap
    dt_loose = [
        t for t in tokens
        if t.text == "DT:"
        and 0 < t.top - cn_top <= 30
        and abs(t.x0 - cn_x0) < X_SAME * 2
        and t.top not in used_tops
    ]
    for dt_tok in sorted(dt_loose, key=lambda t: t.top):
        val = _right_value(dt_tok, tokens, "dt")
        if val:
            used_tops.add(dt_tok.top)
            return val, "stacked_loose"
    return None, None


def _dt_group_below(
    last_cn_top: float, x0: float, tokens: list[WordToken], used_tops: set[float]
) -> list[str]:
    dt_labels = [
        t for t in tokens
        if t.text == "DT:"
        and t.top > last_cn_top
        and abs(t.x0 - x0) < X_SAME
        and t.top not in used_tops
    ]
    dt_labels.sort(key=lambda t: t.top)

    result = []
    for dt_tok in dt_labels:
        val = _right_value(dt_tok, tokens, "dt")
        if val:
            result.append(val)
            used_tops.add(dt_tok.top)
    return result


def _right_value(label_tok: WordToken, tokens: list[WordToken], kind: str) -> str | None:
    """Find the value token immediately to the right of a CN:/DT: label."""
    candidates = [
        t for t in tokens
        if abs(t.top - label_tok.top) < 5
        and t.x0 >= label_tok.x1 - X_VALUE
        and t.x0 - label_tok.x1 < 120
        and t.text != label_tok.text
    ]
    candidates.sort(key=lambda t: t.x0)
    for tok in candidates:
        if kind == "cn" and PART_RE.match(tok.text) and not DT_VALUE_RE.match(tok.text):
            return tok.text
        if kind == "dt" and DT_VALUE_RE.match(tok.text):
            return tok.text
        # Also match TBD as a DT placeholder
        if kind == "dt" and tok.text.upper() == "TBD":
            return "TBD"
    return None


def _group_by_x0(rows: list[dict], tol: float) -> list[list[dict]]:
    if not rows:
        return []
    sorted_rows = sorted(rows, key=lambda r: r["x0"])
    groups: list[list[dict]] = [[sorted_rows[0]]]
    for row in sorted_rows[1:]:
        if abs(row["x0"] - groups[-1][0]["x0"]) <= tol:
            groups[-1].append(row)
        else:
            groups.append([row])
    return groups


def _device_above(
    row_top: float, row_x0: float, tokens: list[WordToken]
) -> tuple[str | None, bool]:
    """
    Find a device label token above row_top at similar x0.
    Returns (label_text, found_flag).
    """
    candidates = [
        t for t in tokens
        if DEVICE_RE.match(t.text)
        and 0 < row_top - t.top <= LABEL_Y_GAP
        and abs(t.x0 - row_x0) <= 25
    ]
    if candidates:
        best = max(candidates, key=lambda t: t.top)
        return best.text, True
    return None, False
