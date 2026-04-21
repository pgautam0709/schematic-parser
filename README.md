# Schematic Parser

A web application that parses electrical schematic PDFs and extracts a **Device → Device Tree (DT)** mapping table — one row per connector variant, ready for download.



---

## What it does

Each schematic PDF contains component blocks annotated with:
- A **device label** (e.g. `ECU-BCM`, `PDB-EXT`, `SN-BMS`, `BATT-POSTIVE`)
- One or more **Connector Numbers** (`CN: <part-number>`)
- One or more **Device Tree identifiers** (`DT: DT-<part-number>_<variant-suffix>`)

The parser extracts these annotations, strips the variant suffix from DT values, and produces a clean table:

| SR # | Page No | Device | DT |
|------|---------|--------|----|
| 1 | 1 | ECU-BCM | DT-WU5T-14F141-AJX |
| 2 | 1 | PDB-EXT | DT-W3KT-14D068-AA |
| 3 | 1 | PDB-EXT | DT-W3KT-14D068-EA |
| 4 | 1 | PDB-EXT | DT-W3KT-14D068-GA |
| 5 | 1 | PDB-EXT | DT-W3KT-14D068-PA |
| 6 | 1 | PDB-EXT | DT-W3KT-14D068-HA |
| 7 | 1 | SN-BMS | DT-PZ3T-10C652-AX |
| 8 | 1 | BATT-POSTIVE | DT-R1MT-10655-AA |
| 9 | 1 | *(unnamed)* | DT-DS7T-10655-AA |

---

## Architecture

```
schematic-parser/
├── backend/                  # Python FastAPI service
│   ├── app/
│   │   ├── main.py           # FastAPI app, CORS, startup
│   │   ├── config.py         # Env-var settings
│   │   ├── database.py       # SQLAlchemy + SQLite
│   │   ├── models.py         # Upload + ParsedRow ORM tables
│   │   ├── schemas.py        # Pydantic request/response models
│   │   ├── api/              # REST endpoints
│   │   │   ├── upload.py     # POST /api/upload
│   │   │   ├── jobs.py       # GET  /api/jobs[/{id}]
│   │   │   ├── results.py    # GET  /api/results/{id}
│   │   │   ├── export.py     # GET  /api/export/{id}?format=csv|xlsx
│   │   │   └── delete.py     # DELETE /api/jobs/{id}
│   │   ├── pipeline/         # 6-stage parsing pipeline
│   │   │   ├── extractor.py        # Stage 1 — pdfplumber word extraction
│   │   │   ├── spatial_parser.py   # Stage 2 — spatial block detection
│   │   │   ├── regex_pass.py       # Stage 3 — regex cross-validation
│   │   │   ├── llm_enricher.py     # Stage 4 — Claude API fallback
│   │   │   ├── normalizer.py       # Stage 5 — DT suffix strip + row expansion
│   │   │   ├── validator.py        # Stage 6 — structural checks
│   │   │   └── orchestrator.py     # Wires all stages, updates DB status
│   │   └── utils/
│   │       └── file_store.py       # PDF file storage helpers
│   ├── tests/
│   │   ├── expected_output.json    # Ground-truth for P736_BCM.pdf
│   │   ├── test_normalizer.py      # Unit tests (DT suffix, row expansion)
│   │   ├── test_extractor.py       # Unit tests (word extraction)
│   │   └── test_pipeline_integration.py  # End-to-end correctness gate
│   └── requirements.txt
├── frontend/                 # React + Vite + TypeScript UI
│   └── src/
│       ├── api/client.ts     # Typed fetch wrappers for all endpoints
│       ├── types/api.ts      # TypeScript interfaces
│       ├── hooks/            # useUpload, useJobPoller, useResults
│       └── components/       # UploadZone, JobList, ResultsTable, ExportBar
└── data/
    ├── uploads/              # Uploaded PDFs (organised by job UUID)
    └── schematic_parser.db   # SQLite database
```

---

## Parsing Pipeline

The pipeline runs automatically in the background after each upload.

