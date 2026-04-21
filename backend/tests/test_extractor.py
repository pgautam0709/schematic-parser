import pytest
from pathlib import Path
from app.pipeline.extractor import extract_page_words, words_to_text

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "P736_BCM.pdf"


@pytest.mark.skipif(not FIXTURE_PDF.exists(), reason="Fixture PDF not present")
def test_extract_page_count():
    pages = extract_page_words(FIXTURE_PDF)
    assert len(pages) == 1


@pytest.mark.skipif(not FIXTURE_PDF.exists(), reason="Fixture PDF not present")
def test_extract_word_count():
    pages = extract_page_words(FIXTURE_PDF)
    assert len(pages[0]) >= 100


@pytest.mark.skipif(not FIXTURE_PDF.exists(), reason="Fixture PDF not present")
def test_known_devices_present():
    pages = extract_page_words(FIXTURE_PDF)
    text = words_to_text(pages[0])
    for device in ["ECU-BCM", "PDB-EXT", "SN-BMS", "BATT-POSTIVE"]:
        assert device in text, f"Expected device '{device}' not found in extracted text"


@pytest.mark.skipif(not FIXTURE_PDF.exists(), reason="Fixture PDF not present")
def test_known_dt_values_present():
    pages = extract_page_words(FIXTURE_PDF)
    text = words_to_text(pages[0])
    for dt in ["DT-WU5T-14F141-AJX", "DT-W3KT-14D068-AA", "DT-PZ3T-10C652-AX"]:
        assert dt in text, f"Expected DT '{dt}' not found in extracted text"
