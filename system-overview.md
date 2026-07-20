# AI Email Assistant — System Overview

> **Version:** MVP (backend `0.2.0`)
> **Last updated:** 2026-07-20
> **Audience:** end users *and* developers — see the reading guide below.

---

## How to read this document

This document is written for two different readers. Nothing is duplicated; each
section is simply labelled with who it is for.

| If you are… | Read these sections |
|---|---|
| **A user** (you want to use the product) | [1. System Overview](#1-system-overview) · [2. Product Vision](#2-product-vision) · [3. MVP Scope](#3-mvp-scope) · [6. Feature Specifications](#6-feature-specifications) · [8. User Flows](#8-user-flows) · [10. Limitations](#10-limitations) · [12. Glossary](#12-glossary) |
| **A developer** (you want to build on it) | Everything, but especially [4. System Architecture](#4-system-architecture) · [5. Module Breakdown](#5-module-breakdown) · [7. User Stories](#7-user-stories) · [9. Technical Notes](#9-technical-notes) · [11. Future Improvements](#11-future-improvements) |

Sections marked **👤 User** describe what a person sees and does.
Sections marked **🛠 Developer** describe how the system is built.

---

## Table of contents

1. [System Overview](#1-system-overview)
2. [Product Vision](#2-product-vision)
3. [MVP Scope](#3-mvp-scope)
4. [System Architecture](#4-system-architecture)
5. [Module Breakdown](#5-module-breakdown)
6. [Feature Specifications](#6-feature-specifications)
7. [User Stories](#7-user-stories)
8. [User Flows](#8-user-flows)
9. [Technical Notes](#9-technical-notes)
10. [Limitations](#10-limitations)
11. [Future Improvements](#11-future-improvements)
12. [Glossary](#12-glossary)

---

# 1. System Overview

## 👤 In one paragraph

**AI Email Assistant watches your Gmail inbox for mail from people you have
explicitly listed, reads each of those emails for you, and leaves a reply
waiting in Gmail as a draft.** Nothing is ever sent. You open the thread, read
what was written, edit it if you want, and press Send yourself — or delete it.
The product is a sidebar that lives next to Gmail in Chrome.

## 👤 What it is not

- It is **not** a chatbot. There is no conversation box.
- It does **not** send email. Ever. It only creates drafts.
- It does **not** touch mail from senders you have not listed. Those are
  recorded as *skipped* and cost nothing.

## 🛠 In one paragraph

A Chrome Manifest V3 side-panel extension (React + TypeScript + Vite) rendering
data from a local FastAPI backend (Python 3.12, SQLAlchemy async, SQLite). The
backend owns Google OAuth, polls the Gmail API on an interval, matches each
inbound sender against a whitelist, runs a two-stage LLM pipeline
(summarize → route + draft), persists the result, and files the reply through
`gmail.drafts.create`. The extension holds **no** Google credentials and
requests **no** Gmail permissions; it is a view over the backend's database.

## The one-line pipeline

```
Gmail ──poll──▶ whitelist ──match──▶ summarise ──▶ route ──▶ draft ──▶ file in Gmail
                    │                  (LLM)      (LLM)     (LLM)          │
                    └── no match ──▶ logged as "skipped", nothing else     ▼
                                                              shown in the side panel
```

---

# 2. Product Vision

## The problem

A working inbox contains a small number of messages that genuinely need a reply,
buried in a large number that do not. Two costs follow:

1. **Reading cost.** You re-read long threads to recover what is being asked.
2. **Starting cost.** Even a known reply is easier to edit than to begin.

Existing "AI email" tools mostly attack this by putting a chat window next to
your mail, which means you still do the work — you just do it in two places.

## The product bet

> **The assistant should have already done the work by the time you look.**

Not "ask me to summarise this." Instead: by the time you open the thread, the
summary exists and a draft reply is sitting in Gmail's own draft box, threaded
under the conversation, waiting for your judgement.

## Principles

| Principle | What it means in this system |
|---|---|
| **Never send** | The system's terminal action is `drafts.create`. There is no send path anywhere in the codebase. The `gmail.compose` scope permits drafting, not sending on your behalf. |
| **Opt in, per sender** | Nothing is processed unless its sender matches a whitelist rule you created. Silence is the default. |
| **The user's mailbox is the source of truth** | The draft lives in Gmail, not in our UI. Edit it where you will send it. |
| **Credentials live in one place** | Only the backend holds Google tokens. The extension can be reloaded, reinstalled or uninstalled without touching your Google account. |
| **Explain, don't just act** | Every processed email carries its summary, the template chosen, the provider used, and whether confidence was low. Every skipped email carries its reason. |
| **Degrade, don't fail** | A failing LLM falls back to a second provider, then to a static template. A failing Gmail call still leaves the generated text stored. |

## Who it is for (MVP)

A **single person**, running the backend on their own machine, connecting
**one** Gmail account, using Chrome. This is a demo/self-hosted product, not a
multi-tenant service — see [10. Limitations](#10-limitations).

---

# 3. MVP Scope

## 👤 What works today

| Capability | Status |
|---|---|
| Connect one Gmail account by OAuth | ✅ |
| Automatically poll for new mail (default: every 60s) | ✅ |
| Whitelist by exact email address or whole domain | ✅ |
| Add / edit / remove whitelist rules | ✅ |
| Quick-add the sender of the thread open in Gmail | ✅ |
| Bulk import whitelist from CSV or Excel | ✅ |
| AI summary: overview, key points, action items, language | ✅ |
| AI-written draft reply, in the language of the incoming mail | ✅ |
| Draft filed in Gmail, threaded under the original conversation | ✅ |
| Re-examine skipped mail after adding a rule ("Rescan") | ✅ |
| Emails you have replied to retire from the Inbox view | ✅ |
| Activity log with skip / failure reasons | ✅ |
| Dashboard: volume, matched vs unmatched, failures, top senders | ✅ |
| Badge count + desktop notification while the panel is closed | ✅ |
| Configure backend URL, background interval, notifications | ✅ |

## 👤 What is deliberately **not** in the MVP

| Not included | Why |
|---|---|
| **Sending email** | Out of scope by design, not by omission. |
| **Multiple Gmail accounts** | `oauth_credentials.provider` is unique — connecting a second account replaces the first. |
| **Multiple users / login** | The backend has no authentication at all. It is a localhost tool. |
| **Regenerating a draft on demand** | The database supports draft versions; no endpoint or button exposes it. |
| **Editing the draft inside the panel** | The draft lives in Gmail; a second editable copy would invite editing the one that never gets sent. |
| **"Summarise everything, reply to some"** | The whitelist currently means both. One list, one meaning. |
| **Custom reply templates** | Three fixed templates: `TECH_SUPPORT`, `PRICING_INQUIRY`, `GENERAL_GREETING`. |
| **Attachment understanding** | Attachment metadata is carried; content is never analysed. |
| **Deployment beyond localhost** | See the security notes in [10. Limitations](#10-limitations). |

## 🛠 MVP boundary conditions

- **One backend process.** The whitelist match cache is per-process; running
  `uvicorn --workers 2` makes caches diverge for up to 60 seconds.
- **One background worker task.** A single asyncio loop drains retries, rescans
  and inbound mail in that order.
- **SQLite.** `email_assistant.db` in `backend/`. Alembic migrations exist;
  local dev also auto-creates tables at startup.
- **Chrome 114+.** `chrome.sidePanel` requires it.

---

# 4. System Architecture

## 🛠 Component diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│  CHROME EXTENSION (Manifest V3)                                      │
│  Holds no Google credentials. Requests no Gmail permissions.         │
│                                                                      │
│  ┌───────────────┐   ┌────────────────┐   ┌──────────────────────┐   │
│  │ Content       │   │ Service Worker │   │ Side Panel (React)   │   │
│  │ Script        │   │                │   │                      │   │
│  │ mail.google   │   │ chrome.alarms  │   │ Inbox                │   │
│  │  .com only    │   │ badge count    │   │ Dashboard            │   │
│  │               │   │ notifications  │   │ Whitelist            │   │
│  │ reads open    │   │ (fetch only —  │   │ Logs                 │   │
│  │ thread sender │   │  no axios)     │   │ Settings             │   │
│  └───────┬───────┘   └───────┬────────┘   └──────────┬───────────┘   │
│          │ chrome.storage    │                       │               │
│          └───────────────────┴───────────┬───────────┘               │
└──────────────────────────────────────────┼───────────────────────────┘
                                           │ REST + CORS
                                           │ http://localhost:8000
                     ┌─────────────────────▼──────────────────────────┐
                     │  FastAPI BACKEND                               │
                     │                                                │
                     │  API layer   whitelist · inbox · logs ·        │
                     │              dashboard · drafts · gmail-auth   │
                     │  ─────────────────────────────────────────     │
                     │  Workflow    AutoReplyWorkflow                 │
                     │              background worker · retry queue   │
                     │              rescan sweep                      │
                     │  ─────────────────────────────────────────     │
                     │  Tools       matcher · whitelist · bulk import │
                     │              draft store · stats · log query   │
                     │  ─────────────────────────────────────────     │
                     │  AI          SummarizationService              │
                     │              EmailOrchestrator + Drafter       │
                     │  ─────────────────────────────────────────     │
                     │  Proxy       Gmail client · poller · OAuth     │
                     │  ─────────────────────────────────────────     │
                     │  Storage     SQLAlchemy async → SQLite         │
                     └───────┬──────────────────────────┬─────────────┘
                             │ OAuth 2.0                │ HTTPS
                             │ (server-side)            │
                     ┌───────▼─────────┐      ┌─────────▼───────────┐
                     │  GMAIL API      │      │  LLM PROVIDERS      │
                     │  messages.list  │      │  Groq   (primary)   │
                     │  messages.get   │      │  Gemini (fallback)  │
                     │  drafts.create  │      │  mock   (no keys)   │
                     └─────────────────┘      └─────────────────────┘
```

## 🛠 Responsibility split

This is the single most important table in the document. Each row states who
owns a concern, and — just as importantly — who does **not**.

| Concern | Owner | Explicitly *not* |
|---|---|---|
| Google OAuth consent, token storage, token refresh | **Backend** | The extension never sees a token |
| Discovering new mail | **Backend** (polls Gmail) | The extension never calls Gmail's API |
| Deciding whether an email is processed | **Backend** (`MatcherTool`) | The LLM never sees the whitelist |
| Reading and understanding email content | **LLM** (summarization) | The backend does no NLP of its own |
| Choosing a reply template | **LLM** (routing), validated by the backend | The LLM's choice is schema-validated and confidence-gated |
| Writing the reply text | **LLM** (compose), cleaned by the backend | Falls back to a static template on any failure |
| Creating the draft in the mailbox | **Gmail API**, called by the backend | The extension has no `gmail.*` scope |
| Threading the draft under the conversation | **Backend** (sets `threadId` + `In-Reply-To`/`References`) | Gmail will not infer it |
| Detecting that you replied | **Backend** (sweeps sent mail via Gmail API) | Not the extension, and not only for AI-generated replies |
| Rendering everything a human sees | **Chrome Extension** | The backend serves JSON, not HTML (one exception: the OAuth result page) |
| Badge count, desktop notifications | **Chrome Extension** service worker | Backend has no push channel |
| Reading which Gmail thread is on screen | **Chrome Extension** content script | Read-only; it never modifies Gmail's DOM |
| Storing user preferences | **Chrome Extension** (`chrome.storage.local`) | Not the backend — settings are per-device |

## 🛠 Technology stack

**Backend**

| Layer | Choice |
|---|---|
| Language | Python ≥ 3.12 |
| Web framework | FastAPI `0.2.0` app, served by Uvicorn |
| ORM | SQLAlchemy 2.x async + `aiosqlite` |
| Migrations | Alembic (`0001`–`0005`) |
| Config | `pydantic-settings`, single `Settings` object |
| HTTP client | `httpx` (async) for Gmail |
| LLM SDKs | `groq`, `google-genai` |
| Package manager | `uv` |

**Frontend**

| Layer | Choice |
|---|---|
| Language | TypeScript |
| UI | React 19 |
| Build | Vite + `@crxjs/vite-plugin` (MV3 HMR) |
| Styling | TailwindCSS v4 |
| Server state | TanStack Query |
| UI state | Zustand |
| HTTP | `axios` in the panel, plain `fetch` in the service worker |
| Node | pinned to **18.17.1** |

## 🛠 Runtime topology

Three independent clocks run at once. Confusing them is the most common source
of "why hasn't it updated yet".

| Clock | Where | Default | Controls |
|---|---|---|---|
| **Gmail poll** | Backend worker | 60 s (`GMAIL_POLL_INTERVAL_SECONDS`) | How fast new mail is *discovered*. Spends Gmail quota. |
| **Panel refresh** | Side panel, TanStack Query | 30 s | How fast the open panel *shows* what the backend already has. |
| **Background check** | Service worker, `chrome.alarms` | 5 min (floor 1 min) | Badge + notification while the panel is closed. |

Worst-case latency from "mail arrives" to "badge appears" is therefore roughly
one poll interval plus one alarm interval.

---

# 5. Module Breakdown

## 🛠 Backend modules

---

### B1 · Configuration

**Purpose** — One typed, validated source of truth for every tunable value.

**Responsibilities**
- Load `.env` into a `Settings` model with ranges enforced by Pydantic.
- Expose capability flags: `has_groq`, `has_gemini`, `has_google_oauth`.
- Cache the settings object (`@lru_cache`) so no module re-reads the file.

**Features** — Provider keys and models · summarizer tuning · confidence
threshold · database URL · whitelist cache TTL · retry policy · rescan lookback
· bulk import cap · Google OAuth client and scopes · Gmail polling parameters.

**Inputs** — `backend/.env`, process environment.
**Outputs** — `Settings` instance via `get_settings()`.

**Dependencies** — `pydantic-settings`. Depends on nothing else in the project;
everything else depends on it.

**Edge cases**
- Missing Groq key → `has_groq` is False → routing silently uses the **mock**
  keyword router and drafting falls back to static templates. The pipeline still
  completes; the output is much worse. This is intentional (it lets the app run
  with zero keys) and is a common source of confusion.
- `has_groq` requires **both** a key and a model name — there is no default
  model.
- `@lru_cache` means changing `.env` requires a **restart**.

**Future improvements** — Surface capability flags on `/health` so the panel can
warn "no LLM configured" instead of silently producing mock output.

---

### B2 · Persistence

**Purpose** — Durable storage of rules, processing history, drafts and tokens.

**Responsibilities**
- Define the ORM schema and the async session lifecycle.
- Provide repositories that encapsulate every query.

**Features** — Four tables:

| Table | Holds |
|---|---|
| `whitelist_entries` | `entry_type` (email/domain), `value`, `is_active`, audit columns. Unique on `(value, is_active)`. |
| `match_logs` | One row per inbound email ever seen: Gmail ids, sender, subject, matched rule, `status`, `retry_count`, `error_detail`, `processing_ms`, `summary_json`, `received_at`, `processed_at`, `replied_at`. Unique on `gmail_message_id`. |
| `generated_drafts` | Versioned draft text + `template_id`, `confidence_score`, `extracted_data`, `provider_used`, `used_fallback`, `gmail_draft_id`. Unique on `(match_log_id, version)`. |
| `oauth_credentials` | One row: access + refresh token, expiry, granted scopes, `last_polled_at`. Unique on `provider`. |

**Inputs** — ORM operations from tools and the workflow.
**Outputs** — Persisted rows; `AsyncSession` via `get_db()` (request scope) and
`db_session()` (worker scope).

**Dependencies** — B1 (database URL), SQLAlchemy, aiosqlite.

**Edge cases**
- **Soft delete.** Deleting a whitelist rule sets `is_active=False`. Re-adding
  the same value *reactivates the original row* rather than creating a new one —
  "delete then re-add" is not a clean slate.
- `summary_json` is null for rows that were skipped, failed before
  summarization, or predate the feature. Every reader must handle null.
- `replied_at` is deliberately **not** an `ExecutionStatus` value: status records
  how *our processing* ended and must stay meaningful afterwards. Folding "was
  replied to" into the enum would overwrite the outcome and skew the dashboard.
- SQLite returns naive datetimes; the poller re-attaches UTC on read.

**Future improvements** — Encrypt tokens at rest · owner column on every table
for multi-user · index review once volume grows.

---

### B3 · Gmail OAuth

**Purpose** — Obtain and maintain permission to read the mailbox and create
drafts.

**Responsibilities**
- Build the Google authorization URL with a CSRF `state`.
- Exchange the authorization code for tokens; identify the account.
- Refresh the access token on demand; preserve the refresh token (Google only
  returns it on first consent).
- Revoke and delete on disconnect.

**Features** — `GET /api/v1/gmail/auth/start` (307 to Google) ·
`GET …/callback` (renders a human-readable HTML result page, not JSON) ·
`GET …/status` · `DELETE /api/v1/gmail/auth/`.

**Inputs** — `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`,
the code and state returned by Google.
**Outputs** — A persisted `OAuthCredential`; a valid access token on request;
a status object consumed by the Settings panel.

**Scopes requested** — `gmail.readonly` (poll) · `gmail.compose` (draft) ·
`userinfo.email` (name the connected account). Both Gmail scopes are classified
*sensitive* by Google.

**Dependencies** — B1, B2, `httpx`, Google's OAuth endpoints.

**Edge cases**
- OAuth client must be type **Web application**; Google blocks the loopback flow
  Desktop clients use.
- The redirect URI must match *exactly*, including port — which is why the
  backend must stay on **8000**.
- Consent screen in **Testing** mode shows an "unverified app" warning; expected.
- `state` is single-use; a replayed or expired callback renders an explanatory
  error page rather than a stack trace.
- Connecting a second account **replaces** the first (unique `provider`).
- A revoked token surfaces as a 401 during polling, recorded in
  `poller.last_error`.

**Future improvements** — Token encryption · explicit re-consent prompt when
scopes change · support for more than one connected account.

---

### B4 · Gmail Client & Poller

**Purpose** — All I/O with the Gmail API, and the loop that discovers new mail.

**Responsibilities**
- `list_message_ids` / `get_message` / `list_sent_thread_ids` / `create_draft`.
- Parse Gmail's payload into an internal `InboundEmailEvent` (decode base64url
  bodies, walk MIME parts, extract headers, resolve `received_at`).
- Build the reply MIME, including threading headers.
- Poll on an interval, buffer results, advance the watermark, detect replies.

**Features**
- **Interval polling** with an in-memory buffer: the worker calls `receive()` in
  a tight loop, so serving from a buffer is what keeps Gmail quota alive.
- **Watermark** (`last_polled_at`) captured *before* the fetch, so a message
  arriving mid-poll is caught next time rather than lost.
- **First-poll lookback** bounded to `GMAIL_INITIAL_LOOKBACK_MINUTES` (60) so
  connecting an account does not draft replies to a month of history.
- **Reply sweep**: lists sent threads since the watermark and stamps
  `replied_at` on matching logs. Works for hand-typed replies too.
- **Backoff**: retryable failure → 2× interval; non-retryable → 10×; no account
  connected → at least 60 s.

**Inputs** — A valid access token; `GMAIL_POLL_QUERY` (default
`in:inbox -in:chats`); `GMAIL_MAX_RESULTS_PER_POLL` (25).
**Outputs** — `InboundEmailEvent` objects; a created draft id; a `status` dict
(`connected`, `buffered`, `next_poll_at`, `last_error`) surfaced in Settings.

**Dependencies** — B1, B2, B3, `httpx`.

**Edge cases**
- One unreadable message must not stall the batch — fetch failures are logged
  and skipped.
- Messages are processed **oldest first** (`reversed(message_ids)`).
- Without `threadId` **and** `In-Reply-To`/`References`, Gmail files the draft as
  a brand-new conversation, which looks broken. Both are set.
- The reply sweep swallows all its errors: it is bookkeeping, and letting it
  abort a poll would stop new mail being fetched.
- Gmail has **no working deep link to an individual draft**, which is why the UI
  links to the *thread* instead.

**Future improvements** — Gmail push notifications (`users.watch` + Pub/Sub)
instead of polling · per-label filtering · richer quota/backoff telemetry.

---

### B5 · Whitelist

**Purpose** — Decide, cheaply and predictably, whether an email is processed.

**Responsibilities**
- Validate and normalise rule values; infer type from a leading `@`.
- CRUD with soft delete and duplicate detection.
- Match a sender against active rules, with a TTL cache.
- Bulk import from CSV/Excel with a per-row report.

**Features**
- **Type inference**: `alice@x.com` → exact email rule; `@x.com` → whole-domain
  rule. There is no type dropdown anywhere in the product.
- **Precedence**: exact email **always** beats domain. No tie-breaker is needed
  — uniqueness on `(value, is_active)` means a sender matches at most one rule
  of each kind.
- **Cache**: entries held in memory for `WHITELIST_CACHE_TTL_SECONDS` (60),
  invalidated on every write.
- **Import**: `value` column required; unknown columns (notably a legacy
  `priority`) are ignored rather than rejected, so old files still import.
  `row_index` is 1-based *including* the header, so it maps to spreadsheet row
  numbers.

**Inputs** — `POST/PUT` bodies; an uploaded CSV/XLSX; a raw sender address.
**Outputs** — `WhitelistEntry` rows; a `MatchResult` (`entry`, `matched_rule`,
`match_type`); a `BulkImportReport` (`total_rows`, `inserted`,
`skipped_duplicates`, `validation_errors[]`, `warnings[]`).

**Dependencies** — B1, B2, guardrails.

**Edge cases**
- `PUT` with an empty body → **400** (`exclude_unset`).
- Editing a value **re-infers the type** — changing `bob@x.com` to `@x.com`
  silently widens one address into an entire company. The UI warns live.
- Duplicate → **409**; invalid → **422**. Both messages are written for humans
  and are safe to display verbatim.
- A rule added now does **not** retroactively apply — see B6 (rescan).
- Cache staleness means a new rule can take up to 60 s to take effect.

**Future improvements** — Split the single flag into `summarize` and
`auto_draft` booleans (the two sets genuinely diverge — you would summarise your
boss but never auto-reply to them) · shared cache (Redis) for multi-worker ·
wildcard/subdomain rules · export.

---

### B6 · AutoReply Workflow

**Purpose** — The end-to-end pipeline for a single inbound email. This is the
heart of the system.

**Responsibilities** — Sanitize → deduplicate → log → match → summarise → draft
→ persist → file in Gmail → mark complete. Plus retry and rescan variants.

**Features**

`process_initial(event)`:

| # | Step | On failure |
|---|---|---|
| 1 | `sanitize_sender` — parse `Name <addr>` | Return `None`; nothing logged |
| 2 | Idempotency check on `gmail_message_id` | Return the existing log id |
| 3 | Create `MatchLog` (status `PENDING`) | — |
| 4 | `MatcherTool.match` | No match → `SKIPPED`, reason recorded, **stop** |
| 5 | Status → `PROCESSING`, record matched rule | — |
| 6 | `_execute_core` | See below |

`_execute_core`:

| # | Step | Note |
|---|---|---|
| 1 | `LLMAdapter.generate_draft` → summary + draft | 3 LLM calls (see B7/B8) |
| 2 | Persist `summary_json` **first** | Before anything else can fail |
| 3 | Store `GeneratedDraft` | The expensive artefact, secured |
| 4 | `create_draft` in Gmail, store `gmail_draft_id` | **Errors swallowed** |
| 5 | Status → `COMPLETED`, record `processing_ms` | — |

`process_rescan(log_id)` — re-examines a `SKIPPED` log against the *current*
whitelist. The body is not stored on the log, so the message is **re-fetched
from Gmail**; a rescan therefore needs a connected account and cannot recover
mail Gmail no longer has.

`process_retry(log_id, event)` — increments `retry_count` and re-runs the core.

**Background worker** — one asyncio task, draining in strict order:
retries → rescan (if requested) → pushed mail → polled mail → sleep 0.5 s.
Retry backoff is exponential: `AUTO_REPLY_RETRY_DELAY_SECONDS × 2^(attempt-1)`,
capped at `AUTO_REPLY_MAX_RETRIES` (3).

**Rescan trigger** — a boolean flag, set **only** by
`POST /api/v1/whitelist/rescan`. Whitelist writes deliberately do not set it: a
sweep re-fetches from Gmail, spends LLM calls and files real drafts, which is
far too much to happen as a side effect of typing an address into a form — and a
bulk import of 300 rules would fire it against the whole lookback window at once.
Repeated clicks collapse into one sweep, and the sweep re-reads rules when it
actually runs.

**Inputs** — `InboundEmailEvent` (from the poller or the push endpoint).
**Outputs** — Rows in `match_logs` and `generated_drafts`; a draft in Gmail.

**Dependencies** — B2, B4, B5, B7, B8.

**Edge cases**
- **Ordering matters.** Summary is persisted before the draft is stored, and the
  draft is stored before Gmail is called. A Gmail outage leaves a completed row
  with no draft link rather than dragging an already-paid-for LLM result through
  the retry queue.
- **Emails with no readable body** raise a non-retryable
  `InvalidEmailContentError` and land as `FAILED`. Image-only mail, calendar
  invites and some HTML newsletters hit this; a live inbox will show red rows.
- Disconnecting mid-run: buffered mail still processes, but draft filing is
  skipped with `gmail_draft_id = null`.
- A rescan that raises leaves the log in `PROCESSING`, so the next sweep will not
  re-pick it (only `SKIPPED` is eligible).

**Future improvements** — `POST /logs/{id}/regenerate` (versioning already
exists) · reclassify body-less mail as `SKIPPED` rather than `FAILED` · a real
`rate_limited` status (the dashboard field exists but can never be set today) ·
durable retry queue that survives restart.

---

### B7 · Summarization

**Purpose** — Turn an email (or thread) into provider-neutral, source-cited
structured context. It never retrieves, changes, sends or stores email.

**Responsibilities** — Normalise and truncate input · call the primary provider
with one retry · fall back to a second provider once · validate that every
citation refers to a message actually processed.

**Features** — `SummarizationResult`: `overview`, up to **7** cited
`key_points`, up to 20 `action_items` (task/owner/deadline), detected
`language`, plus `request_id`, `source_message_ids`, `omitted_message_ids`,
`truncated`.

Provider order: **Groq → Gemini**. A Groq-only configuration is valid.

**Inputs** — `SummarizationRequest` (1–100 messages; multiple messages must
share one non-empty `thread_id`; every message needs a non-empty text or HTML
body).
**Outputs** — `SummarizationResult`, or a typed `SummarizationError` carrying
`code`, `safe_message`, `retryable` and an HTTP status.

**Dependencies** — B1, provider SDKs. **Depends on nothing else in the app** —
it is reusable and directly exposed as `POST /api/v1/summaries`.

**Edge cases**
- Input over `SUMMARIZER_MAX_NORMALIZED_CHARS` (100k) or
  `SUMMARIZER_MAX_MESSAGES` (20) is truncated; `truncated: true` and
  `omitted_message_ids` say so, and the UI shows a badge.
- A model citing a message id it was not given is rejected as invalid output —
  this is the anti-hallucination guard.
- Configuration and content-rejection errors are **not** retried.
- `language` is the language of the *original email*. The summary prose itself
  is not guaranteed to be in that language.

**Future improvements** — Stream partial summaries · attachment text extraction
· per-provider cost/latency telemetry.

---

### B8 · Orchestrator & Drafting

**Purpose** — Decide what *kind* of reply this is, then write it.

**Responsibilities**
- Build a routing prompt from the template catalog and a JSON schema.
- Call the LLM for routing (**Groq → Gemini → mock**).
- Validate the result against `EmailRoutingSchema`; degrade on low confidence.
- Delegate text generation to a `Drafter`.

**Features**

*Routing* returns `template_id`, `extracted_data`, `confidence_score`. Two
degradation paths, both setting `used_fallback: true`:
1. Schema validation fails → `GENERAL_GREETING`, confidence `0.0`.
2. Confidence below `CONFIDENCE_THRESHOLD` (**0.6**) → `GENERAL_GREETING`.

*Drafting* — two implementations behind one `Drafter` protocol:

| Implementation | When | Output |
|---|---|---|
| `LLMDrafter` | Any API key configured | A real reply, written in `summary.language`, 3–6 sentences |
| `TemplateRenderDrafter` | No keys, or `LLMDrafter` threw | One fixed Jinja2 sentence per template |

`LLMDrafter` is instructed to invent no facts, respond only to what the summary
contains, and **not** sign off — the user adds their own signature. Post-
processing strips code fences, preambles ("Sure, here is…"), `Subject:` lines,
sign-offs and `[Your name]` placeholders.

**Inputs** — `SummarizationResult`.
**Outputs** — `DraftResult` (`draft_text`, `template_id`, `confidence_score`,
`extracted_data`, `provider_used`, `used_fallback`).

**Dependencies** — B1, B7's models, `email_module` (template catalog + schema).

**Edge cases**
- **`mock` provider.** With no keys at all, routing uses a Vietnamese/English
  keyword matcher that reports a hardcoded confidence of `0.85` — high enough to
  pass the threshold. Useful for frontend work; misleading in a demo.
- `compose()` has **no** mock: with no provider, `LLMDrafter` falls through to
  the static template. A real canned sentence beats an invented fake draft.
- `LLMDrafter` catches **every** exception. There is always a draft; an email is
  never marked `FAILED` because the writing step failed.
- The three templates and the drafting system prompt are written in Vietnamese.
  The LLM-written draft follows `summary.language`, but the **static fallback is
  Vietnamese only** — an English email that falls back gets a Vietnamese
  sentence.
- `run()` is synchronous and makes two blocking network calls, so the workflow
  dispatches it via `asyncio.to_thread`; calling it directly would freeze the
  event loop the API shares.

**Cost** — per whitelisted email, with keys configured: **3 LLM calls**
(summarise, route, compose). Senders matching no rule cost **zero**.

**Future improvements** — User-defined templates · per-sender tone · a
confidence signal from the drafting step, not just routing · translate the
static templates.

---

### B9 · Read APIs

**Purpose** — Serve everything the panel renders.

**Responsibilities** — Query, paginate and shape `match_logs`,
`generated_drafts` and aggregate statistics.

**Features**

| Endpoint | Notes |
|---|---|
| `GET /api/v1/auto-reply/inbox` | Log + summary + latest draft **in one response**. `since`, `page`, `page_size` (≤100), `include_skipped` (default false), `include_replied` (default false). Uses `selectinload` — one extra query for the page, not one per row. |
| `GET /api/v1/auto-reply/logs` | Filters: `sender_filter`, `status_filter`, `date_from`, `date_to`. |
| `GET /api/v1/auto-reply/status/{log_id}` | Status, `retry_count`, `error_detail`, `processing_ms`. |
| `GET /api/v1/auto-reply/drafts/{draft_id}` | One draft. |
| `GET /api/v1/auto-reply/logs/{log_id}/drafts` | Version history, oldest first. |
| `GET /api/v1/auto-reply/dashboard/summary` | `since_hours` (1–8760, default 24). |

**Dashboard fields** — `total_inbound_emails`, `matched_whitelist`, `unmatched`,
`total_drafts_generated`, `failed_generation`, `avg_processing_ms`,
`status_breakdown`, `active_whitelist_entries`, `top_senders[]`.

**Inputs** — Query parameters. **Outputs** — JSON.

**Dependencies** — B2.

**Edge cases**
- Every figure answers *"what happened in this window"*, never *"what would
  today's rules do"*. Top senders is filtered on the FK alone, matching
  `matched_whitelist` by construction — an earlier version required
  `is_active`, so deactivating a rule erased its sender from the chart while
  Matched kept counting, and the panel contradicted itself permanently.
- `status_breakdown.rate_limited` is **dead**: `ExecutionStatus` has no such
  member, so it is always `0`.
- The inbox total is counted before pagination, so paging is honest.
- Timestamps read back from SQLite are naive; `since`/`until` on the dashboard
  are offset-aware because Python builds them. The client parses both.

**Future improvements** — A `summarized` count · true SQL `COUNT` on inbox
(currently materialised in Python) · cursor pagination.

---

## 🛠 Frontend modules

---

### F1 · Side Panel Shell

**Purpose** — The app frame: header, tabs, panel switching, gating.

**Responsibilities** — Mount React and TanStack Query · hold UI state in
Zustand · hydrate settings from `chrome.storage` once at boot · gate all four
tabs behind a connected Gmail account.

**Features** — Tabs: **Inbox** (default) · Dashboard · Whitelist · Logs, plus a
Settings view reachable from the header. Tabs are **hidden** until an account is
connected (behind the gate they all lead to the same connect screen). Settings
stays reachable regardless, because the backend URL may need fixing before
connecting is even possible.

**Inputs** — `chrome.storage.local`; auth status from the backend.
**Outputs** — Rendered UI.

**Dependencies** — F6, all feature modules.

**Edge cases**
- Panels are keyed so switching remounts rather than reusing state across two
  unrelated views; inactive panels unmount, which also stops their polling.
- The side panel unmounts when closed, so the in-memory query cache dies with
  it. The refetch on reopen is accepted for the MVP.

**Future improvements** — Persisted query cache (only if reopen latency becomes
a real complaint) · deep-linking to a specific log.

---

### F2 · Inbox

**Purpose** — The product's centre: what arrived, what it said, what to reply.

**Responsibilities** — List processed emails, expand to show the summary,
confirm a draft exists, link into Gmail, advance the "seen" watermark.

**Features** — `EmailCard` (sender, subject, time) → expands to `SummaryView`
(overview, language badge, truncation badge, key points, action items) and
`DraftSection` (template id, provider badge, version badge, **Check draft**
button). Paginated at 25. Polls every 30 s. Viewing the tab clears the badge.

**Inputs** — `GET /auto-reply/inbox`.
**Outputs** — A Gmail tab opened at the thread.

**Dependencies** — F6, B9.

**Edge cases**
- **The draft text is deliberately not rendered.** It lives in Gmail as a real
  draft; showing a second copy invites editing the one that never gets sent.
- `gmail_draft_id === null` → an explicit amber notice: the reply *was*
  generated and stored, only the filing failed. Saying "no draft" would be
  wrong; saying nothing would leave a button that goes nowhere useful.
- Summary may be null (skipped, failed early, or an old row).
- Skipped and already-replied emails are excluded by default — Logs shows them.

**Future improvements** — Regenerate button · inline "why this template" ·
filter by sender.

---

### F3 · Whitelist

**Purpose** — Manage the rules that decide what gets processed.

**Responsibilities** — Quick add with live type inference · inline edit ·
delete · CSV/Excel import with a results panel · suggest the sender of the
thread currently open in Gmail · trigger a rescan.

**Features**
- **One input, no dropdown.** Typing `@fpt.edu.vn` shows *"Domain rule — matches
  everyone at fpt.edu.vn"* **before** submitting, not after a whole department
  starts getting automatic replies.
- **Quick-add suggestion** from the content script, shown only when the field is
  empty. Clicking it *fills* the field rather than submitting, so inference and
  guardrail feedback are visible first.
- **Import** renders a per-row report (a toast cannot carry it).

**Inputs** — Typed values, uploaded files, `chrome.storage` sender capture.
**Outputs** — Whitelist mutations; a rescan request.

**Dependencies** — F6, F7, B5, B6.

**Edge cases** — 409/422 messages are shown verbatim · a rejected value stays in
the field so it can be corrected rather than retyped · no Restore button and no
trash view, because delete is soft with no restore endpoint · widening warning
on edit.

**Future improvements** — Downloadable CSV template · bulk delete · search.

---

### F4 · Logs

**Purpose** — Answer "what happened to this email, and why?"

**Responsibilities** — Paginated, filterable history of every inbound email.

**Features** — Status filter tabs (all / completed / failed / skipped) · sender
and date filters · per-row status, matched rule, error detail, processing time.

**Inputs** — `GET /auto-reply/logs`.
**Outputs** — Read-only display.

**Dependencies** — F6, B9.

**Edge cases** — The response omits `sender_name`, `gmail_thread_id` and
`retry_count` that exist on the model, so the list shows raw addresses and
retry count needs the per-log status endpoint.

**Future improvements** — Expose the omitted fields · export · link a log row to
its inbox card.

---

### F5 · Dashboard & Settings

**Dashboard purpose** — Is the system working, and how much is it doing?

**Features** — Stat cards (inbound, matched, drafts, failed, average processing
time) · status breakdown bar · top senders · time-window filter (hours).

**Settings purpose** — Everything device-local, plus the Gmail connection.

**Features** — Gmail connect/disconnect with live status · backend URL with a
**Test** button that pings `/health` · background interval (1/5/15/30 min) ·
notifications toggle · reset to defaults · extension version.

**Edge cases**
- The Test button uses a raw `fetch` against the *draft* URL — the shared client
  reads the saved one, which is not what is being tested.
- Pointing at any origin outside `localhost:8000` / `127.0.0.1:8000` fails as an
  opaque network error because the manifest does not grant it. The panel warns
  explicitly rather than letting someone debug a dead app.
- Saving a new backend URL **clears** the query cache: the data is not stale, it
  is from somewhere else.

**Future improvements** — Surface backend config (poll interval, threshold) ·
show `poller.last_error` prominently.

---

### F6 · Service Layer

**Purpose** — One typed, normalised boundary between UI and backend.

**Responsibilities** — HTTP clients · error normalisation · query keys ·
hand-mirrored types.

**Features**
- `http.ts` (axios) for the panel; `fetchClient.ts` (fetch) for the worker.
- **The backend returns two error shapes** — `{request_id, code, message,
  retryable}` from summarization/routing, and `{detail}` from FastAPI's
  `HTTPException`. Both are normalised into one `ApiError`; neither raw shape
  ever reaches a component.
- Retry policy is driven by the backend's own `retryable` flag rather than an
  invented client-side rule.
- `services/api/` mirrors backend routers **1:1**, so adding auth later means
  touching one interceptor rather than thirty components.

**Edge cases** — Types in `types/api.ts` are *assertions*, not validations;
nothing checks at runtime that a response matches. Each block names the Python
source it mirrors so the two can be diffed.

**Future improvements** — Generate types from the OpenAPI schema · runtime
validation at the boundary.

---

### F7 · Service Worker & Content Script

**Service worker purpose** — Keep the user informed while the panel is closed.

**Features** — `chrome.alarms` poll · badge count · desktop notification on an
*increase* only (a persisted high-water mark stops every poll re-announcing the
same backlog) · re-reads settings when they change.

**Content script purpose** — Notice which Gmail thread is open, so its sender
can be quick-added.

**Features** — Four sender-detection strategies tried in order (most to least
durable), debounced 400 ms behind a `MutationObserver`. Reads only the message
*header* region — a body frequently quotes other addresses, and whitelisting the
wrong person is a silent, consequential mistake. Retracts the capture on leaving
a thread or the page.

**Inputs** — Alarms; Gmail's DOM. **Outputs** — Badge, notifications,
`chrome.storage` sender capture.

**Edge cases**
- **No axios in the worker** — its browser build needs `XMLHttpRequest`, absent
  in service workers.
- **No `setInterval` and no module state** — the worker is torn down after ~30 s
  idle; every top-level statement re-runs on wake and must be idempotent.
- Chrome silently clamps alarms below one minute.
- A failed poll leaves the badge alone; clearing it would claim there is nothing
  new, which is not what we know.
- **Gmail's DOM is undocumented and changes without notice.** Every selector is
  an observed pattern, not a contract. When quick-add stops finding senders,
  `readSender.ts` is the file to fix.

**Permissions** — `storage`, `sidePanel`, `alarms`, `notifications`, plus host
access to `localhost:8000` / `127.0.0.1:8000`. Deliberately **no** `tabs`
permission: "Check draft" uses `window.open`, whereas reusing the open Gmail tab
would force every installed user to re-approve a "Read your browsing history"
warning on update.

**Future improvements** — Resilience tests against captured Gmail DOM snapshots
· notification click → open the panel on that email.

---

# 6. Feature Specifications

## 👤 F-01 · Connect your Gmail account

**What it does** — Grants the backend permission to read your inbox and create
drafts in it.

**How to use it** — Side panel → ⚙ Settings → **Connect Gmail**. A Google
consent tab opens; approve it and close the tab. The panel then shows
**Connected** with your address.

**What you should know**
- You are granting access to the **backend running on your machine**, not to the
  extension. The extension asks for no Gmail permissions at all.
- In Testing mode Google shows an "unverified app" warning. Choose
  **Advanced → Go to AI Email Assistant (unsafe)**.
- Only the last 60 minutes of mail is considered on first connect — connecting
  will not draft replies to a month of history.
- You can revoke access at any time, independently, at
  <https://myaccount.google.com/permissions>.

---

## 👤 F-02 · Whitelist a sender

**What it does** — Tells the assistant which senders to process. Everything else
is ignored.

**How to use it** — Whitelist tab → type an address or a domain → **Add**.
- `alice@company.com` → just Alice.
- `@company.com` → **everyone** at company.com.

The panel tells you which one you are about to create, before you press Add.

**What you should know**
- If a thread is open in Gmail, its sender is offered as a one-click suggestion.
- An exact address always wins over a domain rule.
- A new rule can take up to a minute to take effect.
- A new rule does **not** automatically apply to mail that already arrived —
  use **Rescan** (F-06).

---

## 👤 F-03 · Automatic summary and draft

**What it does** — For each new email from a whitelisted sender, the assistant
reads it, writes a reply, and files that reply as a Gmail draft on the same
conversation.

**How to use it** — Nothing to do. Open the Inbox tab to see what has been
processed.

**What you get per email**
| | |
|---|---|
| **Overview** | A few sentences: what this email is about |
| **Key points** | Up to seven, each traceable to the message it came from |
| **Action items** | Task, and where stated, who owns it and by when |
| **Language** | The language of the incoming mail — the draft is written to match |
| **Draft reply** | In Gmail, threaded under the original. Never sent. |

**What you should know**
- Default checking interval is 60 seconds.
- The draft text is **not** shown in the panel on purpose — it lives in Gmail,
  which is where you will edit and send it. Press **Check draft** to go there.
- A "truncated" badge means the original was too long to read in full.
- Reply drafts are suggestions. Read them before sending. They can be wrong.

---

## 👤 F-04 · Review a draft in Gmail

**What it does** — Takes you to the conversation in Gmail, where the draft is
attached under the thread.

**How to use it** — Inbox tab → expand an email → **Check draft**. A new Gmail
tab opens.

**What you should know**
- The link opens the **thread**, not the draft directly — Gmail has no reliable
  deep link to an individual draft.
- If you use several Google accounts in one browser, the link opens whichever
  signed in first, which may not be the connected one.
- Occasionally you will see *"The reply was generated but could not be filed in
  Gmail."* The text was written and saved, but Gmail was unreachable at that
  moment, so there is no draft to open.

---

## 👤 F-05 · See what was skipped, and why

**What it does** — Records every inbound email, including the ones nothing
happened to.

**How to use it** — Logs tab. Filter by status: completed / failed / skipped.

**What you should know**
- **skipped** = the sender matched no rule. This is the normal, intended outcome
  for most mail, and it costs nothing.
- **failed** = processing was attempted and did not finish. The most common
  cause is an email with no readable text — image-only mail, calendar invites,
  some HTML newsletters.
- If your Inbox tab is empty, this is the tab that tells you why.

---

## 👤 F-06 · Rescan mail that was skipped

**What it does** — Re-examines recently skipped mail against your *current*
rules, so mail that arrived before you added a rule is not stranded.

**How to use it** — Whitelist tab → **Rescan**.

**What you should know**
- It only reaches back 24 hours by default.
- It is an explicit button, never automatic, because a sweep genuinely re-reads
  mail, spends AI calls, and creates real drafts in your mailbox.
- It needs a connected account, and cannot recover mail Gmail no longer has.
- The result appears in Logs; the button returns immediately.

---

## 👤 F-07 · Replied mail retires itself

**What it does** — Once you reply on a thread, that email disappears from the
Inbox view. It has been dealt with.

**How to use it** — Nothing to do.

**What you should know**
- Detection works by looking at your **sent mail**, so replies you typed
  entirely by hand count too — you do not have to use the generated draft.
- The record is kept; Logs still shows it.
- Detection happens on the next poll, so allow a minute.

---

## 👤 F-08 · Dashboard

**What it does** — Shows whether the system is working and how much it is doing.

**How to use it** — Dashboard tab. Pick a time window.

**Shows** — Emails seen · matched vs unmatched · drafts generated · failures ·
average processing time · status breakdown · your top senders · number of active
rules.

---

## 👤 F-09 · Notifications while the panel is closed

**What it does** — Puts a count on the toolbar icon and (optionally) shows a
desktop notification when new mail has been processed.

**How to use it** — Settings → Background check interval, and the notifications
toggle.

**What you should know**
- Chrome will not run background checks more than once a minute.
- You are notified when the count **increases**, not on every check.
- Opening the Inbox tab clears the badge.

---

## 👤 F-10 · Settings

Backend URL (with a **Test** button) · background interval · notifications
toggle · Gmail connect/disconnect · reset to defaults.

Settings are stored **on this device only** and are not shared with the backend.

---

# 7. User Stories

## Conventions

- **Priority** — `P0` MVP-critical (the product does not function without it) ·
  `P1` important · `P2` nice to have, still implemented.
- **Acceptance Criteria** use Given–When–Then.
- Each story names the responsible layer: **[EXT]** Chrome extension ·
  **[BE]** backend · **[GMAIL]** Gmail API · **[LLM]** model provider.

---

### US-01 · Connect a Gmail account

| | |
|---|---|
| **ID** | US-01 |
| **Priority** | P0 |

**Description**
As a **user**, I want to connect my Gmail account to the assistant, so that it
can read new mail and prepare draft replies for me.

**Preconditions**
- The backend is running and reachable at the configured URL.
- `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set in `backend/.env`.
- My address is listed as a test user on the OAuth consent screen.
- No account is currently connected.

**Acceptance Criteria**
- **AC1** — *Given* the backend has Google credentials configured and no account
  connected, *when* I open Settings, *then* I see a **Connect Gmail** button.
- **AC2** — *Given* I click Connect Gmail, *when* the browser opens Google's
  consent screen, *then* the requested scopes are exactly `gmail.readonly`,
  `gmail.compose` and `userinfo.email`.
- **AC3** — *Given* I approve consent, *when* Google redirects back, *then* a
  confirmation page names the connected address and tells me I can close the tab.
- **AC4** — *Given* consent succeeded, *when* I return to the panel, *then*
  Settings shows **Connected** with my address, and the four tabs become visible.
- **AC5** — *Given* the backend has **no** Google credentials configured, *when*
  I open Settings, *then* I see an explanatory notice instead of a Connect
  button, and no OAuth attempt is possible.

**Main Flow**
1. **[EXT]** User opens Settings and clicks *Connect Gmail*.
2. **[EXT]** Opens `GET /api/v1/gmail/auth/start` in a new tab.
3. **[BE]** Issues a single-use `state` and redirects (307) to Google.
4. **[GMAIL]** User authenticates and approves the scopes.
5. **[GMAIL]** Redirects to `/api/v1/gmail/auth/callback?code=…&state=…`.
6. **[BE]** Validates and consumes `state`; exchanges the code for tokens.
7. **[BE]** Calls `userinfo` to identify the account; persists an
   `OAuthCredential`.
8. **[BE]** Renders a success page.
9. **[EXT]** Next `GET …/auth/status` poll returns `connected: true`; the gate
   opens.

**Alternative Flow**
- **A1 — Already connected.** Connecting again replaces the stored credential
  (`provider` is unique). No second row is created.
- **A2 — User cancels at Google.** Google returns `error=access_denied`; the
  callback renders "Connection cancelled". Nothing is stored.

**Error Cases**
| Case | Handling |
|---|---|
| OAuth not configured | `/start` → **503** with a readable message |
| `state` missing, expired or replayed | Callback renders "Expired or invalid request" and instructs restarting from Settings |
| Code exchange fails | Callback renders "Could not connect" with Google's message; nothing persisted |
| Gmail API not enabled on the project | Consent succeeds; later polls fail with 403, surfaced as `poller.last_error` |
| Backend unreachable | Settings shows a connection error; the Test button diagnoses it |

**Post Conditions**
- One `oauth_credentials` row exists with a refresh token and granted scopes.
- `last_polled_at` is null, so the first poll uses the 60-minute lookback.
- The panel's four tabs are unlocked.

**Dependencies** — None. This is the root story.

---

### US-02 · See connection status and disconnect

| | |
|---|---|
| **ID** | US-02 |
| **Priority** | P1 |

**Description**
As a **user**, I want to see which account is connected and be able to
disconnect it, so that I stay in control of what the assistant can reach.

**Preconditions** — Backend reachable.

**Acceptance Criteria**
- **AC1** — *Given* an account is connected, *when* I open Settings, *then* I
  see the address, the granted scopes and when it last checked for mail.
- **AC2** — *Given* an account is connected, *when* I click **Disconnect**,
  *then* the credential is deleted and the panel returns to the connect screen.
- **AC3** — *Given* no account is connected, *when* I disconnect, *then* the
  request returns **404** and the UI does not claim success.
- **AC4** — *Given* polling has failed, *when* I open Settings, *then* the last
  error is visible rather than silently swallowed.

**Main Flow**
1. **[EXT]** Settings queries `GET /api/v1/gmail/auth/status`.
2. **[BE]** Returns `configured`, `connected`, `email_address`, `scopes`,
   `last_polled_at`, `poll_interval_seconds`, and the poller's status.
3. **[EXT]** Renders. On **Disconnect**, calls `DELETE /api/v1/gmail/auth/`.
4. **[BE]** Removes the credential; returns **204**.

**Alternative Flow**
- **A1** — The user revokes access at Google instead. The stored credential
  remains locally but polls begin failing with 401, shown as `last_error`.

**Error Cases**
| Case | Handling |
|---|---|
| No account connected | 404, surfaced verbatim |
| Backend down | Query error state with a Retry button |

**Post Conditions** — After disconnect: no `oauth_credentials` row; polling backs
off; existing logs, summaries and drafts are **retained**.

**Dependencies** — US-01.

---

### US-03 · Add a sender to the whitelist

| | |
|---|---|
| **ID** | US-03 |
| **Priority** | P0 |

**Description**
As a **user**, I want to add an email address or a whole domain to the
whitelist, so that mail from that source is summarised and gets a draft reply.

**Preconditions** — Backend reachable. Whitelist tab open.

**Acceptance Criteria**
- **AC1** — *Given* an empty field, *when* I type `alice@example.com`, *then*
  the panel shows an `email` badge and explains it matches that address only.
- **AC2** — *Given* an empty field, *when* I type `@example.com`, *then* the
  panel shows a `domain` badge and warns it matches **everyone** at that domain
  — **before** I submit.
- **AC3** — *Given* a valid value, *when* I click Add, *then* a rule is created
  (**201**), the list refreshes, and the field clears.
- **AC4** — *Given* a value that already exists, *when* I click Add, *then* I
  see the backend's **409** message inline and the field keeps my input.
- **AC5** — *Given* a malformed value, *when* I click Add, *then* the Add button
  is disabled and a validation hint is shown; no request is made.

**Main Flow**
1. **[EXT]** User types a value; the panel infers the type from a leading `@`,
   mirroring the backend's own rule, and shows the consequence live.
2. **[EXT]** `POST /api/v1/whitelist { value }`.
3. **[BE]** Guardrails normalise (trim, lowercase) and validate; type inferred.
4. **[BE]** Checks for an existing active row with the same value.
5. **[BE]** Inserts, invalidates the match cache, returns **201**.
6. **[EXT]** Invalidates its own `['whitelist']` query cache and re-renders.

**Alternative Flow**
- **A1 — Previously deleted value.** Delete is soft, so re-adding the same value
  **reactivates the original row** rather than creating a new one. "Delete then
  re-add" is not a clean slate.
- **A2 — Sender suggested from Gmail.** See US-04.

**Error Cases**
| Case | Handling |
|---|---|
| Empty / malformed | 422; message shown verbatim |
| Over 320 chars (email) or 255 (domain) | 422 `value_too_long` |
| Duplicate active value | 409; input preserved for correction |
| Backend unreachable | Inline error; nothing lost |

**Post Conditions**
- An active `whitelist_entries` row exists.
- The backend match cache is invalidated; new mail matches immediately.
- Mail that **already** arrived is unaffected — see US-11.

**Dependencies** — None (works without Gmail connected).

---

### US-04 · Quick-add the sender of the thread I am reading

| | |
|---|---|
| **ID** | US-04 |
| **Priority** | P2 |

**Description**
As a **user** reading a thread in Gmail, I want the panel to offer that sender,
so that I can whitelist them without retyping the address.

**Preconditions** — On `mail.google.com` with a thread open; the panel is open
on the Whitelist tab; the quick-add field is empty.

**Acceptance Criteria**
- **AC1** — *Given* a thread is open, *when* I switch to the Whitelist tab,
  *then* a suggestion row shows that thread's sender address.
- **AC2** — *Given* the suggestion is shown, *when* I click it, *then* the value
  **fills the input** rather than submitting — so the inferred type and any
  validation feedback are visible before anything is created.
- **AC3** — *Given* I start typing, *when* the field is non-empty, *then* the
  suggestion is hidden; it is a shortcut for an empty field, not a competitor.
- **AC4** — *Given* I navigate back to the inbox list, *when* no thread is open,
  *then* the suggestion is withdrawn.

**Main Flow**
1. **[EXT/content]** A `MutationObserver` fires; capture is debounced 400 ms.
2. **[EXT/content]** Reads the newest expanded message and extracts the sender
   from its **header** region only, trying four strategies in order.
3. **[EXT/content]** Writes `{email, name, subject}` to `chrome.storage.local`.
4. **[EXT/panel]** Reads it and renders the suggestion.
5. User clicks it → the value is placed in the field → continue at US-03 step 1.

**Alternative Flow**
- **A1 — Same sender, different thread.** The capture signature includes the
  subject, so moving between two threads from one sender still refreshes.

**Error Cases**
| Case | Handling |
|---|---|
| No thread on screen | No suggestion; the field works normally |
| Gmail changed its DOM and no strategy matches | No suggestion; feature degrades silently. Fix `readSender.ts` |
| Address found only in the quoted body | **Not** used — reading beyond the header risks whitelisting the wrong person |

**Post Conditions** — Only the input field is populated. Nothing is created
until the user presses Add.

**Dependencies** — US-03.

---

### US-05 · Import many rules from a file

| | |
|---|---|
| **ID** | US-05 |
| **Priority** | P2 |

**Description**
As a **user** with an existing list of contacts, I want to import a CSV or Excel
file, so that I do not add hundreds of rules by hand.

**Preconditions** — A file with a `value` column. Backend reachable.

**Acceptance Criteria**
- **AC1** — *Given* a valid CSV, *when* I upload it, *then* I get a report
  showing total rows, inserted, skipped duplicates and per-row errors.
- **AC2** — *Given* a file with some invalid rows, *when* I upload it, *then*
  valid rows are still inserted and each invalid row is listed with its
  spreadsheet row number and reason.
- **AC3** — *Given* a file with a legacy `priority` column, *when* I upload it,
  *then* the column is ignored and the import succeeds.
- **AC4** — *Given* an unsupported file type, *when* I upload it, *then* I get a
  **400** naming the accepted formats.

**Main Flow**
1. **[EXT]** User selects a file; `POST /api/v1/whitelist/import` (multipart).
2. **[BE]** Detects format from extension or content type.
3. **[BE]** Validates each row; inserts valid, non-duplicate values.
4. **[BE]** Invalidates the match cache if anything was inserted.
5. **[BE]** Returns a `BulkImportReport`.
6. **[EXT]** Renders it as a **panel**, not a toast — a toast cannot carry a
   per-row error list.

**Alternative Flow**
- **A1** — All rows are duplicates: `inserted: 0`, cache untouched, report still
  rendered.

**Error Cases**
| Case | Handling |
|---|---|
| Unsupported format | 400 |
| Over `BULK_IMPORT_MAX_ROWS` (10 000) | **Truncated, not rejected** — the first 10 000 rows import and a warning names the real row count |
| Missing `value` column | Every row reports "Missing required 'value' field" |
| Malformed row | Listed with `row_index` (1-based **including** the header, so the first data row is 2 — it maps to the spreadsheet) |

**Post Conditions** — Valid rows exist as active entries; the report is
displayed until dismissed.

**Dependencies** — US-03.

---

### US-06 · Edit a whitelist rule

| | |
|---|---|
| **ID** | US-06 |
| **Priority** | P2 |

**Description**
As a **user**, I want to correct a rule I typed wrong, so that I do not have to
delete and recreate it.

**Preconditions** — At least one active rule.

**Acceptance Criteria**
- **AC1** — *Given* a rule, *when* I edit its value and save, *then* the rule is
  updated and the list refreshes.
- **AC2** — *Given* I have changed nothing, *when* I look at Save, *then* it is
  disabled — an empty patch is a **400** on the backend.
- **AC3** — *Given* I change `bob@x.com` to `@x.com`, *when* I save, *then* the
  rule's type is **re-inferred to domain** and I am warned that it now matches
  the whole domain.
- **AC4** — *Given* I enter a value another active rule already uses, *when* I
  save, *then* I see the **409** message and the edit is not applied.

**Main Flow**
1. **[EXT]** User edits inline; only changed fields are sent.
2. **[EXT]** `PUT /api/v1/whitelist/{id} { value }`.
3. **[BE]** Re-validates, re-infers type, checks duplicates, updates.
4. **[BE]** Invalidates the match cache; returns the updated entry.

**Alternative Flow** — **A1** Cancel: the row reverts, nothing sent.

**Error Cases**
| Case | Handling |
|---|---|
| Empty patch | 400 — prevented client-side |
| Entry not found (deleted concurrently) | 404; list refreshed |
| Invalid value | 422 verbatim |
| Duplicate | 409 verbatim |

**Post Conditions** — The row carries the new value and possibly a new
`entry_type`. Matching behaviour changes within one cache TTL.

**Dependencies** — US-03.

---

### US-07 · Remove a whitelist rule

| | |
|---|---|
| **ID** | US-07 |
| **Priority** | P1 |

**Description**
As a **user**, I want to stop the assistant processing a sender, so that their
mail is left alone from now on.

**Preconditions** — At least one active rule.

**Acceptance Criteria**
- **AC1** — *Given* a rule, *when* I delete it, *then* it disappears from the
  list (**204**).
- **AC2** — *Given* a deleted rule, *when* new mail arrives from that sender,
  *then* it is logged as **skipped**.
- **AC3** — *Given* a deleted rule, *when* I look for a way to restore it,
  *then* there is none — deletion is presented as final.
- **AC4** — *Given* a deleted rule, *when* I look at the Dashboard, *then*
  emails it already processed are **still counted** — the dashboard reports what
  happened, not what today's rules would do.

**Main Flow**
1. **[EXT]** `DELETE /api/v1/whitelist/{id}`.
2. **[BE]** Sets `is_active = False` (soft delete).
3. **[BE]** Invalidates the match cache; returns **204**.

**Alternative Flow** — **A1** Re-adding the same value later reactivates the
original row (see US-03/A1).

**Error Cases** — Not found → 404. Backend unreachable → error state, list
unchanged.

**Post Conditions** — The row persists with `is_active = False`. Existing
`match_logs` keep their FK and history.

**Dependencies** — US-03.

---

### US-08 · Have new mail summarised and drafted automatically

| | |
|---|---|
| **ID** | US-08 |
| **Priority** | P0 |

**Description**
As a **user**, I want mail from whitelisted senders to be summarised and to have
a reply drafted without me asking, so that the work is already done when I look.

**Preconditions**
- An account is connected (US-01).
- At least one active whitelist rule (US-03).
- At least one LLM provider key configured.

**Acceptance Criteria**
- **AC1** — *Given* a whitelisted sender emails me, *when* one poll interval
  passes, *then* a `match_logs` row exists with status **completed**.
- **AC2** — *Given* processing completed, *when* I look at that email in the
  panel, *then* it carries an overview, key points, action items and a detected
  language.
- **AC3** — *Given* processing completed, *when* I open the thread in Gmail,
  *then* a draft reply is attached **to that conversation**, in the language of
  the incoming mail, and **nothing has been sent**.
- **AC4** — *Given* a sender matching **no** rule emails me, *when* a poll
  passes, *then* the log is **skipped**, no LLM call is made, and no draft is
  created.
- **AC5** — *Given* the same Gmail message is seen twice, *when* it is
  processed, *then* no duplicate log and no second draft are created.
- **AC6** — *Given* routing confidence is below `0.6`, *when* the draft is
  produced, *then* `used_fallback` is true and the safe generic template is used.

**Main Flow**
1. **[BE]** Poller lists messages newer than the watermark (max 25).
2. **[BE]** Fetches each, parses to an `InboundEmailEvent`, buffers.
3. **[BE]** Worker picks one up; sanitizes the sender.
4. **[BE]** Rejects duplicates on `gmail_message_id`.
5. **[BE]** Creates a `MatchLog`.
6. **[BE]** `MatcherTool` matches — exact address beats domain.
7. **[BE]** Status → `PROCESSING`.
8. **[LLM]** Summarize (Groq → Gemini). Citations validated against the
   messages actually processed.
9. **[BE]** Persists `summary_json` **before** anything else can fail.
10. **[LLM]** Route → `template_id`, `extracted_data`, `confidence_score`.
11. **[BE]** Validates against the schema; degrades below threshold.
12. **[LLM]** Compose the reply in `summary.language`; backend strips fences,
    preambles, `Subject:` lines and sign-offs.
13. **[BE]** Stores the `GeneratedDraft`.
14. **[GMAIL]** `drafts.create` with `threadId` plus `In-Reply-To` /
    `References`.
15. **[BE]** Stores `gmail_draft_id`; status → `COMPLETED` with
    `processing_ms`.

**Alternative Flow**
- **A1 — Not whitelisted.** Stop at step 6: `SKIPPED`, reason "Sender not on
  whitelist." Zero cost.
- **A2 — No LLM key.** Routing uses the `mock` keyword matcher and drafting
  falls back to a static template. The pipeline completes; quality is poor.
- **A3 — Groq fails.** Gemini is tried once for summarization, and independently
  for routing and composing.
- **A4 — Compose fails.** `LLMDrafter` falls back to the static template. There
  is always a draft; the email is never `FAILED` because writing failed.
- **A5 — Pushed rather than polled.** `POST /api/v1/gmail/incoming` injects an
  event into the same pipeline (used for testing).

**Error Cases**
| Case | Handling |
|---|---|
| Unparseable sender | Nothing logged; warning only |
| No readable body | Non-retryable `InvalidEmailContentError` → **failed** |
| Retryable summarization error | Re-raised → retry queue, exponential backoff, max 3 attempts, then **failed** |
| All routing providers fail | `LLMRoutingError` → 502 shape; treated as an unexpected error → retry then **failed** |
| Gmail unreachable at draft time | **Swallowed.** Status stays **completed**, `gmail_draft_id` null, panel shows an amber notice |
| Account disconnected mid-run | Buffered mail still processes; draft filing skipped |
| One message in the batch unreadable | Logged and skipped; the batch continues |

**Post Conditions**
- `match_logs`: one row, `completed`, with `summary_json` and `processing_ms`.
- `generated_drafts`: one row, version 1, with provider, template, confidence,
  `used_fallback` and (usually) `gmail_draft_id`.
- Gmail: one draft on the original thread. **No mail sent.**

**Dependencies** — US-01, US-03.

---

### US-09 · Read the summary of a processed email

| | |
|---|---|
| **ID** | US-09 |
| **Priority** | P0 |

**Description**
As a **user**, I want to read a structured summary of each processed email, so
that I know what it says without opening it.

**Preconditions** — At least one email has completed processing (US-08).

**Acceptance Criteria**
- **AC1** — *Given* processed emails exist, *when* I open the Inbox tab, *then*
  they are listed newest first with sender, subject and time.
- **AC2** — *Given* an email in the list, *when* I expand it, *then* I see the
  overview, a language badge, key points and action items.
- **AC3** — *Given* an email had no action items, *when* I expand it, *then* the
  Action items section is **absent** — an empty heading reads as failure.
- **AC4** — *Given* the original was truncated, *when* I expand it, *then* a
  "truncated" badge and an explanatory line are shown.
- **AC5** — *Given* nothing has been processed, *when* I open the tab, *then* I
  see an empty state that points me at Logs to find out why.
- **AC6** — *Given* the panel is open, *when* 30 seconds pass, *then* the list
  refreshes without me acting.

**Main Flow**
1. **[EXT]** `GET /api/v1/auto-reply/inbox?page=1&page_size=25`.
2. **[BE]** Excludes skipped and already-replied rows by default; returns log +
   summary + latest draft **in one response**.
3. **[EXT]** Renders cards; expanding reveals `SummaryView`.
4. **[EXT]** Records "seen now", clearing the badge.

**Alternative Flow**
- **A1 — Older row with no summary.** Rows predating summary persistence render
  without a summary section rather than erroring.
- **A2 — More than 25 items.** Paginated; `total` is counted before pagination.

**Error Cases**
| Case | Handling |
|---|---|
| Backend unreachable | Error state with a Retry button gated on `retryable` |
| Panel reopened | In-memory cache is gone; a refetch shows a skeleton first |

**Post Conditions** — The "last seen" watermark advances; the badge is cleared.

**Dependencies** — US-08.

---

### US-10 · Open the draft in Gmail

| | |
|---|---|
| **ID** | US-10 |
| **Priority** | P0 |

**Description**
As a **user**, I want to jump from the panel to the draft in Gmail, so that I
can edit and send it where I normally work.

**Preconditions** — A processed email with a stored draft.

**Acceptance Criteria**
- **AC1** — *Given* a draft was filed, *when* I expand the email, *then* I see
  the template used, the provider, and the message that a draft was created and
  nothing was sent.
- **AC2** — *Given* a draft was filed, *when* I click **Check draft**, *then*
  Gmail opens in a **new tab** at that conversation, with the draft attached.
- **AC3** — *Given* the draft could **not** be filed in Gmail, *when* I expand
  the email, *then* an amber notice states the reply was generated but not
  filed, so I do not go looking for a draft that is not there.
- **AC4** — *Given* several draft versions exist, *when* I expand the email,
  *then* the version badge shows which one is current.
- **AC5** — *Given* I am on the Inbox tab, *when* I look for the draft text,
  *then* it is **not** rendered in the panel — by design.

**Main Flow**
1. **[EXT]** Renders `DraftSection` from `latest_draft`.
2. **[EXT]** Builds `https://mail.google.com/mail/u/0/#all/<threadId>`.
3. **[EXT]** `window.open(url, '_blank', 'noopener')`.
4. **[GMAIL]** Shows the thread with the draft inline.

**Alternative Flow**
- **A1 — No thread id.** Falls back to the message id.
- **A2 — Thread archived.** `#all/` is used precisely so archived threads still
  resolve; `#inbox/` would land on an empty view.

**Error Cases**
| Case | Handling |
|---|---|
| `gmail_draft_id` null | AC3 notice; the button still opens the thread |
| Multiple Google accounts | `/u/0/` is the first signed-in account, which may be the wrong mailbox. **Known limitation** — Gmail supports no other selector |
| Draft deleted in Gmail | The thread opens without a draft; the stored text remains |

**Post Conditions** — A new Gmail tab. No state changes in the backend.
Sending remains entirely the user's action.

**Dependencies** — US-08, US-09.

---

### US-11 · Rescan mail skipped before a rule existed

| | |
|---|---|
| **ID** | US-11 |
| **Priority** | P1 |

**Description**
As a **user** who has just added a rule, I want recently skipped mail from that
sender re-examined, so that adding a rule is not silently useless for mail that
already arrived.

**Preconditions** — A connected account; at least one skipped log within
`WHITELIST_RESCAN_LOOKBACK_HOURS` (24); at least one rule that now matches it.

**Acceptance Criteria**
- **AC1** — *Given* skipped mail now matches a rule, *when* I trigger Rescan,
  *then* the request is accepted (**202**) and returns immediately.
- **AC2** — *Given* the sweep runs, *when* a skipped log now matches, *then* it
  is re-fetched from Gmail, processed exactly as new mail, and its stale skip
  reason is **cleared**.
- **AC3** — *Given* the sweep runs, *when* a skipped log still matches nothing,
  *then* it is left untouched.
- **AC4** — *Given* I add a rule, *when* I do **not** press Rescan, *then* no
  sweep occurs — adding a rule never spends LLM calls or creates drafts as a
  side effect.
- **AC5** — *Given* I click Rescan several times quickly, *when* the worker
  picks it up, *then* exactly one sweep runs.

**Main Flow**
1. **[EXT]** `POST /api/v1/whitelist/rescan`.
2. **[BE]** Sets the rescan flag; returns **202**.
3. **[BE]** Worker consumes the flag before handling new inbound mail, so a
   just-added rule applies to the backlog in arrival order.
4. **[BE]** Lists `SKIPPED` logs within the lookback window.
5. **[BE]** For each: re-match → re-fetch from Gmail → clear `error_detail` →
   run the standard core pipeline (US-08 steps 8–15).
6. **[BE]** Logs a report: examined / matched / failed.

**Alternative Flow**
- **A1 — Lookback is 0.** Rescanning is disabled; the sweep returns an empty
  report.
- **A2 — Concurrently processed.** A log already moved out of `SKIPPED` is
  stepped over, not an error.

**Error Cases**
| Case | Handling |
|---|---|
| No account connected | Each re-fetch fails; logged, sweep continues, nothing changes |
| Gmail no longer has the message | That log is counted failed and skipped over |
| One log raises | Counted, logged, sweep continues. The log stays `PROCESSING` and will not be re-picked (only `SKIPPED` is eligible) |

**Post Conditions** — Matching logs move from `skipped` to `completed` (or
`failed`) with a summary, a draft and a Gmail draft. The result is visible in
Logs; the endpoint itself reports nothing.

**Dependencies** — US-01, US-03, US-08.

---

### US-12 · Understand why an email was not processed

| | |
|---|---|
| **ID** | US-12 |
| **Priority** | P1 |

**Description**
As a **user** whose Inbox tab looks empty, I want to see every email that
arrived and what happened to it, so that I can tell "nothing arrived" from
"nothing matched".

**Preconditions** — At least one poll has run.

**Acceptance Criteria**
- **AC1** — *Given* mail has been seen, *when* I open the Logs tab, *then* every
  inbound email is listed with a status, including skipped ones.
- **AC2** — *Given* a skipped email, *when* I look at its row, *then* the reason
  reads "Sender not on whitelist."
- **AC3** — *Given* a failed email, *when* I look at its row, *then* the error
  detail is shown.
- **AC4** — *Given* many rows, *when* I filter by status, *then* only matching
  rows are listed.
- **AC5** — *Given* a completed email, *when* I look at its row, *then* I see
  the matched rule and the processing time.

**Main Flow**
1. **[EXT]** `GET /api/v1/auto-reply/logs` with filters.
2. **[BE]** Applies sender/status/date filters; paginates.
3. **[EXT]** Renders rows with status badges.

**Alternative Flow** — **A1** No logs at all: empty state indicating no mail has
been seen yet (check the connection and the poll interval).

**Error Cases** — Backend unreachable → error state with Retry. Invalid status
filter → validation error surfaced.

**Post Conditions** — None; read-only.

**Dependencies** — US-01.

---

### US-13 · Monitor volume and failures

| | |
|---|---|
| **ID** | US-13 |
| **Priority** | P2 |

**Description**
As a **user**, I want an at-a-glance view of what the assistant has been doing,
so that I can tell whether it is healthy and worth its API cost.

**Preconditions** — Backend reachable.

**Acceptance Criteria**
- **AC1** — *Given* activity in the window, *when* I open the Dashboard, *then*
  I see inbound total, matched, unmatched, drafts generated, failures and
  average processing time.
- **AC2** — *Given* I change the time window, *when* the query reruns, *then*
  every figure recomputes for that window.
- **AC3** — *Given* whitelisted senders have written, *when* I look at Top
  senders, *then* the counts reconcile with **Matched** — the two use the same
  filter by construction.
- **AC4** — *Given* a rule has since been deleted, *when* I look at the window
  in which it was active, *then* the mail it processed is **still counted**.
- **AC5** — *Given* no activity, *when* I open the Dashboard, *then* zeros are
  shown rather than an error.

**Main Flow**
1. **[EXT]** `GET /api/v1/auto-reply/dashboard/summary?since_hours=24`.
2. **[BE]** Runs eight aggregate queries over `match_logs`,
   `generated_drafts` and `whitelist_entries`.
3. **[EXT]** Renders stat cards, breakdown bar and top-sender list.

**Alternative Flow** — **A1** Window widened to a year (8760 h): the same
queries run over a larger range.

**Error Cases** — `since_hours` outside 1–8760 → 422. Backend unreachable →
error state.

**Post Conditions** — None; read-only.

**Dependencies** — US-01.

---

### US-14 · Be told about new mail while the panel is closed

| | |
|---|---|
| **ID** | US-14 |
| **Priority** | P2 |

**Description**
As a **user** who does not keep the panel open, I want the toolbar icon to tell
me when new mail has been processed, so that I know when it is worth looking.

**Preconditions** — Extension installed; backend reachable.

**Acceptance Criteria**
- **AC1** — *Given* mail has been processed since I last looked, *when* the
  background check runs, *then* the toolbar icon shows that count.
- **AC2** — *Given* the count has **increased** and notifications are on, *when*
  the check runs, *then* one desktop notification is shown.
- **AC3** — *Given* the count has not increased, *when* the check runs again,
  *then* the same backlog is **not** re-announced.
- **AC4** — *Given* I open the Inbox tab, *when* the list renders, *then* the
  badge clears and the watermark advances.
- **AC5** — *Given* I set the interval to 5 minutes, *when* I save, *then* the
  alarm is rescheduled without reloading the extension.
- **AC6** — *Given* notifications are off, *when* new mail is processed, *then*
  the badge still updates but no notification appears.

**Main Flow**
1. **[EXT/worker]** Alarm fires; settings and watermark are read from storage
   (the worker starts cold every time).
2. **[EXT/worker]** `GET /auto-reply/inbox?since=<lastSeenAt>` via plain
   `fetch`.
3. **[EXT/worker]** Sets the badge to `total`.
4. **[EXT/worker]** If `total` exceeds the persisted high-water mark and
   notifications are on, notifies and advances the mark.

**Alternative Flow**
- **A1 — Fresh install.** One immediate check on install so a badge can appear
  without waiting out an interval.
- **A2 — Interval changed.** A storage-change listener reschedules; the alarm is
  only rewritten when the period actually differs, because unconditional
  rewriting restarts the countdown and a frequently-woken worker would never
  reach its own deadline.

**Error Cases**
| Case | Handling |
|---|---|
| Backend unreachable | The badge is **left as-is**. Clearing it would claim there is nothing new, which is not what we know |
| Interval below 1 minute | Clamped — Chrome refuses shorter alarms |
| Worker terminated | Nothing is lost; state lives in `chrome.storage` and every top-level statement is idempotent |

**Post Conditions** — Badge reflects unseen count; the high-water mark prevents
duplicate notifications.

**Dependencies** — US-08.

---

### US-15 · Point the extension at my backend

| | |
|---|---|
| **ID** | US-15 |
| **Priority** | P1 |

**Description**
As a **user** whose backend is not on the default address, I want to change and
verify the backend URL, so that the panel is not silently dead.

**Preconditions** — Extension installed.

**Acceptance Criteria**
- **AC1** — *Given* Settings is open, *when* I edit the URL, *then* a Save
  button appears only once the value actually differs.
- **AC2** — *Given* a URL, *when* I click **Test**, *then* I see whether the
  backend responded, what status it returned, or that nothing answered.
- **AC3** — *Given* a URL outside the granted origins, *when* I type it, *then*
  I am warned that the extension may only reach `localhost:8000` and
  `127.0.0.1:8000`, and that anything else needs a manifest change and a rebuild.
- **AC4** — *Given* I save a new URL, *when* the panel reloads data, *then* the
  cached data from the previous backend is **discarded**, not revalidated.
- **AC5** — *Given* I click Reset to defaults, *when* it completes, *then* every
  setting returns to its default and the cache is cleared.

**Main Flow**
1. **[EXT]** User edits the URL; the panel validates the scheme.
2. **[EXT]** Test issues a raw `fetch` to `<draft URL>/health` — deliberately
   the draft URL, since the shared client reads the saved one.
3. **[EXT]** Save writes to `chrome.storage.local`, clears the query cache, and
   the worker's storage listener picks the change up.

**Alternative Flow** — **A1** Invalid URL: Save and Test are disabled and the
field is marked invalid.

**Error Cases**
| Case | Handling |
|---|---|
| No response | "No response — backend not running, or origin not permitted." Both causes look identical to the browser, so both are named |
| Non-2xx | The status code is shown |
| Origin not in `host_permissions` | Amber warning (AC3) |

**Post Conditions** — Settings persist per device. The backend never learns
about them.

**Dependencies** — None.

---

### US-16 · Have replied mail retire itself

| | |
|---|---|
| **ID** | US-16 |
| **Priority** | P1 |

**Description**
As a **user** who has answered an email, I want it to leave the Inbox view, so
that the list shows only what still needs me.

**Preconditions** — A connected account; a processed email whose thread I have
since replied on.

**Acceptance Criteria**
- **AC1** — *Given* I reply on a processed thread, *when* the next poll runs,
  *then* that email is stamped as replied.
- **AC2** — *Given* an email is stamped replied, *when* I open the Inbox tab,
  *then* it is no longer listed.
- **AC3** — *Given* I typed the reply **by hand** instead of using the draft,
  *when* the poll runs, *then* it is stamped just the same — detection is based
  on sent mail, not on our draft.
- **AC4** — *Given* an email is stamped replied, *when* I open the Logs tab,
  *then* the record is still there with its original outcome.
- **AC5** — *Given* an email is stamped replied, *when* I look at the Dashboard,
  *then* its original status still counts — replying does not rewrite what our
  processing did.

**Main Flow**
1. **[GMAIL]** User sends a reply on the thread.
2. **[BE]** Next poll lists sent thread ids since the watermark.
3. **[BE]** Stamps `replied_at` on every matching `match_log`.
4. **[EXT]** The next inbox query excludes it (`include_replied` defaults false).

**Alternative Flow** — **A1** Reply sent from another client/device: still
detected, because detection reads the mailbox, not the app.

**Error Cases**
| Case | Handling |
|---|---|
| Sweep fails | **Swallowed and logged.** Bookkeeping must never abort a poll — an email lingering one more interval is far better than new mail not being fetched |
| Reply sent between polls | Caught by the next sweep; the window overlaps deliberately |

**Post Conditions** — `replied_at` is set; `status` is unchanged; the row leaves
the Inbox view but is retained everywhere else.

**Dependencies** — US-08.

---

## 🛠 Story dependency graph

```
US-15 (backend URL) ─── independent, unblocks everything in practice
US-01 (connect) ──┬── US-02 (status/disconnect)
                  ├── US-12 (logs)
                  └── US-13 (dashboard)
US-03 (add rule) ─┬── US-04 (quick add)
                  ├── US-05 (import)
                  ├── US-06 (edit)
                  └── US-07 (delete)
US-01 + US-03 ────── US-08 (process) ──┬── US-09 (read summary) ── US-10 (open draft)
                                       ├── US-11 (rescan)
                                       ├── US-14 (badge/notify)
                                       └── US-16 (retire replied)
```

---

# 8. User Flows

## 👤 Flow 1 — First-time setup

```
Install extension
      │
      ▼
Start backend  ──► not running? ──► Settings ▸ Test ──► "No response"
      │
      ▼
Open Gmail ▸ click toolbar icon ──► side panel opens
      │
      ▼
Settings ▸ Connect Gmail
      │
      ▼
Google consent (new tab) ──► "unverified app"? ──► Advanced ▸ Go to… (expected in Testing mode)
      │
      ▼
"Gmail connected"  ──► close tab
      │
      ▼
Panel shows Connected + four tabs
      │
      ▼
Whitelist ▸ add your first sender
      │
      ▼
Wait one poll interval (60s) ──► Inbox shows the email + summary
                                 Gmail shows the draft on the thread
```

**If the Inbox stays empty:** open **Logs**. The sender is almost certainly not
whitelisted — skipped rows record exactly that.

---

## 👤 Flow 2 — Daily use

```
Badge shows "3"
      │
      ▼
Click icon ▸ Inbox tab (badge clears)
      │
      ▼
Expand an email
      │
      ├── Read overview, key points, action items
      │
      ▼
Click "Check draft" ──► Gmail opens on that thread
      │
      ├── Draft looks right ──► edit lightly ──► Send        ─┐
      ├── Draft is wrong    ──► rewrite or delete it          │
      └── Reply by hand ignoring the draft                    │
                                                              ▼
                                          Next poll stamps it replied
                                                              │
                                                              ▼
                                          Email leaves the Inbox view
                                          (still visible in Logs)
```

---

## 👤 Flow 3 — Whitelisting the sender you are reading

```
Reading a thread in Gmail
      │
      ▼
Open panel ▸ Whitelist tab
      │
      ▼
Suggestion row shows that thread's sender
      │
      ▼
Click it ──► the address fills the input (not submitted)
      │
      ▼
Check the inferred type   email → just this person
                          domain → EVERYONE at that domain
      │
      ▼
Add ──► 201, rule active
      │
      ▼
Want their earlier mail handled too?
      │
      ├── No  ──► done; future mail is processed
      └── Yes ──► Rescan ──► 202 ──► watch Logs
```

---

## 🛠 Flow 4 — Data flow: one whitelisted email, end to end

```
 GMAIL                BACKEND                                       LLM         DB
   │
   │  messages.list(after=watermark, max=25)
   │◄────────────────── poller
   │  ids ─────────────► buffer
   │  messages.get(id)
   │◄──────────────────
   │  payload ─────────► parse → InboundEmailEvent
                              │
                         worker.receive()
                              │
                         sanitize_sender ──► invalid? drop (warning only)
                              │
                         dedupe on gmail_message_id ──────────────────► SELECT
                              │
                         create MatchLog (pending) ───────────────────► INSERT
                              │
                         MatcherTool.match (60s TTL cache) ──────────► SELECT
                              │
                    ┌─────────┴──────────┐
              no match                 match
                    │                    │
        status=SKIPPED               status=PROCESSING ──────────────► UPDATE
        "Sender not on whitelist"        │
        ■ zero LLM cost                  │
                                    summarize ──────────────► Groq ──► (fail) Gemini
                                         │◄─── SummarizationResult
                                         │
                                    persist summary_json ───────────► UPDATE  ★ first
                                         │
                                    route ──────────────────► Groq ──► Gemini ──► mock
                                         │◄─── template_id, extracted_data, confidence
                                         │
                                    confidence < 0.6? ──► GENERAL_GREETING, used_fallback
                                         │
                                    compose ────────────────► Groq ──► Gemini
                                         │◄─── draft text (cleaned)   (no mock; falls
                                         │                             back to template)
                                    store GeneratedDraft v1 ────────► INSERT  ★ second
                                         │
   │  drafts.create(raw, threadId,       │
   │                In-Reply-To,         │
   │                References)          │
   │◄────────────────────────────────────┘
   │  draft id ─────────► store gmail_draft_id ─────────────────────► UPDATE  ★ third
                              │
                         status=COMPLETED + processing_ms ──────────► UPDATE
```

**★ The ordering is deliberate.** Summary before draft, draft before Gmail. The
generated text is the expensive artefact and must survive Gmail being
unreachable; the reverse order risks an orphan draft in the mailbox with no row
pointing at it.

---

## 🛠 Flow 5 — Data flow: panel read path

```
Side panel (open)                     Backend                    SQLite
      │
      │ every 30s: GET /auto-reply/inbox?page=1&page_size=25
      │────────────────────────────────►│
      │                                 │ WHERE status != skipped
      │                                 │   AND replied_at IS NULL
      │                                 │ selectinload(drafts)   ← one extra
      │                                 │────────────────────────► query, not N
      │◄────────────────────────────────│
      │ items[] each carrying: log + summary + latest_draft + draft_count
      │
      ▼
 Render cards ──► expand ──► SummaryView + DraftSection
                                  │
                                  └─► window.open(gmail thread url)
```

```
Service worker (panel closed)
      │
      │ chrome.alarms fires (≥1 min)
      ▼
 read settings + lastSeenAt from chrome.storage   ← cold start every time
      │
      │ GET /auto-reply/inbox?since=<lastSeenAt>     (plain fetch, no axios)
      ▼
 setBadgeText(total)
      │
      └─ total > highWaterMark && notificationsEnabled ──► notify, advance mark
```

---

## 🛠 Flow 6 — Failure and recovery paths

```
                    ┌─────────────────────────────┐
                    │  _execute_core throws       │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┴────────────────────┐
      SummarizationError                        any other Exception
              │                                          │
      retryable AND retry_count < 3?             retry_count < 3?
         │            │                            │           │
        yes           no                          yes          no
         │            │                            │           │
      re-raise    status=FAILED                re-raise   status=FAILED
         │        "Summarization error: …"         │       "Internal error: …"
         ▼                                         ▼
   ┌──────────────────────────────────────────────────────┐
   │  Retry queue — exponential backoff 1s, 2s, 4s        │
   │  max 3 attempts, then dropped with an error log      │
   └──────────────────────────────────────────────────────┘

  Gmail draft creation failure is NOT in this diagram — it is swallowed.
  Status stays COMPLETED, gmail_draft_id is null, and the panel says so.
  Rationale: the LLM has already been paid for; re-running would re-bill it.
```

---

# 9. Technical Notes

## 🛠 Design decisions and their reasons

### D1 — The extension never talks to Gmail

**Decision.** All Gmail access is server-side. The extension requests no Gmail
permissions and holds no Google tokens.

**Why.** The backend must poll and draft while the panel is closed, so it needs
credentials regardless. Giving the extension a second copy would double the
attack surface for no capability gain, and would force every user through
Chrome's Gmail-permission prompt. It also means reinstalling the extension never
touches your Google account.

**Cost.** The panel cannot show anything the backend has not already fetched.

---

### D2 — `chrome.sidePanel`, not an injected DOM sidebar

| | Native side panel | Injected sidebar |
|---|---|---|
| Breaks when Gmail's DOM changes | Never | Constantly |
| CSS collisions | None | Needs Shadow DOM + reset |
| Survives Gmail SPA navigation | Automatic | Needs a `MutationObserver` |
| `chrome.*` API access | Direct | Via message passing |
| Overlays Gmail's content | No | Yes |

**Why it applies here specifically.** Because polling is server-side, the panel
mostly renders backend data. It barely needs Gmail's DOM, so the main
justification for DOM injection evaporates. Requires Chrome 114+.

---

### D3 — Polling, not Gmail push

**Decision.** An interval poll with an in-memory buffer.

**Why.** Push (`users.watch` + Pub/Sub) needs a public HTTPS endpoint and a
Google Cloud Pub/Sub topic — impossible for a localhost MVP. The buffer exists
because the worker calls `receive()` in a tight loop; calling Gmail at that rate
would exhaust quota in minutes.

**Cost.** Latency up to one interval. Quota spent even when nothing arrived.

---

### D4 — Summary persisted as JSON, not normalised

**Decision.** `match_logs.summary_json` holds the whole `SummarizationResult`.

**Why.** It is read as a whole and never queried by field, and its shape is owned
by a Pydantic model that would otherwise force a schema migration on every new
field. `model_dump(mode="json")` is used so datetimes and enums become
JSON-native.

**Cost.** No SQL querying inside a summary; readers must handle null.

---

### D5 — `replied_at` is a column, not an `ExecutionStatus`

**Decision.** Replying is recorded separately from processing status.

**Why.** `status` records how *our* processing ended and stays meaningful
afterwards. A reply is a later, independent fact. Folding it into the enum would
overwrite the outcome and skew every status breakdown that counts it.

---

### D6 — Rescan is explicit, never automatic

**Decision.** Only `POST /api/v1/whitelist/rescan` starts a sweep.

**Why.** A sweep re-fetches from Gmail, spends LLM calls and files **real drafts
in the user's mailbox**. That is far too much to happen as a side effect of
typing an address into a form — and a bulk import of 300 rules would fire it
against the entire lookback window at once.

**Implementation.** A boolean flag, not a queue of ids, so repeated clicks
collapse into one sweep. The sweep re-reads the whitelist when it *runs*, so it
always uses current rules rather than a snapshot from request time.

---

### D7 — The draft text is not shown in the panel

**Decision.** `DraftSection` shows that a draft exists, which template was used
and which provider wrote it — but never the text.

**Why.** The draft is a real Gmail draft. A second editable copy in the panel
invites editing the one that is never sent. Reducing the panel's job to "say a
draft was made, and get you to it" removes an entire class of confusion.

---

### D8 — Errors degrade in layers

```
Summarization :  Groq → Gemini → typed error → retry queue → FAILED
Routing       :  Groq → Gemini → mock (only when no keys) → schema fallback
                                                          → confidence fallback
Drafting      :  Groq → Gemini → static template  (never fails)
Gmail draft   :  swallowed — the row completes without a draft link
Reply sweep   :  swallowed — bookkeeping must not abort a poll
```

**The rule:** the further a failure is from the expensive work, the more
aggressively it is swallowed. Losing a summary is worth a retry; losing a draft
*link* is not worth re-billing three LLM calls.

---

### D9 — Two error shapes, normalised once

The backend genuinely returns two shapes:

```
Summarization / routing / validation → { request_id, code, message, retryable }
auto_reply routers (HTTPException)   → { detail: "…" }
```

`services/errors.ts` collapses both into one `ApiError`. Retry policy reads the
backend's own `retryable` flag rather than inventing a client-side rule — the
backend already decided.

---

### D10 — Confidence threshold at 0.6

Below `CONFIDENCE_THRESHOLD`, routing degrades to `GENERAL_GREETING` and
`used_fallback` is set. The frontend mirrors the constant so meters colour
against the real value rather than a hardcoded guess. Both must be changed
together.

---

### D11 — No `tabs` permission

"Check draft" uses `window.open`, which needs no permission. Reusing the already
open Gmail tab would require `tabs`, which re-prompts **every installed user** on
update with a "Read your browsing history" warning. Not worth it for a
convenience link.

---

### D12 — `#all/` in the Gmail deep link

`#inbox/<id>` lands on an empty view when the thread has been archived; `#all/`
resolves either way. `/u/0/` is the only account selector Gmail supports —
addressing by email address appears to work but was always undocumented and
Google broke it in April 2026 (a fragment on such a URL fails with "Temporary
Error (404)"). Do not reintroduce it.

---

### D13 — Synchronous orchestrator dispatched to a thread

`EmailOrchestrator.run()` is synchronous and makes two blocking LLM calls.
Called directly it would block the event loop for several seconds, freezing the
background worker *and* every API request the panel makes, since they share one
loop. `asyncio.to_thread` isolates it.

---

### D14 — CORS is `*`, deliberately and temporarily

Unpacked extensions get a new origin on every reload, so the origin cannot be
pinned during development. There is no auth and no cookie to protect, and
browsers reject `*` together with credentials — hence
`allow_credentials=False`. **Both must be tightened before any deployment.**

---

## 🛠 API reference (current)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | `{"status":"ok"}` |
| `POST` | `/api/v1/summaries` | Summarize a message or thread |
| `POST` | `/api/v1/drafts` | Route + draft from a `SummarizationResult` |
| `GET` | `/api/v1/whitelist` | `?page`, `?page_size` (≤100), `?entry_type` |
| `POST` | `/api/v1/whitelist` | `{ value }` → **201** |
| `GET` | `/api/v1/whitelist/{id}` | |
| `PUT` | `/api/v1/whitelist/{id}` | Partial; **400** on empty body |
| `DELETE` | `/api/v1/whitelist/{id}` | Soft delete → **204** |
| `POST` | `/api/v1/whitelist/import` | multipart CSV/XLSX → per-row report |
| `POST` | `/api/v1/whitelist/rescan` | → **202** |
| `GET` | `/api/v1/auto-reply/inbox` | `?since`, `?page`, `?page_size`, `?include_skipped`, `?include_replied` |
| `GET` | `/api/v1/auto-reply/logs` | `?sender_filter`, `?status_filter`, `?date_from`, `?date_to` |
| `GET` | `/api/v1/auto-reply/status/{log_id}` | |
| `GET` | `/api/v1/auto-reply/drafts/{draft_id}` | |
| `GET` | `/api/v1/auto-reply/logs/{log_id}/drafts` | Version history, oldest first |
| `GET` | `/api/v1/auto-reply/dashboard/summary` | `?since_hours` (1–8760, default 24) |
| `POST` | `/api/v1/gmail/incoming` | Push an event → **202**; **429** if the queue is full |
| `GET` | `/api/v1/gmail/auth/start` · `/callback` · `/status` | |
| `DELETE` | `/api/v1/gmail/auth/` | → **204** |

Interactive docs at `/docs` while the backend runs.

### Status codes the UI handles

| Code | Source | UI response |
|---|---|---|
| 400 | empty `PUT` body | Prevented client-side; Save stays disabled |
| 404 | entry / draft / log not found | Refresh the list |
| 409 | duplicate whitelist value | Inline field error, input preserved |
| 413 | input too large | Non-retryable notice |
| 422 | validation | Show `detail` verbatim |
| 429 | push queue full | Toast, back off |
| 502 | `routing_unavailable` | Retry button |
| 503 | not configured | Banner: provider or OAuth not configured |

---

## 🛠 Configuration reference

Set in `backend/.env`. Defaults live in `backend/src/config.py`.

| Variable | Default | Effect |
|---|---|---|
| `GROQ_API_KEY` | — | Primary LLM. Without it, routing uses `mock` and drafting uses static templates |
| `GROQ_MODEL` | — | Required alongside the key — no default model |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | — / `gemini-2.5-flash` | Optional fallback |
| `GOOGLE_CLIENT_ID` / `_SECRET` | — | Required for Gmail. Add by hand — not in `.env.example` |
| `GOOGLE_REDIRECT_URI` | `http://localhost:8000/api/v1/gmail/auth/callback` | Must match the registered URI **exactly**, including port |
| `GMAIL_POLL_INTERVAL_SECONDS` | `60` | ≥15. Spends Gmail quota |
| `GMAIL_POLL_QUERY` | `in:inbox -in:chats` | Any Gmail search expression |
| `GMAIL_INITIAL_LOOKBACK_MINUTES` | `60` | How far back the **first** poll looks |
| `GMAIL_MAX_RESULTS_PER_POLL` | `25` | 1–100. Stops a backlog stampeding |
| `CONFIDENCE_THRESHOLD` | `0.6` | Below this, routing degrades to the safe template |
| `WHITELIST_CACHE_TTL_SECONDS` | `60` | Explains the stale-match window |
| `WHITELIST_RESCAN_LOOKBACK_HOURS` | `24` | 0 disables rescanning |
| `AUTO_REPLY_MAX_RETRIES` | `3` | Transient failures only |
| `AUTO_REPLY_RETRY_DELAY_SECONDS` | `1.0` | Base for exponential backoff |
| `SUMMARIZER_MAX_MESSAGES` | `20` | Per request |
| `SUMMARIZER_MAX_NORMALIZED_CHARS` | `100000` | Beyond this, input is truncated |
| `BULK_IMPORT_MAX_ROWS` | `10000` | Per file |
| `DATABASE_URL` | `sqlite+aiosqlite:///./email_assistant.db` | |

Settings are cached; **restart the backend after editing `.env`.**

---

## 🛠 Running and testing

```bash
# Backend
cd backend
cp .env.example .env        # then add GROQ_API_KEY, GROQ_MODEL, Google creds
uv sync --group dev
uv run uvicorn src.main:app --reload    # keep it on port 8000

# Frontend
cd frontend
npm install
npm run dev                 # writes dist/ and watches
# chrome://extensions ▸ Developer mode ▸ Load unpacked ▸ frontend/dist
```

**Tests**

```bash
cd backend
uv run pytest tests/auto_reply tests/test_models.py
```

Tests use fake model providers and never call an external API. The gated live
provider check needs real keys:

```bash
RUN_LIVE_MODEL_TESTS=1 uv run pytest -m live
```

> **Known issue.** `uv run pytest` over the whole suite fails to *collect*
> `tests/test_api.py` and `tests/test_service.py` — two `conftest.py` files
> collide on module name. Run the paths above until that is untangled.

---

# 10. Limitations

## 👤 Limitations you will notice

| Limitation | What it means for you |
|---|---|
| **One Gmail account** | Connecting a second replaces the first. |
| **Only whitelisted senders** | Everything else is ignored, by design. If the Inbox tab is empty, check Logs. |
| **Up to a minute of delay** | Polling is every 60 seconds by default. |
| **A new rule is not retroactive** | Press **Rescan** for mail that already arrived (last 24 h only). |
| **The draft cannot be edited in the panel** | Edit it in Gmail, where you will send it. |
| **No regenerate button** | If a draft is wrong, rewrite it in Gmail. |
| **Mail with no text fails** | Image-only mail, calendar invites and some HTML newsletters show up red in Logs. |
| **Three reply styles only** | Tech support, pricing enquiry, general greeting. |
| **Static fallback is Vietnamese** | When the AI cannot write the reply, the canned sentence is Vietnamese regardless of the email's language. |
| **Multi-account Chrome users** | "Check draft" opens whichever Google account signed in first, which may not be the connected one. |
| **Quick-add depends on Gmail's HTML** | Google can change it without notice, and the suggestion silently stops appearing. |
| **Chrome only, 114+** | The side panel API requires it. |

## 🛠 Limitations that constrain development

### Security — read before deploying anywhere

This runs on `localhost`. Three things make it unsafe elsewhere:

1. **Every API endpoint is unauthenticated.** Anyone who can reach the URL can
   read every stored summary, edit the whitelist, or disconnect the account.
2. **The Gmail refresh token is stored in plaintext** in `email_assistant.db`.
   It grants continuing mailbox access until revoked. Treat that file as a
   secret — it is gitignored, and must never be copied off the machine.
3. **CORS is `allow_origins=["*"]`** (see D14).

Revoke access at any time, independently of this app:
<https://myaccount.google.com/permissions>

### Scale

| Constraint | Detail |
|---|---|
| **Single worker only** | The whitelist match cache is per-process. `uvicorn --workers 2` makes caches diverge for up to 60 s. |
| **Retry queue is in memory** | A restart loses pending retries. |
| **Rescan flag is module state** | Same — it does not survive a restart, and does not work across processes. |
| **SQLite** | Fine for one user; no concurrent-writer story. |
| **Inbox `total` is counted in Python** | The result set is materialised to be counted. Fine at MVP volume; replace with `COUNT` before it is not. |
| **Panel cache is not persisted** | Closing the side panel discards TanStack's in-memory cache; reopening refetches. |

### Cost

Each whitelisted email costs **three LLM calls** (summarize, route, compose).
Senders matching no rule cost nothing. A free-tier Groq key will hit rate limits
on a busy inbox — keep the whitelist narrow while testing. There is no
rate-limit-aware backoff in the pipeline today, and
`status_breakdown.rate_limited` can never be set.

### Known dead code and gaps

| Item | State |
|---|---|
| `StatusBreakdown.rate_limited` | Always `0` — no such `ExecutionStatus` member |
| `GeneratedDraft` versioning | Schema supports it; nothing creates version 2 |
| `MatchLog.retry_count`, `sender_name`, `gmail_thread_id` | Exist on the model, omitted from the logs response |
| `extracted_data` | Stored, never exposed by the draft API |
| Whole-suite `pytest` collection | Broken by colliding `conftest.py` module names |
| Frontend `blockedReason` on tabs | All `null` now; the mechanism remains for future gaps |

---

# 11. Future Improvements

Ordered by the value-to-effort ratio as the system stands today.

## Near term

| # | Improvement | Why it matters | Notes |
|---|---|---|---|
| 1 | **Reclassify body-less mail as `SKIPPED`** | A live inbox shows red `FAILED` rows for calendar invites and image-only mail, which reads as a broken system | `InvalidEmailContentError` is already non-retryable; only the terminal status changes |
| 2 | **`POST /logs/{id}/regenerate`** | The single most-requested missing button. Versioning already exists in the schema | Reuses `_execute_core`; increments `version` |
| 3 | **Surface capability flags on `/health`** | Silent `mock` output is the most confusing failure mode in the product | Return `has_groq` / `has_gemini` / `has_google_oauth`; the panel warns |
| 4 | **Fix whole-suite test collection** | Backend changes are currently made against a partially-collected suite | Rename or namespace the colliding `conftest.py` files |
| 5 | **Translate the static fallback templates** | An English email that falls back gets a Vietnamese sentence | Key the catalog by language, defaulting to `summary.language` |
| 6 | **Real `rate_limited` status** | Free-tier keys hit limits routinely and it currently looks like a generic failure | Add the enum member; the dashboard field is already waiting |

## Medium term

| # | Improvement | Why it matters | Notes |
|---|---|---|---|
| 7 | **Authentication on every endpoint** | The first thing that must exist before this leaves localhost | `services/api/` mirrors routers 1:1, so the client change is one interceptor |
| 8 | **Encrypt tokens at rest** | The refresh token is the crown jewel of this system | Envelope encryption with a key outside the DB |
| 9 | **Split the whitelist flag in two** | The list currently means both "summarise" and "auto-draft", and those sets genuinely diverge — you would summarise your boss but never auto-reply to them | Two booleans on `WhitelistEntry`, **not** two tables |
| 10 | **User-defined templates** | Three hardcoded categories will not survive real use | Move `TEMPLATE_CATALOG` into the database |
| 11 | **Persist the retry queue** | Restarts currently lose in-flight work | A `pending_retries` table, drained on startup |
| 12 | **Generate frontend types from OpenAPI** | `types/api.ts` is hand-mirrored and will drift | The mirroring comments already name every Python source |

## Longer term

| # | Improvement | Why it matters |
|---|---|---|
| 13 | **Gmail push (`users.watch` + Pub/Sub)** | Removes polling latency and quota burn entirely — needs a public HTTPS endpoint |
| 14 | **Multi-account and multi-user** | Drop the unique `provider` constraint; give every whitelist entry and match log an owner. Larger than it looks |
| 15 | **Shared cache (Redis)** | Prerequisite for running more than one worker |
| 16 | **Attachment understanding** | Metadata is already carried; content is never read |
| 17 | **Learning from edits** | Diff the sent message against the generated draft to improve future drafts — the highest-value idea in this table, and the hardest |
| 18 | **Postgres** | When SQLite's single-writer model becomes the bottleneck |

---

# 12. Glossary

Terms are used consistently throughout this document and in the code.

| Term | Meaning |
|---|---|
| **Whitelist** | The set of rules deciding which senders are processed. One list; matching it means both "summarise" and "draft a reply". |
| **Entry / Rule** | One whitelist row. Either an **exact email** rule or a **domain** rule. |
| **Entry type** | `email` or `domain`, **inferred** from a leading `@` — never chosen from a dropdown. |
| **Match** | A sender satisfying a rule. Exact email always beats domain. |
| **Match log** | One row per inbound email ever seen, whatever happened to it. The unit the Logs tab lists. |
| **Execution status** | `pending` · `processing` · `completed` · `failed` · `skipped`. How *our processing* ended. |
| **Skipped** | The sender matched no rule. The normal, intended outcome for most mail. Costs nothing. |
| **Failed** | Processing was attempted and did not finish. Most often an email with no readable text. |
| **Replied** | The user answered on this thread, detected from **sent mail** — so hand-typed replies count. Recorded separately from status, and retires the email from the Inbox view. |
| **Summary** | The structured `SummarizationResult`: overview, cited key points, action items, detected language. Stored as `summary_json`. |
| **Key point** | A claim from the summary, carrying the message ids it came from. Up to seven per summary. |
| **Action item** | A task from the summary, optionally with an owner and a deadline. |
| **Truncated** | The original was too long to read in full; some of it was not seen by the model. |
| **Routing** | The LLM step that classifies the email into a template and extracts fields. |
| **Template** | One of `TECH_SUPPORT`, `PRICING_INQUIRY`, `GENERAL_GREETING`. |
| **Confidence score** | The router's own certainty, 0–1. Below `0.6` the system degrades to the safe template. |
| **Fallback (`used_fallback`)** | True when the generic template was substituted — because validation failed or confidence was too low. |
| **Drafting / Compose** | The LLM step that writes the actual reply text, in the email's own language. |
| **Draft** | The generated reply. Stored in the database **and** filed in Gmail. Never sent. |
| **Gmail draft id** | Gmail's id for the filed draft. The *draft* id, not its message id — Gmail replaces the message and its id on every edit, so only this one stays valid. |
| **Provider** | Which model produced a result: `groq`, `gemini`, or `mock`. |
| **Mock** | A keyword-based router used when no API keys are configured. Lets the pipeline run end to end without spending quota. Reports a hardcoded confidence of `0.85`. |
| **Poll** | The backend asking Gmail for new mail. Default every 60 s. |
| **Watermark (`last_polled_at`)** | The instant the last poll started. Only mail after it is considered new. |
| **Lookback** | How far back the *first* poll after connecting looks. Default 60 minutes. |
| **Rescan** | An explicitly requested sweep re-examining recently skipped mail against current rules. |
| **Retry queue** | In-memory queue for transient failures, with exponential backoff, up to 3 attempts. |
| **Side panel** | The native Chrome panel that is the product's UI. Requires Chrome 114+. |
| **Service worker** | The extension's MV3 background script. Runs the badge and notifications; terminated after ~30 s idle. |
| **Content script** | The tiny read-only script on Gmail pages that notices which thread is open. |
| **Badge** | The count on the toolbar icon: emails processed since you last opened the Inbox tab. |
| **Backend** | The FastAPI service. The only component holding Google credentials. |
| **Guardrails** | Pure validation functions: address/domain validation, sender sanitization, import row checks, prompt-injection patterns. |

---

*This document describes the current MVP only. Anything not listed under
[6. Feature Specifications](#6-feature-specifications) is not implemented — see
[11. Future Improvements](#11-future-improvements) for what is planned and
[10. Limitations](#10-limitations) for what is deliberately out of scope.*
