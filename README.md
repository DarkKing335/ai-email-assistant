# 📧 AI Email Assistant

> Reads your inbox, summarises what matters, and leaves a reply waiting in Gmail as a draft.

A Chrome side-panel extension over a FastAPI backend. The backend polls Gmail,
summarises each message from a sender you have whitelisted, generates a reply,
and files it as a **real Gmail draft**. Nothing is ever sent — you open the
thread, read the draft, and decide.

---

## How it works

```
Gmail ──poll──▶ whitelist ──match──▶ summarise ──▶ route to template ──▶ draft
                    │                    (LLM)          (LLM)             │
                    └── no match ──▶ logged as "skipped", nothing else     │
                                                                          ▼
                                                          filed in Gmail as a draft
                                                          shown in the side panel
```

Each whitelisted email costs **two LLM calls** — one to summarise, one to pick a
reply template. Senders that match no rule cost nothing.

Once you reply on a thread, the email retires from the Inbox view automatically.
The backend notices by scanning your sent mail, so replies you typed by hand
count too.

**The extension holds no Google credentials and requests no Gmail permissions.**
Consent is granted to the *backend*, which is the only thing that touches Gmail.
The panel just displays what the backend found.

---

## Repository layout

```
backend/        FastAPI service — polling, LLM pipeline, SQLite storage
  src/
    auto_reply/   whitelist, workflow, Gmail proxy, REST API
    summarization/ provider-neutral summariser (Groq → Gemini fallback)
    orchestrator/  template routing and draft text generation
frontend/       Chrome MV3 extension (React + Vite + Tailwind)
  src/
    sidepanel/    the product — React root and app shell
    background/   service worker: alarms, badge, notifications
    content/      Gmail page only; reads the open thread's sender
docs/           setup and architecture notes
```

---

## Prerequisites

