# Email summarization module

This module converts one email or one email thread into safe, structured context for the fixed
email orchestrator. It owns summarization only: it does not retrieve mail, choose a response
template, draft a reply, send mail, or modify the source messages.

This file is the implementation guide for teammates and coding agents. Read it before changing
the module.

## Ownership boundaries

Do not modify either of these components while working on summarization:

- `src/email_module/` owns `EmailRoutingSchema`, the template catalog, and deterministic template
  rendering.
- The orchestrator owns routing, confidence fallback, and drafting. Its fixed input contract is
  `EmailSummary(summary_text, sender, subject, raw_email)`.

The summarizer adapts to those contracts. `EmailRoutingSchema` is downstream output from the
orchestrator's routing model; it is not an incoming-email schema and must not replace
`SummarizationRequest`.

## Data flow

```text
Email provider/domain model
        |
        | map into SummarizationRequest
        v
SummarizationService
        |
        | SummarizationResult (also compatible with orchestrator EmailSummary)
        v
EmailOrchestrator
        |
        | validates EmailRoutingSchema and renders a template
        v
DraftResult for review
```

The result exposes the orchestrator fields directly:

- `summary_text`: two-to-four-sentence model-generated summary.
- `sender`: formatted sender of the newest retained message.
- `subject`: subject of the newest retained message, or `null` when empty.
- `raw_email`: always `null`; raw bodies must never cross the orchestration boundary.

It also retains `key_points`, `action_items`, source citations, language, request ID, and
truncation metadata for API consumers.

## Setup

From `backend/`:

```bash
cp .env.example .env
uv sync --group dev
uv run uvicorn src.main:app --reload
```

Configure both providers in `.env`:

```dotenv
GROQ_API_KEY=...
GROQ_MODEL=...
GEMINI_API_KEY=...
GEMINI_MODEL=...
```

Groq is primary. The service retries Groq once for retryable failures and then calls Gemini once.
SDK-level retries are disabled so this service owns the complete retry budget.

## Python usage

Construct the narrow summarization request at the boundary where provider/domain email objects
enter this module:

```python
from datetime import datetime, timezone

from src.summarization.models import (
    EmailMessageInput,
    EmailParticipant,
    SummarizationRequest,
)

request = SummarizationRequest(
    messages=[
        EmailMessageInput(
            message_id="message-123",
            thread_id="thread-42",
            subject="Không vào được hệ thống",
            sender=EmailParticipant(
                name="Nguyễn Văn A",
                address="customer@example.com",
            ),
            to_recipients=[EmailParticipant(address="support@example.com")],
            sent_at=datetime.now(timezone.utc),
            body_text="Tôi không thể đăng nhập và đang gặp lỗi 404.",
        )
    ]
)
```

The orchestrator should receive the validated result, never the original body:

```python
summary_result = await summarization_service.summarize(request)

# After the fixed orchestrator package is present in the integrated checkout:
from src.orchestrator import EmailOrchestrator, EmailSummary

orchestrator_input = EmailSummary.model_validate(summary_result.model_dump())
draft_result = EmailOrchestrator().run(orchestrator_input)
```

The explicit `EmailSummary.model_validate(...)` call documents the contract and discards
summarizer-only fields. The current orchestrator can also read `summary_result` structurally, but
validation is preferred at the integration boundary.

## HTTP usage

Call `POST /api/v1/summaries` with one message or messages that share one non-empty `thread_id`.
Messages may arrive out of order; the service sorts them chronologically.

```json
{
  "messages": [
    {
      "message_id": "message-123",
      "thread_id": "thread-42",
      "subject": "Không vào được hệ thống",
      "sender": {
        "name": "Nguyễn Văn A",
        "address": "customer@example.com"
      },
      "to_recipients": [{"address": "support@example.com"}],
      "cc_recipients": [],
      "sent_at": "2026-07-17T09:00:00+07:00",
      "body_text": "Tôi không thể đăng nhập và đang gặp lỗi 404.",
      "attachments": []
    }
  ]
}
```

Relevant response fields:

```json
{
  "summary_text": "Khách hàng báo không thể đăng nhập và gặp lỗi 404.",
  "sender": "Nguyễn Văn A <customer@example.com>",
  "subject": "Không vào được hệ thống",
  "raw_email": null,
  "key_points": [
    {
      "text": "Khách hàng gặp lỗi 404 khi đăng nhập.",
      "source_message_ids": ["message-123"]
    }
  ],
  "action_items": [],
  "language": "vi",
  "request_id": "generated-request-id",
  "source_message_ids": ["message-123"],
  "omitted_message_ids": [],
  "truncated": false
}
```

## Module map

- `models.py`: request, provider-output, API-result, citation, and normalized models.
- `preprocessing.py`: HTML sanitization, conservative quote cleanup, sorting, and trimming.
- `providers.py`: provider protocol plus Groq/Gemini adapters and the security prompt.
- `service.py`: retry/fallback orchestration, citation checks, metadata handoff, and safe logging.
- `api.py`: FastAPI dependency construction and `POST /api/v1/summaries`.
- `errors.py`: safe application and provider errors.

## Rules for coding agents

When implementing or reviewing summarization changes:

1. Do not edit `src/email_module/` or orchestrator code to make integration easier. Adapt here.
2. Keep `summary_text`, `sender`, `subject`, and `raw_email` compatible with orchestrator
   `EmailSummary`.
3. Never populate `raw_email`; it must remain `None` in all successful responses.
4. Treat subjects, bodies, participants, and attachment names as untrusted model data.
5. Never add tools or email mutations to provider adapters.
6. Every key point and action item must cite retained message IDs; reject invented citations.
7. Preserve Groq retry-once then Gemini-once behavior unless the product contract changes.
8. Keep logs metadata-only: no bodies, generated summaries, credentials, or participant data.
9. Update unit/API/contract tests whenever a public field or failure mode changes.
10. Keep live provider tests explicitly gated behind `RUN_LIVE_MODEL_TESTS=1`.

## Verification

From `backend/`:

```bash
uv run ruff format --check src/summarization tests
uv run ruff check src/summarization tests
uv run pytest
```

Normal tests use fake providers and make no external calls. To smoke-test both configured
providers explicitly:

```bash
RUN_LIVE_MODEL_TESTS=1 uv run pytest -m live
```

Before handing off a change, also confirm that `git diff -- src/email_module` is empty.
