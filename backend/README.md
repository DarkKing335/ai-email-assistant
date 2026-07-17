# Email summarization backend

The summarization component accepts a normalized email or thread and returns provider-neutral,
source-cited context for the drafting pipeline. It uses Groq as the primary model provider and
Gemini as a one-call fallback. It never retrieves, changes, sends, or stores email.

## Run locally

```bash
cd backend
cp .env.example .env
# Add both API keys and model identifiers to .env.
uv sync --group dev
uv run uvicorn src.main:app --reload
```

OpenAPI documentation is available at `http://127.0.0.1:8000/docs` and health status at
`GET /health`.

## API contract

Call `POST /api/v1/summaries` with one message or multiple messages sharing a non-empty
`thread_id`. For example:

```json
{
  "messages": [
    {
      "message_id": "message-123",
      "thread_id": "thread-42",
      "subject": "Quarterly report",
      "sender": {"name": "Alice", "address": "alice@example.com"},
      "to_recipients": [{"address": "bob@example.com"}],
      "cc_recipients": [],
      "sent_at": "2026-07-15T09:00:00+07:00",
      "body_text": "Please send the report by Friday.",
      "attachments": []
    }
  ]
}
```

The response contains compact `summary_text`, at most seven cited key points, cited action items,
the detected language, and explicit processed/omitted message IDs. The reusable
`SummarizationService` exposes the same contract directly to the future drafting component.

For the complete module contract, orchestration handoff, and AI-agent implementation rules,
read [`src/summarization/README.md`](src/summarization/README.md).

## Test

```bash
cd backend
uv run pytest
```

Automated tests use fake model providers and never make external API calls.

To run the explicitly gated provider smoke test after configuring `.env`:

```bash
RUN_LIVE_MODEL_TESTS=1 uv run pytest -m live
```
