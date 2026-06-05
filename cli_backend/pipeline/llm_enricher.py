"""
Stage 4 — LLM Enrichment.

Triggered when spatial parser confidence < threshold OR spatial found fewer DTs than regex.
Processes pages in batches (default 5 pages per call) to handle large PDFs efficiently.

Supported providers (set LLM_PROVIDER in .env):
  azure  — Azure OpenAI (GPT-4o)
  gcp    — Google Cloud Vertex AI (Gemini)
  unset  — LLM enrichment disabled; spatial parser results used as-is

Azure configuration:
  AZURE_OPENAI_API_KEY        required
  AZURE_OPENAI_ENDPOINT       required  (https://<resource>.openai.azure.com/)
  AZURE_OPENAI_DEPLOYMENT     default: gpt-4o
  AZURE_OPENAI_API_VERSION    default: 2024-05-01-preview

GCP configuration:
  GCP_PROJECT_ID              required
  GCP_LOCATION                default: us-central1
  GCP_MODEL                   default: gemini-2.0-flash
  GOOGLE_APPLICATION_CREDENTIALS  optional — path to service account key JSON
                                   if unset, Application Default Credentials are used

Pipeline tuning:
  LLM_BATCH_SIZE              default: 5 pages per call
"""
from __future__ import annotations
import json
import logging
import os
import re
import time
from pipeline.spatial_parser import RawBlock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared system prompt (same for both providers)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert at parsing Ford Motor Company electrical schematic PDFs.

Your task is to extract Component → DT (Device Tree) mappings from schematic page text.

## Component label patterns
Component labels appear directly above or near their CN:/DT: entries. They follow these formats:
- Named modules:   ECU-XXX, PDB-XXX, SN-XXX, BATT-XXX, GWM-XXX, IPC-XXX, PEPS-XXX, HCU-XXX
- Alphanumeric:    E515-1, E820-1, E922-1, CF02, HP01, BB01, BA01 (letter prefix + digits + optional dash+digit)

## DT value formats (PRESERVE EXACTLY — do not modify, strip, or normalise)
Three suffix formats are used — extract the full raw value exactly as printed:
  Underscore suffix:   DT-WU5T-14F141-AJX_K
  Slash suffix:        DT-WU5T-14F141-AJX/K
  No suffix:           DT-W3KT-14D068-AA
  TBD placeholder:     TBD  (use the literal string "TBD" when the schematic shows TBD)

## Pairing rules (CN ↔ DT)
1. Stack layout (most common):
   Component label appears above a block:
     CN: <value>
     DT: <value>
   → one pair; component label assigned to it.

2. Grouped layout (e.g. PDB-EXT):
   All CN: values listed first (stacked), then all DT: values listed below (stacked).
   → pair positionally: CN[0]↔DT[0], CN[1]↔DT[1], etc.

3. Same-line layout (e.g. BATT-POSTIVE):
   CN: <value>   DT: <value>   — both on same line
   → one pair per line; ALL pairs share the same component label.

4. When a component has multiple CN/DT pairs, ALL pairs share the same component label.
   Do NOT leave device empty for subsequent pairs.

## Output format
Return ONLY valid JSON — no markdown, no explanation, no code fences.
Include ALL pages from the input even if a page has no entries (use empty blocks list).

{
  "pages": [
    {
      "page": <int>,
      "blocks": [
        {
          "device": "<component label, or empty string if truly unknown>",
          "pairs": [
            {
              "cn": "<CN part number, or empty string>",
              "dt_raw": "<full DT value exactly as printed, including suffix>",
              "variant": "<variant label in parentheses e.g. (GAS LOW), or empty>"
            }
          ]
        }
      ]
    }
  ]
}"""

# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

_RETRY_EXCEPTIONS = (Exception,)  # broadened — provider SDKs raise different types
_MAX_RETRIES = 3
_RETRY_BACKOFF = [2, 5, 10]  # seconds between retries


def _call_with_retry(fn, batch: list[int]):
    """Call fn(); retry up to _MAX_RETRIES times on failure with backoff."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            wait = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
            logger.warning(
                "LLM call failed (attempt %d/%d) for batch %s: %s — retrying in %ds",
                attempt + 1, _MAX_RETRIES, batch, exc, wait,
            )
            time.sleep(wait)
    logger.error("LLM call permanently failed for batch %s after %d attempts: %s",
                 batch, _MAX_RETRIES, last_exc)
    return None  # caller handles None → skip batch


