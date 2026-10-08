# ImpactIQ: Every Change Before It Happens

Banking change-impact analysis: paste a story or change request, get its blast radius, 6-dimension risk scores, a test plan, a compliance check and a release decision. Sprint mode adds conflict detection between stories. A copilot drawer answers questions about the current analysis.

## Stack

- Backend: Python 3.12 (uv), FastAPI, Pydantic v2, NetworkX, SQLite (sqlmodel), `openai` SDK against OpenAI-compatible providers.
- Frontend: Next.js (App Router, TypeScript), Tailwind v4, shadcn/ui, lucide-react, @xyflow/react, recharts.
- Infra: docker compose (backend :8000, frontend :3000).

## Commands

- `cd backend && uv run uvicorn app.api.main:app --reload --port 8000`
- `cd backend && uv run pytest -q`
- `cd frontend && npm run dev`
- `cd frontend && npm run build`
- `cd frontend && npm run lint`
- `docker compose up --build`

## Rules

- **The LLM extracts facts; code computes all scores.** Every score and decision is deterministic Python over the extracted facts and `data/architecture.json`. LLM output is only categorical facts and human-readable text.
- **Never edit `backend/app/contracts.py` or `frontend/lib/types.ts`.** Ask the orchestrator for contract changes.
- Only edit the paths your task owns.
- No real LLM calls in tests. Use `LLM_DISABLED=1` or mock `app.llm.complete_structured` / `complete_text`.
- Every LLM-backed stage has a deterministic fallback for `NoLLM`.
- Never print, log or commit API keys. Never read `.env`.
- Do not install packages; list what you need in your final message.
- Frontend work follows `DESIGN.md` exactly (tokens, type scale, forbidden patterns).
