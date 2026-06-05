# Schematic Parser CLI

A standalone command-line tool that reads Ford Motor Company electrical schematic PDFs and produces a **Component → DT mapping Excel file** — one row per DT per component, ready for review.

---

## Output

| Page Number | Component Name | DT Name | Comment | Confidence Spatial | Confidence LLM |
|:-----------:|---------------|---------|---------|:-----------------:|:--------------:|
| 1 | ECU-BCM | DT-WU5T-14F141-AJX_K | | 1.0 | 0.0 |
| 1 | PDB-EXT | DT-W3KT-14D068-AA | needs review | 0.9 | 0.0 |
| 1 | PDB-EXT | DT-W3KT-14D068-EA | needs review | 0.9 | 0.0 |
| 1 | PDB-EXT | DT-W3KT-14D068-GA | needs review | 0.9 | 0.0 |
| 1 | PDB-EXT | DT-W3KT-14D068-PA | needs review | 0.9 | 0.0 |
| 1 | PDB-EXT | DT-W3KT-14D068-HA | needs review | 0.9 | 0.0 |
| 1 | SN-BMS | DT-PZ3T-10C652-AX_E | | 1.0 | 0.0 |
| 1 | BATT-POSTIVE | DT-R1MT-10655-AA_A | needs review | 0.9 | 0.0 |
| 1 | BATT-POSTIVE | DT-DS7T-10655-AA_D | needs review | 0.9 | 0.0 |

- **DT Name** — full value preserved exactly as printed (`_K`, `/K`, or no suffix — never stripped)
- **Comment** — `needs review` when a component has more than one DT on the same page
- **Confidence Spatial** — how cleanly the spatial parser matched the layout (0.0–1.0)
- **Confidence LLM** — LLM confidence when the LLM was used to fill gaps (0.0 = spatial only)

Rows flagged `needs review` are highlighted in **yellow** in the Excel file.

---

## Setup

### Prerequisites

- Python 3.9+
- An LLM provider account (optional — only needed if LLM enrichment is enabled):
  - **Azure OpenAI** — resource with GPT-4o deployed
  - **Google Cloud** — project with Vertex AI API enabled

### Install

```bash
cd cli_backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env — set LLM_PROVIDER and fill in the matching credentials block
```

**Azure OpenAI:**
```env
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
```

**Google Cloud Vertex AI:**
```env
LLM_PROVIDER=gcp
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
GCP_MODEL=gemini-2.0-flash
# Option A — service account key file:
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
# Option B — use gcloud CLI (no key file needed):
#   gcloud auth application-default login
```

`.env` settings:

### Provider selection

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | *(empty)* | `azure` or `gcp` — leave blank to disable LLM entirely |

### Azure OpenAI (`LLM_PROVIDER=azure`)

