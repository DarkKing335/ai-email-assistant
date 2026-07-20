import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.database import close_db, init_db
from src.orchestrator.api import router as orchestrator_router
from src.orchestrator.llm_client import LLMRoutingError
from src.summarization.api import router as summarization_router
from src.summarization.errors import SummarizationError
from src.summarization.models import ErrorResponse

# AutoReply routers
from src.auto_reply.api.dashboard_router import router as dashboard_router
from src.auto_reply.api.draft_router import router as draft_router
from src.auto_reply.api.gmail_auth_router import router as gmail_auth_router
from src.auto_reply.api.gmail_router import router as gmail_router
from src.auto_reply.api.inbox_router import router as inbox_router
from src.auto_reply.api.log_router import router as log_router
from src.auto_reply.api.whitelist_router import router as whitelist_router
from src.auto_reply.workflow.background_worker import start_workers, stop_workers

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await start_workers()
    yield
    # Shutdown
    await stop_workers()
    await close_db()


app = FastAPI(title="AI Email Assistant", version="0.2.0", lifespan=lifespan)

# Existing routers
app.include_router(summarization_router)
app.include_router(orchestrator_router)

# AutoReply routers
app.include_router(whitelist_router)
app.include_router(draft_router)
app.include_router(log_router)
app.include_router(inbox_router)
app.include_router(dashboard_router)
app.include_router(gmail_router)
app.include_router(gmail_auth_router)


@app.middleware("http")
async def assign_request_id(request: Request, call_next):
    request.state.request_id = str(uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


# Registered last so it wraps the request-id middleware: preflight OPTIONS are
# answered here and never reach the app.
#
# Unpacked extensions get a new origin (chrome-extension://<id>) on every reload,
# so the origin can't be pinned during development. There is no auth and no
# cookie to protect, and browsers reject "*" together with credentials — hence
# allow_credentials=False. Tighten both before this is ever deployed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],  # otherwise the browser hides it from JS
)


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