# ---------------------------------------------------------------------------
# JSON extraction — handles models that wrap output in markdown fences
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict:
    """
    Parse JSON from LLM output robustly.
    Strips markdown code fences (```json ... ```) if present.
    Raises json.JSONDecodeError if content is not valid JSON after stripping.
    """
    text = raw.strip()

    # Strip ```json ... ``` or ``` ... ``` fences
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    return json.loads(text)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def enrich_batch(
    pages_text: dict[int, str],
    batch_size: int | None = None,
) -> dict[int, list[RawBlock]]:
    """
    Enrich a set of pages using the configured LLM provider.

    Selects provider from LLM_PROVIDER env var:
      "azure" → Azure OpenAI
      "gcp"   → Google Cloud Vertex AI (Gemini)
      unset   → skip, return empty dict

    Args:
        pages_text: {page_num: raw_text} for pages needing enrichment
        batch_size: pages per LLM call (default: LLM_BATCH_SIZE env var, or 5)

    Returns:
        {page_num: list[RawBlock]}  source="llm", confidence=0.75
    """
    provider = os.getenv("LLM_PROVIDER", "").strip().lower()

    if not provider:
        logger.info("LLM_PROVIDER not set — skipping LLM enrichment.")
        return {}

    if batch_size is None:
        batch_size = int(os.getenv("LLM_BATCH_SIZE", "5"))

    if provider == "azure":
        return _enrich_azure(pages_text, batch_size)
    elif provider == "gcp":
        return _enrich_gcp(pages_text, batch_size)
    else:
        logger.error(
            "Unknown LLM_PROVIDER '%s'. Valid values: 'azure', 'gcp'. "
            "Skipping LLM enrichment.",
            provider,
        )
        return {}


# ---------------------------------------------------------------------------
# Azure OpenAI provider
# ---------------------------------------------------------------------------

def _enrich_azure(pages_text: dict[int, str], batch_size: int) -> dict[int, list[RawBlock]]:
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o").strip()
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview").strip()

    # Validate credentials before doing any work
    missing = []
    if not api_key:
        missing.append("AZURE_OPENAI_API_KEY")
    if not endpoint:
        missing.append("AZURE_OPENAI_ENDPOINT")
    if missing:
        logger.error(
            "Azure provider selected but missing required env vars: %s. "
            "Skipping LLM enrichment.",
            ", ".join(missing),
        )
        return {}

    try:
        from openai import AzureOpenAI
    except ImportError:
        logger.error("openai package not installed. Run: pip install openai>=1.13.0")
        return {}

    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
    )

    results: dict[int, list[RawBlock]] = {}
    page_nums = sorted(pages_text.keys())

    for i in range(0, len(page_nums), batch_size):
        batch = page_nums[i : i + batch_size]
        xml_input = _build_xml_input(batch, pages_text)
        logger.info("Azure LLM enrichment: pages %s", batch)

        def call_azure():
            response = client.chat.completions.create(
                model=deployment,
                max_tokens=8192,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_message(batch, xml_input)},
                ],
            )
            return response.choices[0].message.content

        raw = _call_with_retry(call_azure, batch)
        if raw is None:
            continue  # batch failed permanently — skip, continue with next

        try:
            data = _extract_json(raw)
            results.update(_parse_llm_response(data))
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Failed to parse Azure LLM response for batch %s: %s\nRaw: %.200s",
                         batch, exc, raw)

    return results


# ---------------------------------------------------------------------------
# Google Cloud Vertex AI provider
# ---------------------------------------------------------------------------

