import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
CUAD_DIR = DATA_DIR / "raw" / "cuad" / "CUAD_v1"

DATABASE_URL = (
    f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
    f"@localhost:{os.environ.get('POSTGRES_PORT', '5432')}/{os.environ['POSTGRES_DB']}"
)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# The router uses the light model; answers, SQL and the evaluation judge use the main one.
# Newer Flash releases are often overloaded (HTTP 503) on the free tier; 2.5 Flash is stable and fast.
# (2.5 Flash-Lite is closed to new accounts, so the router uses 3.5 Flash-Lite.)
GEMINI_FAST_MODEL = os.environ.get("GEMINI_FAST_MODEL", "gemini-3.5-flash-lite")
GEMINI_MAIN_MODEL = os.environ.get("GEMINI_MAIN_MODEL", "gemini-2.5-flash")
# Tried in order when a model is overloaded or out of free-tier quota (quotas are per model).
GEMINI_FALLBACK_MODELS = os.environ.get(
    "GEMINI_FALLBACK_MODELS", "gemini-3-flash-preview,gemini-3.5-flash-lite,gemini-3.6-flash"
).split(",")

EMBED_MODEL = "BAAI/bge-m3"
EMBED_DIM = 1024
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"

# The contract types we treat as supply chain (CUAD folder names contain these).
SUPPLY_CHAIN_TYPES = ["Supply", "Distributor", "Manufacturing", "Transportation", "Outsourcing"]
