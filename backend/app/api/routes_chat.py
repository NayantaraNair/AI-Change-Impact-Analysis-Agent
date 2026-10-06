"""Chat route contract stand-in; T13 supplies the copilot implementation."""

from fastapi import APIRouter

from app.contracts import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(
        answer="Copilot is not wired yet.", cited_nodes=[], cited_factors=[], provider="none",
    )