| Variable | Default | Description |
|----------|---------|-------------|
| `AZURE_OPENAI_API_KEY` | *(empty)* | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | *(empty)* | Resource endpoint URL (e.g. `https://<resource>.openai.azure.com/`) |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4o` | Deployment name |
| `AZURE_OPENAI_API_VERSION` | `2024-05-01-preview` | API version |

### Google Cloud Vertex AI (`LLM_PROVIDER=gcp`)

| Variable | Default | Description |
|----------|---------|-------------|
| `GCP_PROJECT_ID` | *(empty)* | Google Cloud project ID |
| `GCP_LOCATION` | `us-central1` | Vertex AI region |
| `GCP_MODEL` | `gemini-2.0-flash` | Model name — `gemini-2.0-flash` (fast) or `gemini-1.5-pro` (higher quality) |
| `GOOGLE_APPLICATION_CREDENTIALS` | *(empty)* | Path to service account key JSON file. If unset, [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials) are used (`gcloud auth application-default login`) |

### Pipeline tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `CONFIDENCE_THRESHOLD` | `0.65` | Pages with spatial confidence below this trigger LLM enrichment |
| `LLM_BATCH_SIZE` | `5` | Number of pages sent per LLM call (for large PDFs) |

---

## Running with Azure OpenAI

**Step 1 — Set credentials in `.env`:**
```env
LLM_PROVIDER=azure
AZURE_OPENAI_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_OPENAI_API_VERSION=2024-05-01-preview
```

**Step 2 — Run:**
```bash
python parse_schematics.py schematic.pdf --output results.xlsx
```

The LLM is called only for pages where the spatial parser confidence falls below `CONFIDENCE_THRESHOLD` (default 0.65). To force LLM on every page:
```bash
python parse_schematics.py schematic.pdf --confidence-threshold 1.0 --output results.xlsx
```

---

## Running with Google Cloud Vertex AI

### Prerequisites
1. [Create a Google Cloud project](https://console.cloud.google.com/projectcreate) (if you don't have one)
2. [Enable the Vertex AI API](https://console.cloud.google.com/apis/library/aiplatform.googleapis.com) for your project

### Authentication — choose one option

**Option A — Service account key file (recommended for automation):**
```bash
# 1. Create a service account in GCP Console → IAM → Service Accounts
# 2. Grant it the "Vertex AI User" role
# 3. Create and download a JSON key
# 4. Set the path in .env:
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account-key.json
```

**Option B — gcloud CLI (easiest for local development):**
```bash
# Install gcloud SDK: https://cloud.google.com/sdk/docs/install
gcloud auth application-default login
# No key file needed — credentials are stored automatically
```

**Step 2 — Set configuration in `.env`:**
```env
LLM_PROVIDER=gcp
GCP_PROJECT_ID=your-gcp-project-id
GCP_LOCATION=us-central1
GCP_MODEL=gemini-2.0-flash
# GCP_MODEL=gemini-1.5-pro    ← use this for higher accuracy on complex pages
```

**Step 3 — Run:**
```bash
python parse_schematics.py schematic.pdf --output results.xlsx
```

### Choosing a Gemini model

| Model | Speed | Quality | Best for |
|-------|-------|---------|----------|
| `gemini-2.0-flash` | Fast | Good | Most schematics — default choice |
| `gemini-1.5-pro` | Slower | Higher | Complex pages, low spatial confidence |

---

## Running without LLM (spatial parser only)

No cloud credentials needed. The spatial parser handles most well-structured schematics:
```bash
python parse_schematics.py schematic.pdf --no-llm --output results.xlsx
```

---

## Usage

```bash
# Parse a single PDF (spatial parser only, no LLM)
python parse_schematics.py schematic.pdf --no-llm --output results.xlsx

# Parse a single PDF with LLM enrichment (uses threshold from .env)
python parse_schematics.py schematic.pdf --output results.xlsx

# Parse multiple PDFs into one combined Excel file
python parse_schematics.py file1.pdf file2.pdf file3.pdf --output combined.xlsx

# Override the confidence threshold from the command line
python parse_schematics.py schematic.pdf --confidence-threshold 0.80 --output results.xlsx

# Always trigger LLM on every page (threshold = 1.0)
python parse_schematics.py schematic.pdf --confidence-threshold 1.0 --output results.xlsx
```

### All options

```
usage: parse_schematics.py [-h] [--output PATH] [--confidence-threshold N] [--no-llm] [--verbose] PDF [PDF ...]

positional arguments:
  PDF                        One or more schematic PDF files to parse

optional arguments:
  --output PATH              Output Excel file path (default: output.xlsx)
  --confidence-threshold N   Spatial confidence threshold 0.0–1.0 (overrides .env)
  --no-llm                   Disable LLM enrichment; use spatial parser only
  --verbose                  Enable DEBUG logging
