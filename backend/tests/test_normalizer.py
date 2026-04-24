import pytest
from app.pipeline.normalizer import strip_dt_suffix, normalize_blocks
from app.pipeline.spatial_parser import RawBlock


@pytest.mark.parametrize("dt_raw,expected", [
    ("DT-WU5T-14F141-AJX_K",  "DT-WU5T-14F141-AJX"),
    ("DT-PZ3T-10C652-AX_E",   "DT-PZ3T-10C652-AX"),
    ("DT-R1MT-10655-AA_A",    "DT-R1MT-10655-AA"),
    ("DT-DS7T-10655-AA_D",    "DT-DS7T-10655-AA"),
    ("DT-W3KT-14D068-AA",     "DT-W3KT-14D068-AA"),   # no suffix — no-op
    ("DT-W3KT-14D068-EA",     "DT-W3KT-14D068-EA"),
    ("DT-W3KT-14D068-GA",     "DT-W3KT-14D068-GA"),
    ("DT-W3KT-14D068-PA",     "DT-W3KT-14D068-PA"),
    ("DT-W3KT-14D068-HA",     "DT-W3KT-14D068-HA"),
])
def test_strip_dt_suffix(dt_raw, expected):
    assert strip_dt_suffix(dt_raw) == expected


def test_normalize_single_block():
    block = RawBlock(
        page=1,
        device="ECU-BCM",
        cn_list=["WL3T-15604-AA"],
        dt_list=["DT-WU5T-14F141-AJX_K"],
        variant_list=[""],
        x0=100,
        top=50,
    )
    rows = normalize_blocks([block])
    assert len(rows) == 1
    assert rows[0].device == "ECU-BCM"
    assert rows[0].dt == "DT-WU5T-14F141-AJX"
    assert rows[0].sr_number == 1


def test_normalize_multi_cn_dt_block():
    block = RawBlock(
        page=1,
        device="PDB-EXT",
        cn_list=["W3KT-14D068-AA", "W3KT-14D068-EA", "W3KT-14D068-GA"],
        dt_list=["DT-W3KT-14D068-AA", "DT-W3KT-14D068-EA", "DT-W3KT-14D068-GA"],
        variant_list=["(GAS LOW)", "(FHEV)", "(GAS HIGH)"],
        x0=200,
        top=100,
    )
    rows = normalize_blocks([block])
    assert len(rows) == 3
    # All rows share same DT family (DT-W3KT-14D068-*) → device repeated on all rows
    assert rows[0].device == "PDB-EXT"
    assert rows[1].device == "PDB-EXT"
    assert rows[2].device == "PDB-EXT"
    assert rows[0].dt == "DT-W3KT-14D068-AA"
    assert rows[1].dt == "DT-W3KT-14D068-EA"
    assert rows[2].dt == "DT-W3KT-14D068-GA"


def test_normalize_same_line_pair_blocks():
    # BATT-POSITIVE pattern: both CN/DT pairs share the same x0 column in the schematic,
    # so the spatial parser groups them into ONE block under the BATT-POSTIVE label.
    # Both DTs share part base "10655" (dual-source: R1MT=70AH, DS7T=80AH variants)
    # so device must repeat on BOTH rows.
    block = RawBlock(
        page=1, device="BATT-POSTIVE",
        cn_list=["R1MT-10655-AA", "DS7T-10655-AC"],
        dt_list=["DT-R1MT-10655-AA_A", "DT-DS7T-10655-AA_D"],
        variant_list=["", ""],
        x0=300, top=200,
    )
    rows = normalize_blocks([block])
    assert len(rows) == 2
    assert rows[0].device == "BATT-POSTIVE"
    assert rows[1].device == "BATT-POSTIVE"   # same part base "10655" → device repeats
    assert rows[0].dt == "DT-R1MT-10655-AA"
    assert rows[1].dt == "DT-DS7T-10655-AA"
