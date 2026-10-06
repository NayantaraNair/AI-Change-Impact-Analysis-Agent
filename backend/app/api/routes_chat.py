"""Chat endpoint for the context-grounded analysis copilot."""

from fastapi import APIRouter

from app.agents.chat import answer
from app.contracts import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    return await answer(request)
