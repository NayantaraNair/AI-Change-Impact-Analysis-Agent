"""Environment loading and shared paths."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env", override=False)

DATA_DIR = Path(os.getenv("DATA_DIR", REPO_ROOT / "data"))
CACHE_DIR = DATA_DIR / "cache"
FIXTURES_DIR = DATA_DIR / "fixtures"
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "app.db"))

ARCHITECTURE_PATH = DATA_DIR / "architecture.json"
TEST_CATALOG_PATH = DATA_DIR / "test_catalog.json"
DEMO_SPRINT_PATH = DATA_DIR / "demo_sprint.json"
DEMO_PORTFOLIO_PATH = DATA_DIR / "demo_portfolio.json"
DEMO_CODEBASE_PATH = DATA_DIR / "demo_codebase.json"

CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]


def tokenharbor_key() -> str | None:
    return os.getenv("TOKENHARBOR_API_KEY") or None


def openrouter_key() -> str | None:
    return os.getenv("OPENROUTER_API_KEY") or None


def llm_disabled() -> bool:
    if os.getenv("LLM_DISABLED", "0").strip().lower() in {"1", "true", "yes"}:
        return True
    return not (tokenharbor_key() or openrouter_key())
