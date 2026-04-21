from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WordToken:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    page: int


def extract_page_words(pdf_path: str | Path) -> list[list[WordToken]]:
    """Extract word tokens per page using pdfplumber; falls back to PyMuPDF."""
    import pdfplumber

    pages_words: list[list[WordToken]] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_idx, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(
                x_tolerance=3,
                y_tolerance=3,
                keep_blank_chars=False,
                use_text_flow=False,
            )
            tokens = [
                WordToken(
                    text=w["text"],
                    x0=float(w["x0"]),
                    x1=float(w["x1"]),
                    top=float(w["top"]),
                    bottom=float(w["bottom"]),
                    page=page_idx,
                )
                for w in words
            ]
            if len(tokens) < 10:
                tokens = _fallback_pymupdf(pdf_path, page_idx)
            pages_words.append(tokens)

    return pages_words


def _fallback_pymupdf(pdf_path: str | Path, page_idx: int) -> list[WordToken]:
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    page = doc[page_idx - 1]
    words = page.get_text("words")
    doc.close()
    return [
        WordToken(
            text=w[4],
            x0=float(w[0]),
            x1=float(w[2]),
            top=float(w[1]),
            bottom=float(w[3]),
            page=page_idx,
        )
        for w in words
    ]


def words_to_text(tokens: list[WordToken]) -> str:
    """Reconstruct page text from tokens, sorted by top then x0."""
    sorted_tokens = sorted(tokens, key=lambda t: (round(t.top / 5) * 5, t.x0))
    return " ".join(t.text for t in sorted_tokens)
