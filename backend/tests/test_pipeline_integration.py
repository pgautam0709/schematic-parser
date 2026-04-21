"""
Primary correctness gate: run the full pipeline on P736_BCM.pdf
and verify all 9 expected rows are produced.
"""
import asyncio
import json
import pytest
from pathlib import Path

FIXTURE_PDF = Path(__file__).parent.parent.parent / "P736_BCM (1).pdf"
EXPECTED_JSON = Path(__file__).parent / "expected_output.json"


@pytest.mark.skipif(not FIXTURE_PDF.exists(), reason="Source PDF not in project root")
def test_pipeline_produces_correct_rows():
    from app.pipeline.orchestrator import run_pipeline_from_path

    rows = asyncio.run(run_pipeline_from_path(FIXTURE_PDF))

    with open(EXPECTED_JSON) as f:
        expected = json.load(f)["rows"]

    assert len(rows) == len(expected), (
        f"Row count mismatch: got {len(rows)}, expected {len(expected)}\n"
        f"Got: {[(r.sr_number, r.device, r.dt) for r in rows]}"
    )

    for row, exp in zip(rows, expected):
        assert row.sr_number == exp["sr_number"], f"SR# mismatch at position {exp['sr_number']}"
        assert row.page_number == exp["page_number"], f"Page mismatch for SR#{exp['sr_number']}"
        assert row.device == exp["device"], (
            f"SR#{exp['sr_number']}: device '{row.device}' != '{exp['device']}'"
        )
        assert row.dt == exp["dt"], (
            f"SR#{exp['sr_number']}: DT '{row.dt}' != '{exp['dt']}'"
        )

    print(f"\nAll {len(rows)} rows verified correctly:")
    for r in rows:
        print(f"  SR#{r.sr_number}: {r.device or '(null)'} → {r.dt}")
