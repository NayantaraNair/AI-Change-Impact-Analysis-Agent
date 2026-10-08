"""FastAPI application and startup data loading."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config, db
from app.api import routes_analysis, routes_chat, routes_runs, routes_sprint
from app.architecture import get_architecture, get_test_catalog

# Provider, model and latency per LLM call (app.llm never logs keys or prompts).
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.architecture = get_architecture()
    app.state.test_catalog = get_test_catalog()
    db.init_db()
    yield


app = FastAPI(title="ImpactIQ API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(routes_analysis.router)
app.include_router(routes_sprint.router)
app.include_router(routes_chat.router)
app.include_router(routes_runs.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "providers_configured": {
            "tokenharbor": bool(config.tokenharbor_key()),
            "openrouter": bool(config.openrouter_key()),
        },
        "llm_disabled": config.llm_disabled(),
    }
