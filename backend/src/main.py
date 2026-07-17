import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.orchestrator.api import router as orchestrator_router
from src.orchestrator.llm_client import LLMRoutingError
from src.summarization.api import router as summarization_router
from src.summarization.errors import SummarizationError
from src.summarization.models import ErrorResponse

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AI Email Assistant", version="0.1.0")
app.include_router(summarization_router)
app.include_router(orchestrator_router)


@app.middleware("http")
async def assign_request_id(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(SummarizationError)
async def summarization_error_handler(request: Request, exc: SummarizationError) -> JSONResponse:
    payload = ErrorResponse(
        request_id=request.state.request_id,
        code=exc.code,
        message=exc.safe_message,
        retryable=exc.retryable,
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, _exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default validation body can echo invalid input, including email text.
    payload = ErrorResponse(
        request_id=request.state.request_id,
        code="invalid_request",
        message="The summarization request is invalid.",
        retryable=False,
    )
    return JSONResponse(status_code=422, content=payload.model_dump())


@app.exception_handler(LLMRoutingError)
async def llm_routing_error_handler(request: Request, _exc: LLMRoutingError) -> JSONResponse:
    # All routing providers failed; don't leak provider error details to the caller.
    payload = ErrorResponse(
        request_id=request.state.request_id,
        code="routing_unavailable",
        message="Unable to route the email right now. Please try again later.",
        retryable=True,
    )
    return JSONResponse(status_code=502, content=payload.model_dump())


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
