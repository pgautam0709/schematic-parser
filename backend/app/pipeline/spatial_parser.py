"""
Spatial parser for Ford BCM schematics.

Three block patterns found in P736_BCM.pdf:

Pattern A — Stack (ECU-BCM, SN-BMS):
  Device label
  CN: <value>
  DT: <value>         ← DT: ~12pt below CN:

Pattern B — Same-line (BATT-POSTIVE):
  Device label
  CN: <cn1>  DT: <dt1>
  CN: <cn2>  DT: <dt2>

Pattern C — Grouped (PDB-EXT):
  Device label
  CN: <cn1>
  CN: <cn2>           ← 5x CN: stacked
  ...
  DT: <dt1>
  DT: <dt2>           ← 5x DT: stacked below CNs
  ...

All blocks have CN: and DT: label tokens at the same x0 as the device label.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from app.pipeline.extractor import WordToken

DEVICE_RE = re.compile(r'^[A-Z]{2,8}-[A-Z0-9]{2,12}$')
DT_VALUE_RE = re.compile(r'^DT-[A-Z0-9]+-[A-Z0-9-]+')
PART_RE = re.compile(r'^[A-Z0-9]{2,6}-[A-Z0-9]{4,12}(?:-[A-Z0-9]+)*$')

X_SAME = 8       # pt tolerance for "same x0"
X_VALUE = 5      # pt above the label's x1 where value starts (i.e., dx from label's right edge)
LABEL_Y_GAP = 50 # pt: device label must be within this above first CN:


@dataclass
class RawBlock:
    page: int
    device: str | None
    cn_list: list[str]
    dt_list: list[str]
    variant_list: list[str]
    x0: float
    top: float
    source: str = "spatial"


def find_device_blocks(tokens: list[WordToken], page_num: int) -> list[RawBlock]:
    blocks = _find_labeled_blocks(tokens, page_num)
    blocks.sort(key=lambda b: b.top)
    return blocks


# ---------------------------------------------------------------------------
# Main extraction: blocks identified by CN:/DT: label tokens
# ---------------------------------------------------------------------------

def _find_labeled_blocks(tokens: list[WordToken], page_num: int) -> list[RawBlock]:
    cn_toks = [t for t in tokens if t.text == "CN:"]
    if not cn_toks:
        return []

    # Resolve each CN: → its part-number value
    cn_rows: list[dict] = []
    for tok in cn_toks:
        val = _right_value(tok, tokens, "cn")
        if val:
            cn_rows.append({"top": tok.top, "x0": tok.x0, "cn_val": val, "dt_val": None})

    # Group CN rows by x0 (each group = one device block)
    groups = _group_by_x0(cn_rows, tol=X_SAME)

    used_dt_tops: set[float] = set()
    blocks: list[RawBlock] = []

    for group in groups:
        group.sort(key=lambda r: r["top"])
        _assign_dts(group, tokens, used_dt_tops)

        dt_list = [r["dt_val"] or "" for r in group]
        if not any(dt_list):
            continue

        device = _device_above(group[0]["top"], group[0]["x0"], tokens)
        blocks.append(RawBlock(
            page=page_num,
            device=device,
            cn_list=[r["cn_val"] for r in group],
            dt_list=dt_list,
            variant_list=[""] * len(group),
            x0=group[0]["x0"],
            top=group[0]["top"],
        ))

    return blocks


def _assign_dts(group: list[dict], tokens: list[WordToken], used_tops: set[float]) -> None:
    """
    Assign DT values to CN rows using strategies in order:
    1. Same-line DT — BATT-POSTIVE pattern (CN and DT on same horizontal line)
    2. Stacked DT within 15pt — ECU-BCM / SN-BMS pattern (single CN, DT just below)
       Only applied for single-CN groups to avoid consuming DTs for PDB-EXT groups.
    3. DT group below last CN — PDB-EXT pattern (all CNs stacked, then all DTs stacked)
    """
    # Strategy 1: same-line DT
    for row in group:
        dt = _sameline_dt(row["top"], row["x0"], tokens, used_tops)
        if dt:
            row["dt_val"] = dt

    # Strategy 2: stacked DT — only for single-CN groups
    if len(group) == 1 and group[0]["dt_val"] is None:
        dt = _stacked_dt(group[0]["top"], group[0]["x0"], tokens, used_tops, max_gap=15)
        if dt:
            group[0]["dt_val"] = dt

    # Strategy 3: DT group below last CN (positional pairing)
    if any(r["dt_val"] is None for r in group):
        last_top = max(r["top"] for r in group)
        x0 = group[0]["x0"]
        dt_group = _dt_group_below(last_top, x0, tokens, used_tops)
        if dt_group:
            if len(dt_group) == len(group):
                # Full set — assign positionally to ALL rows
                group.sort(key=lambda r: r["top"])
                for row, dt_val in zip(group, dt_group):
                    row["dt_val"] = dt_val
            else:
                # Partial — fill missing rows only
                missing = [r for r in group if r["dt_val"] is None]
                for row, dt_val in zip(missing, dt_group):
                    row["dt_val"] = dt_val


def _sameline_dt(cn_top: float, cn_x0: float, tokens: list[WordToken], used_tops: set[float]) -> str | None:
    """Find DT: label on the same horizontal line as a CN: entry."""
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
            return val
    return None


def _stacked_dt(cn_top: float, cn_x0: float, tokens: list[WordToken], used_tops: set[float], max_gap: float = 15) -> str | None:
    """Find DT: label directly below a CN: entry (within max_gap pt)."""
    dt_labels = [
        t for t in tokens
        if t.text == "DT:"
        and 0 < t.top - cn_top <= max_gap
        and abs(t.x0 - cn_x0) < X_SAME
        and t.top not in used_tops
    ]
    for dt_tok in sorted(dt_labels, key=lambda t: t.top):
        val = _right_value(dt_tok, tokens, "dt")
        if val:
            used_tops.add(dt_tok.top)
            return val
    return None


def _dt_group_below(last_cn_top: float, x0: float, tokens: list[WordToken], used_tops: set[float]) -> list[str]:
    """
    Find a consecutive group of DT: labels at the same x0, below last_cn_top.
    Returns DT values sorted by top (positional order).
    """
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
    """Find the value token immediately to the right of a label on the same line."""
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


def _device_above(row_top: float, row_x0: float, tokens: list[WordToken]) -> str | None:
    """Find a device label token above row_top at similar x0."""
    candidates = [
        t for t in tokens
        if DEVICE_RE.match(t.text)
        and 0 < row_top - t.top <= LABEL_Y_GAP
        and abs(t.x0 - row_x0) <= 25  # device label may be slightly left of CN:
    ]
    if candidates:
        return max(candidates, key=lambda t: t.top).text
    return None
