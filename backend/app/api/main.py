"""FastAPI application and startup data loading."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config, db
from app.api import routes_analysis, routes_chat, routes_sprint
from app.architecture import get_architecture, get_test_catalog


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.architecture = get_architecture()
    app.state.test_catalog = get_test_catalog()
    db.init_db()
    yield


app = FastAPI(title="Change Impact Copilot API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(routes_analysis.router)
app.include_router(routes_sprint.router)
app.include_router(routes_chat.router)


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