| | Version | Notes |
|---|---|---|
| Python | ≥ 3.12 | |
| [uv](https://docs.astral.sh/uv/) | latest | Manages the Python env and lockfile |
| Node | **18.17.1** | Three frontend packages are pinned to this — see [frontend/README.md](frontend/README.md) before upgrading |
| Chrome | ≥ 114 | `chrome.sidePanel` requires it |
| Groq API key | free | <https://console.groq.com> |
| Google Cloud project | free | For Gmail OAuth |

---

## Setup

Three parts, in this order. The backend must be running and connected to Gmail
before the extension shows anything.

### 1. Backend

```bash
cd backend
cp .env.example .env
uv sync --group dev
```

Edit `.env` and set at minimum:

```ini
GROQ_API_KEY=gsk_your_key
GROQ_MODEL=llama-3.3-70b-versatile
```

> Without a working LLM key every whitelisted email fails before producing
> anything. `GEMINI_API_KEY` is an optional fallback.

Run it:

```bash
uv run uvicorn src.main:app --reload
```

**Keep it on port 8000.** The OAuth redirect URI is registered against
`http://localhost:8000/...`, and a different port breaks the Google callback.

Check it is alive:

- <http://127.0.0.1:8000/health> → `{"status":"ok"}`
- <http://127.0.0.1:8000/docs> → interactive API docs

The database (`backend/email_assistant.db`) is created on first start. No
migration command is needed for local development — missing columns are added
at startup.

### 2. Connect Gmail (OAuth)

**Full walkthrough: [docs/setup/gmail-oauth.md](docs/setup/gmail-oauth.md)** —
roughly 10 minutes, most of it in Google's console. It also has a troubleshooting
table covering every error we have actually hit.

The short version:

1. Create a Google Cloud project, then **enable the Gmail API** (skipping this
   makes consent succeed and every later call fail with an unexplained 403).
2. Configure the **OAuth consent screen** as **External**, add these scopes:
   ```
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/gmail.compose
   https://www.googleapis.com/auth/userinfo.email
   ```
3. Add **your own Gmail address under Test users**. Leave publishing status as
   **Testing** — this is the step people miss.
4. Create an OAuth client of type **Web application** (*not* Desktop app — Google
   blocks the loopback flow Desktop clients use). Authorised redirect URI, exactly:
   ```
   http://localhost:8000/api/v1/gmail/auth/callback
   ```
5. Add the credentials to `backend/.env` and **restart the backend**:
   ```ini
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   ```

You will connect the account from the extension in the next step. The
"unverified app" warning on the consent screen is expected in Testing mode —
**Advanced → Go to AI Email Assistant (unsafe)**.

### 3. Frontend (extension)

```bash
cd frontend
npm install
npm run dev          # writes dist/ and watches for changes
```

Load it into Chrome:

1. Open `chrome://extensions` and enable **Developer mode**
2. **Load unpacked** → select `frontend/dist`
3. Open <https://mail.google.com> and click the toolbar icon

`npm run build` produces the same `dist/` without the watcher.
`npm run typecheck` runs `tsc` alone.

Then, in the side panel: **⚙ Settings → Connect Gmail**, and complete the
consent flow that opens in a new tab.

---

## Verify it end to end

1. Panel shows **Connected** with your address under ⚙ Settings.
2. Go to the **Whitelist** tab and add your own email address.
3. Send yourself an email from that address.
4. Wait one poll interval (60s by default).
5. The **Inbox** tab shows the email with a summary, and Gmail has a draft reply
   on that thread.

If the Inbox stays empty, the sender almost certainly is not whitelisted — check
the **Logs** tab, where skipped mail is recorded with the reason.

---

## Configuration worth knowing

Set in `backend/.env`. Full list with defaults in `backend/src/config.py`.

| Variable | Default | Notes |
|---|---|---|
| `GROQ_API_KEY` | — | Required. Primary LLM. |
| `GEMINI_API_KEY` | — | Optional fallback if Groq fails. |
| `GOOGLE_CLIENT_ID` / `_SECRET` | — | Required for Gmail. Not in `.env.example` — add them by hand. |
| `GMAIL_POLL_INTERVAL_SECONDS` | `60` | Spends Gmail API quota. |
| `GMAIL_POLL_QUERY` | `in:inbox -in:chats` | Any Gmail search expression. |
| `GMAIL_INITIAL_LOOKBACK_MINUTES` | `60` | How far back the *first* poll looks, so connecting does not process a month of history. |
| `GMAIL_MAX_RESULTS_PER_POLL` | `25` | Stops a backlog stampeding the pipeline. |
| `CONFIDENCE_THRESHOLD` | `0.6` | Below this, routing degrades to a safe generic template. |

A free-tier Groq key will hit rate limits on a busy inbox. Keep the whitelist
narrow while testing.

---

## API

Interactive docs at `/docs` while the backend runs.

| Method | Path |
|---|---|
| `GET` | `/health` |
| `GET` | `/api/v1/auto-reply/inbox` |
| `GET` | `/api/v1/auto-reply/logs` |
| `GET` | `/api/v1/auto-reply/logs/{log_id}/drafts` |
| `GET` | `/api/v1/auto-reply/dashboard/summary` |
| `GET`/`POST` | `/api/v1/whitelist` |
| `GET`/`PUT`/`DELETE` | `/api/v1/whitelist/{entry_id}` |
| `POST` | `/api/v1/whitelist/import` |
| `GET` | `/api/v1/gmail/auth/status` · `/start` · `/callback` |
| `DELETE` | `/api/v1/gmail/auth/` |
| `POST` | `/api/v1/summaries` · `/api/v1/drafts` |

---

## Tests

```bash
cd backend
uv run pytest tests/auto_reply tests/test_models.py
```

Tests use fake model providers and never call an external API. The gated live
provider check needs real keys:

```bash
RUN_LIVE_MODEL_TESTS=1 uv run pytest -m live
```

> **Known issue:** `uv run pytest` over the whole suite fails to *collect*
> `tests/test_api.py` and `tests/test_service.py` — two `conftest.py` files
> collide on module name. Run the paths above until that is untangled.

---

## Security — read before deploying

This is built to run on `localhost`. Two things make it unsafe anywhere else:

- **Every API endpoint is unauthenticated.** Anyone who can reach the URL can
  read every stored summary, edit the whitelist, or disconnect the account.
- **The Gmail refresh token is stored in plaintext** in `email_assistant.db`. It
  grants continuing access to your mailbox until revoked. Treat that file as a
  secret — it is already gitignored.

CORS is `allow_origins=["*"]` because unpacked extensions get a new origin on
every reload. Tighten it before any deployment.

Revoke access at any time, independently of this app:
<https://myaccount.google.com/permissions>

---

## Further reading

| Document | Contents |
|---|---|
| [docs/setup/gmail-oauth.md](docs/setup/gmail-oauth.md) | Full OAuth walkthrough + troubleshooting table |
| [frontend/README.md](frontend/README.md) | Extension layout, Node version pins, MV3 constraints |
| [backend/README.md](backend/README.md) | Summarization service contract |
| [docs/architecture/frontend-plan.md](docs/architecture/frontend-plan.md) | Panel design and build order |
