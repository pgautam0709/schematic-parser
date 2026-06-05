#!/usr/bin/env python3
"""
Schematic PDF Parser — CLI entry point.

Reads one or more Ford schematic PDFs and writes a Component → DT mapping
Excel file.

Usage:
    python parse_schematics.py FILE [FILE ...] [OPTIONS]

Options:
    --output PATH               Output Excel file path (default: output.xlsx)
    --confidence-threshold N    Float 0.0–1.0. Pages with spatial confidence
                                below this trigger LLM enrichment.
                                Overrides CONFIDENCE_THRESHOLD in .env.
                                Default: 0.65
    --no-llm                    Disable LLM enrichment entirely (spatial only).
    --verbose                   Enable DEBUG logging.

Environment (.env):
    AZURE_OPENAI_API_KEY        Azure OpenAI API key
    AZURE_OPENAI_ENDPOINT       Azure OpenAI resource endpoint
    AZURE_OPENAI_DEPLOYMENT     Deployment name (default: gpt-4o)
    AZURE_OPENAI_API_VERSION    API version (default: 2024-05-01-preview)
    CONFIDENCE_THRESHOLD        Default spatial confidence threshold (default: 0.65)
    LLM_BATCH_SIZE              Pages per LLM call (default: 5)

Output Excel columns:
    Page Number | Component Name | DT Name | Comment | Confidence Spatial | Confidence LLM

"needs review" comment appears when a component has more than one DT on the same page.
"""
import argparse
import logging
import sys
from pathlib import Path

# Load .env before any pipeline imports read os.getenv
from dotenv import load_dotenv
load_dotenv()

from pipeline.orchestrator import run_pipeline
from exporter import write_excel


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse Ford schematic PDFs and export Component→DT mapping to Excel.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "pdfs",
        nargs="+",
        type=Path,
        metavar="PDF",
        help="One or more schematic PDF files to parse",
    )
    parser.add_argument(
        "--output",
        default="output.xlsx",
        metavar="PATH",
        help="Output Excel file path (default: output.xlsx)",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=None,
        metavar="N",
        help="Spatial confidence threshold 0.0–1.0 (overrides .env CONFIDENCE_THRESHOLD)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM enrichment; use spatial parser only",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    # Validate inputs
    missing = [p for p in args.pdfs if not p.exists()]
    if missing:
        for p in missing:
            logging.error("File not found: %s", p)
        return 1

    all_rows = []
    errors = []

    for pdf_path in args.pdfs:
        try:
            logging.info("Parsing %s …", pdf_path.name)
            rows = run_pipeline(
                pdf_path,
                threshold=args.confidence_threshold,
                use_llm=not args.no_llm,
            )
            all_rows.extend(rows)
            logging.info("  → %d rows extracted", len(rows))
        except Exception as exc:
            logging.error("Failed to parse %s: %s", pdf_path.name, exc)
            errors.append((pdf_path, exc))

    if not all_rows:
        logging.warning("No rows extracted from any file.")
        if errors:
            return 1

    output_path = Path(args.output)
    try:
        write_excel(all_rows, output_path)
        logging.info("Written %d total rows → %s", len(all_rows), output_path)
    except Exception as exc:
        logging.error("Failed to write Excel: %s", exc)
        return 1

    # Summary
    needs_review = sum(1 for r in all_rows if r.comment == "needs review")
    print(f"\nDone. {len(all_rows)} rows written to {output_path}")
    if needs_review:
        print(f"  {needs_review} row(s) flagged 'needs review' (multiple DTs per component)")
    if errors:
        print(f"  {len(errors)} file(s) failed to parse (see log above)")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