```
PDF file
  │
  ▼ Stage 1 — Text Extraction (pdfplumber)
  │   Extracts word tokens with x/y coordinates per page.
  │   Falls back to PyMuPDF for image-heavy pages.
  │
  ▼ Stage 2 — Spatial Block Detection
  │   Detects three block patterns from the PDF layout:
  │
  │   Pattern A — Stack (ECU-BCM, SN-BMS):
  │     Device label → CN: value → DT: value (stacked vertically)
  │
  │   Pattern B — Same-line (BATT-POSTIVE):
  │     Device label → CN: <cn1>  DT: <dt1>  (CN and DT on same line)
  │                     CN: <cn2>  DT: <dt2>
  │
  │   Pattern C — Grouped (PDB-EXT):
  │     Device label → CN: <cn1>         (all CNs stacked first)
  │                     CN: <cn2> ...
  │                     DT: <dt1>         (all DTs stacked below)
  │                     DT: <dt2> ...
  │                     → paired positionally
  │
  ▼ Stage 3 — Regex Cross-Validation
  │   Counts CN:/DT: patterns in raw text. If spatial parser
  │   found fewer DTs than regex found, LLM stage is triggered.
  │
  ▼ Stage 4 — LLM Enrichment (Claude claude-sonnet-4-6) [optional]
  │   Called only when spatial parsing is incomplete.
  │   Uses prompt caching to reduce API cost across multi-page PDFs.
  │   Fills gaps not covered by spatial parser.
  │
  ▼ Stage 5 — Normalisation
  │   • Strips DT variant suffix: DT-WU5T-14F141-AJX_K → DT-WU5T-14F141-AJX
  │   • Expands each block into individual rows (one per CN/DT pair)
  │   • Device name repeated on all rows when DTs share the same part family
  │     (PDB-EXT: DT-W3KT-14D068-* → all 5 rows get "PDB-EXT")
  │   • Device set to null when DTs belong to different physical components
  │     (BATT-POSTIVE row 9: DT-DS7T-10655-AA → null device)
  │   • Global SR# assigned starting at 1 across all pages
  │
  ▼ Stage 6 — Validation
      Checks DT format, detects duplicates, verifies SR# continuity.
      Warnings are logged; processing always completes.
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/upload` | Upload one or more PDF files; returns job IDs |
| `GET` | `/api/jobs` | List all parse jobs (most recent first) |
| `GET` | `/api/jobs/{id}` | Poll single job status + `progress_pct` |
| `GET` | `/api/results/{id}` | Fetch parsed rows for a completed job |
| `GET` | `/api/export/{id}?format=csv` | Download results as CSV (UTF-8 BOM) |
| `GET` | `/api/export/{id}?format=xlsx` | Download results as Excel |
| `DELETE` | `/api/jobs/{id}` | Delete job, rows, and uploaded file |

---

## Setup

### Prerequisites

- Python 3.9+
- Node.js 18+

### Backend

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY if LLM fallback is needed

# Start the API server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

npm install
npm run dev        # starts at http://localhost:5173
```

The Vite dev server proxies `/api/*` requests to `http://localhost:8000`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(empty)* | Required only when LLM fallback is triggered |
| `DATABASE_URL` | `sqlite:///../../data/schematic_parser.db` | SQLAlchemy connection string |
| `UPLOAD_DIR` | `../../data/uploads` | Directory where uploaded PDFs are stored |
| `MAX_CONCURRENT_JOBS` | `3` | Max simultaneous pipeline runs |
| `MAX_PDF_SIZE_MB` | `100` | Upload size limit per file |

---

## Running Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

Expected output:
```
tests/test_normalizer.py::test_strip_dt_suffix[...]   PASSED  (×9)
tests/test_normalizer.py::test_normalize_*            PASSED  (×3)
tests/test_pipeline_integration.py::test_pipeline_produces_correct_rows  PASSED
```

The integration test uploads `P736_BCM (1).pdf` through the full pipeline and asserts
all 9 rows match the ground truth in `tests/expected_output.json`.

---

## LLM Usage & Accuracy

The Claude claude-sonnet-4-6 model is used as a **fallback only** — it is not called when spatial
parsing succeeds. The trigger condition is:

```
spatial_dt_count < regex_dt_count
```

If the spatial parser finds fewer DTs than the raw-text regex count, Claude is invoked
with the full page text to extract device→CN→DT mappings, and its output is merged with
the spatial results.

**Prompt caching** is enabled on the system prompt (via `cache_control: ephemeral`),
so repeated calls on the same model session reuse the cached prompt — reducing latency
and cost for large, multi-page PDFs.

For the sample PDF (`P736_BCM (1).pdf`), the spatial parser correctly finds all 9 entries
without LLM involvement.

---

## Data Standardisation Rules

| Rule | Detail |
|------|--------|
| DT suffix strip | `DT-<base>_<1-3 char suffix>` → `DT-<base>` |
| Device name — same family | DTs sharing `DT-<mfr>-<part>` prefix → device repeated on all rows |
| Device name — mixed family | Different part families in one block → device only on first row, null thereafter |
| Duplicate rows | `(page, device, dt)` duplicates logged as warnings; first occurrence kept |
| SR numbering | 1-based, globally sequential across all pages, never reset |
| Variant labels | `(GAS LOW)`, `(FHEV)` etc. stored in `variant` column; stripped from CN values |

---

## Scaling to Multiple PDFs

Each uploaded PDF is processed as an independent background job. The frontend polls
job status every 2 seconds and displays live progress. Up to `MAX_CONCURRENT_JOBS`
pipelines run simultaneously (controlled by an asyncio semaphore).

For production-scale batch processing, replace `FastAPI BackgroundTasks` with a
task queue (e.g. Celery + Redis) — the `orchestrator.run_pipeline` interface is
unchanged.
