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
| 9 | 1 | BATT-POSTIVE | DT-DS7T-10655-AA |

> **Note:** Row 9 correctly carries `BATT-POSTIVE` — see [Dual-Source Battery Variants](#dual-source-battery-variants) below.

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
│   │   │   ├── llm_enricher.py     # Stage 4 — Azure OpenAI GPT-4o enrichment
│   │   │   ├── normalizer.py       # Stage 5 — DT suffix strip + row expansion
│   │   │   ├── validator.py        # Stage 6 — structural checks
│   │   │   └── orchestrator.py     # Wires all stages, updates DB status
│   │   └── utils/
│   │       └── file_store.py       # PDF file storage helpers
│   ├── tests/
│   │   ├── expected_output.json    # Ground-truth for P736_BCM.pdf (9 rows)
│   │   ├── test_normalizer.py      # Unit tests (DT suffix, row expansion)
│   │   ├── test_extractor.py       # Unit tests (word extraction)
│   │   └── test_pipeline_integration.py  # End-to-end correctness gate
│   └── requirements.txt
├── frontend/                 # React + Vite + TypeScript UI
│   └── src/
│       ├── api/client.ts     # Typed fetch wrappers (XHR upload with progress)
│       ├── types/api.ts      # TypeScript interfaces
│       ├── hooks/            # useResults
│       └── components/       # UploadZone, JobList, ResultsTable, ResultsModal, ExportBar
└── data/
    ├── uploads/              # Uploaded PDFs (organised by job UUID)
    └── schematic_parser.db   # SQLite database
```

---

## Parsing Pipeline

The pipeline runs in a **background thread pool** after each upload, keeping the API responsive during processing.

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
  │     Both pairs share the same x0 column → grouped into ONE block.
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
  ▼ Stage 4 — LLM Enrichment (Azure OpenAI GPT-4o) [conditional]
  │   Called only when spatial_dt_count < regex_dt_count.
  │   Fills gaps not covered by spatial parser.
  │   Gracefully skipped if Azure credentials are not configured.
  │
  ▼ Stage 5 — Normalisation
  │   • Strips DT variant suffix: DT-WU5T-14F141-AJX_K → DT-WU5T-14F141-AJX
  │   • Expands each block into individual rows (one per CN/DT pair)
  │   • Device name repeated on all rows when DTs share the same part base number
  │     (see Dual-Source Battery Variants below)
  │   • Global SR# assigned starting at 1 across all pages
  │
  ▼ Stage 6 — Validation
      Checks DT format, detects duplicates, verifies SR# continuity.
      Warnings are logged; processing always completes.
```

---

## Key Finding: Dual-Source Battery Variants

### Problem

The `BATT-POSTIVE` block in the schematic contains two CN/DT pairs for the **same physical device position** — a 70AH and an 80AH battery, each sourced from a different manufacturer:

```
BATT-POSTIVE
CN: R1MT-10655-AA    DT: DT-R1MT-10655-AA_A    70AH
CN: DS7T-10655-AC    DT: DT-DS7T-10655-AA_D    80AH
```

The original normalizer compared the full DT manufacturer prefix (`DT-R1MT-10655` vs `DT-DS7T-10655`) to decide whether to repeat the device name across rows. Since the manufacturer codes differ (`R1MT` ≠ `DS7T`), it incorrectly treated them as separate physical components and set `device = null` on row 9.

### Root Cause

The manufacturer code (2nd segment of a DT value) identifies the **supplier**, not the component. Two DTs with different manufacturer codes but the same part base number represent **dual-source variants** of the same device:

```
DT - R1MT - 10655 - AA
     ^^^^   ^^^^^
     mfr    part base ← the identity of the physical component
```

### Fix

The family comparison in `normalizer.py` was changed to use **only the part base number** (3rd segment), ignoring the manufacturer prefix:

```python
# Before (wrong): compared "DT-R1MT-10655" vs "DT-DS7T-10655" → different → null device
families.add("-".join(parts[:3]))

# After (correct): compared "10655" vs "10655" → same → device repeats
part_bases.add(parts[2])
```

This correctly identifies `DT-R1MT-10655-AA` and `DT-DS7T-10655-AA` as variants of the same battery position, so `BATT-POSTIVE` now appears on both rows 8 and 9.

---

## Concurrency Model

Each pipeline run executes in a **`ThreadPoolExecutor`** worker, not in the async event loop. This means:

- The FastAPI event loop remains free to serve status-poll requests (every 1.5 s) while large PDFs are being parsed
- Up to `MAX_CONCURRENT_JOBS` (default: 3) pipelines run in parallel
- Each worker creates its own SQLAlchemy session (sessions are not thread-safe)

```
Upload request → FastAPI (event loop)
                     │
                     └─ BackgroundTasks.add_task(run_pipeline, upload_id)
                              │
                              └─ asyncio.run_in_executor(ThreadPoolExecutor)
                                        │
                                        └─ _run_pipeline_sync(upload_id)
                                                │
                                                ├─ SessionLocal() ← own DB session
                                                ├─ pdfplumber extraction (blocking I/O)
                                                ├─ spatial parser (CPU)
                                                ├─ Azure OpenAI call (network I/O)
                                                └─ normalizer / validator
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
| `DELETE` | `/api/jobs` | Delete all jobs, rows, and uploaded files |

---

## Setup

### Prerequisites

- Python 3.9+
- Node.js 18+

### Backend

```bash
cd backend

# Create virtual environment and install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT

# Start the API server (always use the venv's uvicorn explicitly)
bash start.sh
# or equivalently:
# PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --port 8000
```

> **Important:** Always start the server with `bash start.sh` or `.venv/bin/uvicorn`.
> Running a bare `uvicorn` command uses the system Python, which does not have
> `pdfplumber` installed, causing every pipeline job to fail.

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
| `AZURE_OPENAI_API_KEY` | *(empty)* | Azure OpenAI API key — LLM stage skipped if unset |
| `AZURE_OPENAI_ENDPOINT` | *(empty)* | Azure OpenAI resource endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | Deployment name for the GPT-4o model |
| `AZURE_OPENAI_API_VERSION` | `2024-05-01-preview` | Azure OpenAI API version |
| `DATABASE_URL` | `sqlite:///../../data/schematic_parser.db` | SQLAlchemy connection string |
| `UPLOAD_DIR` | `../../data/uploads` | Directory where uploaded PDFs are stored |
| `MAX_CONCURRENT_JOBS` | `3` | Max simultaneous pipeline runs (thread pool size) |
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
tests/test_normalizer.py::test_strip_dt_suffix[...]          PASSED  (×9)
tests/test_normalizer.py::test_normalize_single_block        PASSED
tests/test_normalizer.py::test_normalize_multi_cn_dt_block   PASSED
tests/test_normalizer.py::test_normalize_same_line_pair_blocks PASSED
tests/test_pipeline_integration.py::test_pipeline_produces_correct_rows  PASSED
```

The integration test runs the full pipeline on `P736_BCM_Example.pdf` and asserts all 9 rows — including `BATT-POSTIVE` on both rows 8 and 9 — match the ground truth in `tests/expected_output.json`.

---

## LLM Usage & Accuracy

Azure OpenAI GPT-4o is a **conditional fallback** — it is only invoked when the spatial parser misses entries:

```
spatial_dt_count < regex_dt_count  →  LLM triggered
```

If Azure credentials are not configured in `.env`, the LLM stage is gracefully skipped and the pipeline completes with spatial results only. For `P736_BCM_Example.pdf`, the spatial parser finds all 9 entries without LLM involvement.

The merge strategy ensures spatial results take precedence; GPT-4o only contributes DT entries not already found spatially.

---

## Data Standardisation Rules

| Rule | Detail |
|------|--------|
| DT suffix strip | `DT-<base>_<1-3 char suffix>` → `DT-<base>` |
| Device name — same part base | DTs sharing the same part base number (3rd segment) → device repeated on all rows |
| Device name — dual-source variants | Different manufacturer codes, same part base → treated as same device family |
| Duplicate rows | `(page, device, dt)` duplicates logged as warnings; first occurrence kept |
| SR numbering | 1-based, globally sequential across all pages, never reset |
| Variant labels | `(GAS LOW)`, `(FHEV)` etc. stored in `variant` column; stripped from CN values |

---

## Frontend UX

```
UploadZone (drag-drop multi-PDF)
  │
  ├─ Per-file row appears immediately
  │     [ filename ]  [ size ]  [ Ready ]  [ Parse ]
  │
  ├─ Click "Parse" → uploads with real progress bar (XHR)
  │     [ filename ]  [ size ]  [ Uploading 63% ████░░ ]  [ Uploading… ]
  │
  ├─ Upload complete → pipeline starts
  │     [ filename ]  [ size ]  [ Queued ]  [ Queued… ]
  │     [ filename ]  [ size ]  [ Parsing 45% ███░░░ · 12 pages ]  [ Parsing… ]
  │
  └─ Done → button changes
        [ filename ]  [ size ]  [ Done · 9 rows ]  [ View Results ]
                                                          │
                                                          └─ Opens ResultsModal overlay
                                                               (SR#, Page, Device, DT table)
                                                               (Export CSV / Excel buttons)
                                                               (Esc or click outside to close)

JobList (parse history — all past jobs)
  └─ Each completed job has its own [ View Results ] button → same ResultsModal
```

**Upload behaviour for large files:** Files are uploaded **sequentially** (one at a time) using `XMLHttpRequest` with real byte-level progress reporting. This avoids saturating the network connection when multiple large PDFs are queued.

---

## Scaling to Multiple PDFs

Each uploaded PDF is processed as an independent background job. The frontend polls job status every 1.5 seconds and displays live progress per file. Up to `MAX_CONCURRENT_JOBS` pipelines run simultaneously (controlled by a semaphore + thread pool).

For production-scale batch processing, replace `FastAPI BackgroundTasks` with a task queue (e.g. Celery + Redis) — the `orchestrator.run_pipeline` interface is unchanged.
