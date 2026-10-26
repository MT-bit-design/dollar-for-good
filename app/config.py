"""Settings, key loading, and the model. The model name lives here and nowhere else."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
WEB_DIR = ROOT / "web"
USAGE_LOG = OUTPUT_DIR / "usage.jsonl"
AGENT_CACHE = OUTPUT_DIR / "agent_cache.json"

KEY_NAME = "PORTKEY_API_KEY"


def env_files(root: Path = ROOT) -> list[Path]:
    """Where .env is looked for, in order: this repo's folder, then the folder above it."""
    return [root / ".env", root.parent / ".env"]


def load_env(root: Path = ROOT) -> Path | None:
    """Load the first .env that exists. Never overrides a variable that is already set.

    Returns the file that was used (or None). Never returns or prints the key itself.
    """
    for f in env_files(root):
        if f.is_file():
            load_dotenv(f, override=False)
            return f
    return None


ENV_FILE_USED = load_env()
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

# Course key only: gpt-6-luna through Portkey.
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Price per 1M tokens (USD), used only for the cost display: OpenAI's published list prices
# for gpt-6-luna, standard tier, prompts up to 272K tokens. Sources (accessed 2026-10-26):
#   OpenAI API pricing   https://developers.openai.com/api/docs/pricing
#   eesel.ai             https://www.eesel.ai/blog/gpt-6-luna-pricing
#   AnotherWrapper       https://anotherwrapper.com/llm-pricing/gpt-6-luna  (input and output only)
# The course key is billed through Portkey, so its actual billing may differ.
PRICE_SOURCE = "OpenAI's published list prices for GPT-6 Luna (accessed 2026-10-26)"
PRICE_PER_M_INPUT = float(os.getenv("PRICE_PER_M_INPUT", "0.10"))
PRICE_PER_M_CACHED_INPUT = float(os.getenv("PRICE_PER_M_CACHED_INPUT", "0.01"))
PRICE_PER_M_OUTPUT = float(os.getenv("PRICE_PER_M_OUTPUT", "0.50"))

# Guards so nothing loops forever or burns the budget.
MAX_OUTPUT_TOKENS = 3_000          # per model reply, reasoning included
REASONING_EFFORT = "low"
RUN_REQUEST_LIMIT = 6               # model calls per charity
RUN_TOOL_CALL_LIMIT = 4             # page fetches per charity
RUN_TOTAL_TOKEN_LIMIT = 60_000      # per charity
DAILY_TOKEN_BUDGET = int(os.getenv("DAILY_TOKEN_BUDGET", "1000000"))
MAX_PORTFOLIO_ROWS = 25             # rows per upload
MAX_AGENT_ROWS_PER_UPLOAD = 10      # rows per upload that may call the agent

# Page fetching.
FETCH_TIMEOUT_S = 15
FETCH_MAX_BYTES = 2_000_000
PAGE_TEXT_LIMIT = 12_000            # characters of page text the model sees per fetch


class MissingApiKey(RuntimeError):
    """PORTKEY_API_KEY is not set."""


def api_key() -> str:
    key = os.getenv(KEY_NAME, "").strip()
    if not key or key.lower().startswith("your"):
        raise MissingApiKey(
            f"{KEY_NAME} is not set. Put it in .env in this folder or the folder above it.")
    return key


def has_api_key() -> bool:
    try:
        api_key()
        return True
    except MissingApiKey:
        return False


def build_model():
    """gpt-6-luna via Portkey, Responses API (as in the course setup)."""
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider

    key = api_key()
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=key,
                         default_headers={"x-portkey-api-key": key},
                         timeout=120, max_retries=1)
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def model_settings():
    from pydantic_ai.models.openai import OpenAIResponsesModelSettings
    return OpenAIResponsesModelSettings(max_tokens=MAX_OUTPUT_TOKENS,
                                        openai_reasoning_effort=REASONING_EFFORT)
