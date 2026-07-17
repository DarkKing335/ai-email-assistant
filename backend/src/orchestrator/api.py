from functools import lru_cache

from fastapi import APIRouter

from src.orchestrator.contracts import DraftResult
from src.orchestrator.orchestrator import EmailOrchestrator
from src.summarization.models import SummarizationResult

router = APIRouter(prefix="/api/v1/drafts", tags=["orchestrator"])


@lru_cache
def _get_orchestrator() -> EmailOrchestrator:
    return EmailOrchestrator()


# Sync `def`: EmailOrchestrator.run() makes blocking LLM calls, so FastAPI runs it
# in a threadpool instead of blocking the event loop.
@router.post("", response_model=DraftResult)
def create_draft(summary: SummarizationResult) -> DraftResult:
    """Route a summarizer result to a template and produce a draft reply."""
    return _get_orchestrator().run(summary)
