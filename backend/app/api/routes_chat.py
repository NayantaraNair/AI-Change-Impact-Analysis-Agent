"""Chat endpoint for the context-grounded analysis copilot."""

from fastapi import APIRouter

from app import runs
from app.agents.chat import answer
from app.contracts import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    # Tracked inline so copilot model calls show in the debug pane's run history.
    with runs.tracked("chat", request.message[:80], [], [(None, "answer")]):
        with runs.stage("answer", story_id=None) as item:
            response = await answer(request)
            runs.describe(item, response.provider, f"Cited {len(response.cited_nodes)} components")
    return response
