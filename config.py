"""Central config: models, keys, judge mode.

JUDGE_MODE=dev   -> judge on DeepSeek (cheap iteration; directional only)
JUDGE_MODE=final -> judge on gpt-5.4-mini (official; goes in the report)
Wrapper brain is ALWAYS DeepSeek (different family from the final judge).
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

JUDGE_MODE = os.getenv("JUDGE_MODE", "dev")  # "dev" | "final"

# --- API keys ---
OPENFUNNEL_API_KEY = os.getenv("OPENFUNNEL_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- endpoints ---
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENFUNNEL_BASE_URL = "https://api.openfunnel.dev"  # confirm exact host in docs.openfunnel.dev

# --- models ---
# NOTE: deepseek-chat alias is deprecated 2026-07-24 -> use explicit v4 names.
WRAPPER_FAST_MODEL = "deepseek-v4-flash"   # stage 3 roles, stage 4 rerank
WRAPPER_SMART_MODEL = "deepseek-v4-pro"    # stage 0 facet check (7 calls total)
DEV_JUDGE_MODEL = "deepseek-v4-flash"      # iteration only, never in report
FINAL_JUDGE_MODEL = "gpt-5.4-mini"         # the official benchmark judge


@dataclass
class JudgeConfig:
    model: str
    base_url: str
    api_key: str
    label: str


def judge_config() -> JudgeConfig:
    if JUDGE_MODE == "final":
        return JudgeConfig(FINAL_JUDGE_MODEL, OPENAI_BASE_URL, OPENAI_API_KEY, "final")
    return JudgeConfig(DEV_JUDGE_MODEL, DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, "dev")


# --- pipeline knobs ---
OVERFETCH_K = 250          # candidates fetched per query (benchmark grades top 100)
FINAL_K = 100
ROLE_BATCH_SIZE = 20       # candidates per classifier call
RERANK_BATCH_SIZE = 20
CONCURRENCY = 8            # parallel LLM calls
TEMPERATURE = 0.0

# --- the 7 weak seeds, published Precision@100 for reference ---
WEAK_SEEDS = {
    "veeva": 54.0,
    "shopify": 68.0,
    "hubspot": 67.0,
    "roto-rooter": 74.0,
    "nubank": 35.0,
    "siemens": 16.0,
    "sea-shopee": 10.0,
}

DATASET = "lookalike-2026-q2-expanded"
BENCH_RAW_BASE = (
    "https://raw.githubusercontent.com/openbenchmarks-labs/lookalikes/main/"
    f"data/lookalike-runs/{DATASET}"
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
RUNS_DIR = os.path.join(os.path.dirname(__file__), "runs")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