```

---

## How It Works

The tool runs a 5-stage pipeline per PDF:

```
PDF file
  │
  ▼ Stage 1 — Text Extraction (pdfplumber)
  │   Extracts word tokens with x/y coordinates per page.
  │   Falls back to PyMuPDF for image-heavy pages (<10 tokens).
  │
  ▼ Stage 2 — Spatial Block Detection
  │   Detects component blocks using three layout patterns:
  │
  │   Pattern A — Stack (ECU-BCM, SN-BMS):
  │     Component label → CN: value → DT: value (stacked vertically)
  │     Confidence: 1.0
  │
  │   Pattern B — Same-line (BATT-POSTIVE):
  │     Component label → CN: <cn1>  DT: <dt1>  (on same line)
  │                        CN: <cn2>  DT: <dt2>
  │     Confidence: 0.9
  │
  │   Pattern C — Grouped (PDB-EXT):
  │     Component label → CN: <cn1>  (all CNs stacked first)
  │                        CN: <cn2>
  │                        DT: <dt1>  (all DTs stacked below → paired positionally)
  │                        DT: <dt2>
  │     Confidence: 0.9
  │
  │   Each block gets a confidence score (0.0–1.0) based on how cleanly
  │   the layout matched a known pattern. Page-level confidence is the
  │   weighted mean across all blocks on the page.
  │
  ▼ Stage 3 — Regex Cross-Validation
  │   Counts CN:/DT: tokens in raw text. If spatial parser found fewer DTs
  │   than the regex count, or page confidence < threshold → LLM triggered.
  │
  ▼ Stage 4 — LLM Enrichment [conditional]
  │   Triggered only when spatial confidence < threshold OR missed DTs detected.
  │   Provider selected via LLM_PROVIDER env var (azure | gcp | unset=disabled).
  │   Large PDFs are batched: LLM_BATCH_SIZE pages per API call.
  │   Failed batches are retried up to 3 times with exponential backoff.
  │   Spatial results always take precedence; LLM only fills gaps.
  │   Gracefully skipped if LLM_PROVIDER is unset or credentials are missing.
  │
  ▼ Stage 5 — Normalization
      Groups DTs by component name.
      Outputs one row per DT — NO suffix stripping (full DT value kept).
      Flags "needs review" when a component has more than one DT.
```

---

## Confidence Scores

| Score | Meaning |
|-------|---------|
| 1.0 | Perfect stack layout — label, CN:, DT: all aligned in the same x-column |
| 0.9 | Same-line pair or grouped CN/DT with matching counts |
| 0.85 | Stack with slight x-offset (tolerance applied) |
| 0.6 | Label found, but CN/DT at loose proximity |
| 0.5 | Grouped layout but CN count ≠ DT count (partial match) |
| 0.3 | No component label found (orphan CN/DT tokens) |
| 0.75 | LLM-sourced block |

When `Confidence Spatial = 0` and `Confidence LLM > 0`, the row came entirely from LLM enrichment.

---

## Supported DT Formats

The tool preserves DT values exactly as printed — no normalisation or stripping:

| Format | Example |
|--------|---------|
| Underscore suffix | `DT-WU5T-14F141-AJX_K` |
| Slash suffix | `DT-WU5T-14F141-AJX/K` |
| No suffix | `DT-W3KT-14D068-AA` |
| TBD placeholder | `TBD` |

---

## Supported Component Label Patterns

| Pattern | Examples |
|---------|---------|
| Named modules | `ECU-BCM`, `PDB-EXT`, `SN-BMS`, `BATT-POSTIVE`, `GWM-XXX`, `IPC-XXX` |
| Alphanumeric | `E515-1`, `E820-1`, `CF02`, `HP01`, `BB01`, `FAN-COOL`, `TRANSDR-FTPT` |

---

## Project Structure

```
cli_backend/
├── parse_schematics.py      # CLI entry point (argparse)
├── exporter.py              # openpyxl Excel writer
├── pipeline/
│   ├── extractor.py         # Stage 1 — pdfplumber word extraction
│   ├── spatial_parser.py    # Stage 2 — spatial block detection + confidence scoring
│   ├── regex_pass.py        # Stage 3 — regex cross-validation
│   ├── llm_enricher.py      # Stage 4 — Azure / GCP LLM enrichment (batched, retried)
│   ├── normalizer.py        # Stage 5 — component-centric rows, no suffix stripping
│   └── orchestrator.py      # Wires all stages, handles LLM trigger logic
├── requirements.txt
└── .env.example
```

---

## Portability

This folder is fully self-contained — it has no dependency on the web application in `../backend/`. To deploy on a new machine:

1. Copy the `cli_backend/` folder
2. Create a virtual environment and install dependencies
3. Copy `.env.example` → `.env`, set `LLM_PROVIDER`, and add the matching credentials
4. Run `python parse_schematics.py`