def _enrich_gcp(pages_text: dict[int, str], batch_size: int) -> dict[int, list[RawBlock]]:
    project_id = os.getenv("GCP_PROJECT_ID", "").strip()
    location = os.getenv("GCP_LOCATION", "us-central1").strip()
    model_name = os.getenv("GCP_MODEL", "gemini-2.0-flash").strip()
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

    if not project_id:
        logger.error(
            "GCP provider selected but GCP_PROJECT_ID is not set. "
            "Skipping LLM enrichment."
        )
        return {}

    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, GenerationConfig
    except ImportError:
        logger.error(
            "google-cloud-aiplatform package not installed. "
            "Run: pip install google-cloud-aiplatform>=1.49.0"
        )
        return {}

    # Set credentials file path if provided
    if credentials_path:
        if not os.path.exists(credentials_path):
            logger.error(
                "GOOGLE_APPLICATION_CREDENTIALS path does not exist: %s",
                credentials_path,
            )
            return {}
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

    try:
        vertexai.init(project=project_id, location=location)
        model = GenerativeModel(model_name)
    except Exception as exc:
        logger.error("Failed to initialise Vertex AI (project=%s, location=%s): %s",
                     project_id, location, exc)
        return {}

    # Gemini supports JSON mode via response_mime_type
    generation_config = GenerationConfig(
        response_mime_type="application/json",
        max_output_tokens=8192,
        temperature=0.0,  # deterministic output for structured extraction
    )

    results: dict[int, list[RawBlock]] = {}
    page_nums = sorted(pages_text.keys())

    for i in range(0, len(page_nums), batch_size):
        batch = page_nums[i : i + batch_size]
        xml_input = _build_xml_input(batch, pages_text)
        user_message = _build_user_message(batch, xml_input)
        # Gemini: prepend system prompt into the user turn (no system role in basic API)
        full_prompt = f"{SYSTEM_PROMPT}\n\n{user_message}"
        logger.info("GCP LLM enrichment: pages %s (model=%s)", batch, model_name)

        def call_gcp():
            response = model.generate_content(
                full_prompt,
                generation_config=generation_config,
            )
            if not response.candidates:
                raise ValueError("Vertex AI returned no candidates")
            return response.text

        raw = _call_with_retry(call_gcp, batch)
        if raw is None:
            continue

        try:
            data = _extract_json(raw)
            results.update(_parse_llm_response(data))
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.error("Failed to parse GCP LLM response for batch %s: %s\nRaw: %.200s",
                         batch, exc, raw)

    return results


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_xml_input(batch: list[int], pages_text: dict[int, str]) -> str:
    return "\n".join(
        f'<page num="{n}">\n{pages_text[n]}\n</page>' for n in batch
    )


def _build_user_message(batch: list[int], xml_input: str) -> str:
    return (
        f"Extract all Component→DT mappings from the following "
        f"{len(batch)} schematic page(s):\n\n{xml_input}"
    )


def _parse_llm_response(data: dict) -> dict[int, list[RawBlock]]:
    """
    Convert LLM JSON response into {page_num: [RawBlock]}.
    Confidence for LLM-sourced blocks is 0.75.
    """
    results: dict[int, list[RawBlock]] = {}

    pages = data.get("pages", [])
    if not isinstance(pages, list):
        logger.warning("LLM response missing 'pages' list — got: %s", type(pages).__name__)
        return results

    for page_data in pages:
        if not isinstance(page_data, dict):
            continue

        try:
            page_num = int(page_data.get("page", 0))
        except (ValueError, TypeError):
            continue
        if not page_num:
            continue

        blocks: list[RawBlock] = []
        for block_data in page_data.get("blocks", []):
            if not isinstance(block_data, dict):
                continue

            device = (block_data.get("device") or "").strip() or None
            pairs = block_data.get("pairs", [])
            if not isinstance(pairs, list) or not pairs:
                continue

            cn_list = [(p.get("cn") or "").strip() for p in pairs if isinstance(p, dict)]
            dt_list = [(p.get("dt_raw") or "").strip() for p in pairs if isinstance(p, dict)]
            variant_list = [(p.get("variant") or "").strip() for p in pairs if isinstance(p, dict)]

            # Skip blocks where all DT values are empty
            if not any(dt_list):
                continue

            blocks.append(RawBlock(
                page=page_num,
                device=device,
                cn_list=cn_list,
                dt_list=dt_list,
                variant_list=variant_list,
                x0=0.0,
                top=0.0,
                source="llm",
                confidence=0.75,
            ))

        results[page_num] = blocks

    return results
