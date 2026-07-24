# AI Email Assistant — System Architecture

> **Project version:** backend `0.2.0`, extension `0.1.0`  
> **Last verified:** 2026-07-24  
> **Scope:** current single-user, localhost MVP

## 1. Architecture summary

AI Email Assistant is a Chrome Manifest V3 side-panel extension backed by a
local FastAPI service. The backend owns Gmail OAuth, polls for new messages,
applies whitelist rules, runs the AI pipeline, stores an audit trail, and
creates reply drafts through the Gmail API. The extension is a presentation and
notification client; it does not receive Google tokens or call the Gmail API.

The system is intentionally human-in-the-loop:

> The terminal automated action is creating a draft. There is no email-send
> path in the application.

## 2. System context

```text
 External sender                                              User
       │                                                       │
       │ sends email                                           │ reviews /
       ▼                                                       │ sends manually
┌───────────────────────┐                                      │
│ Gmail API and mailbox │◄─────────────────────────────────────┘
└───────────┬───────────┘
            │ OAuth 2.0, read mail, detect replies, create drafts
            │
┌───────────┴────────────────── LOCAL FASTAPI BACKEND ────────────────┐
│                                                                    │
│  ┌──────────────┐    ┌────────────────┐    ┌───────────────────┐   │
│  │ REST API     │    │ Background     │    │ Auto-reply        │   │
│  │              │◄───│ worker/poller  │───►│ workflow          │   │
│  └──────┬───────┘    └────────────────┘    └─────────┬─────────┘   │
│         │                                            │             │
│         │              ┌──────────────────────┐      │             │
│         └─────────────►│ SQLite               │◄─────┤             │
│                        │ rules, logs, drafts, │      │             │
│                        │ summaries, OAuth     │      │             │
│                        └──────────────────────┘      │             │
│                                                     ▼             │
│                                       ┌────────────────────────┐  │
│                                       │ Summarizer → Router →  │  │
│                                       │ Drafter                │  │
│                                       └───────────┬────────────┘  │
└───────────────────────────────────────────────────┼────────────────┘
                                                    │
                                        ┌───────────▼───────────┐
                                        │ Groq primary          │
                                        │ Gemini fallback/only  │
                                        └───────────────────────┘

┌──────────────────────── CHROME EXTENSION ──────────────────────────┐
│  ┌──────────────┐  ┌────────────────┐  ┌───────────────────────┐  │
│  │ React side   │  │ MV3 service    │  │ Gmail content script  │  │
│  │ panel        │  │ worker         │  │ open sender only      │  │
│  └──────┬───────┘  └───────┬────────┘  └───────────┬───────────┘  │
│         └───────────────────┼───────────────────────┘              │
│                             ▼                                      │
│                   ┌──────────────────────┐                         │
│                   │ chrome.storage.local │                         │
│                   └──────────────────────┘                         │
└───────────────┬───────────────────┬────────────────────────────────┘
                │ REST / JSON       │ badge and notification queries
                └───────────────────┴────────────► FastAPI REST API
```

### Component responsibilities

| Component | Responsibilities | Does not do |
|---|---|---|
| **Side panel** | Inbox, Dashboard, Whitelist, Logs, Settings; REST calls; local UI state | Read Gmail directly or store OAuth tokens |
| **Service worker** | Chrome alarm, badge count, desktop notifications | Run the backend polling loop or use Axios |
| **Content script** | Read the sender from the Gmail thread currently open for whitelist quick-add | Read message bodies or modify Gmail |
| **FastAPI API** | Health, OAuth, whitelist, inbox, logs, dashboard, low-level summary/draft APIs | Render the product UI |
| **Background worker** | Drain retries and explicit rescans, poll Gmail, pass inbound events to the workflow | Run safely across multiple backend processes |
| **AutoReplyWorkflow** | Sanitize, enforce idempotency, match whitelist, coordinate AI, persist results, file Gmail draft | Send email |
| **SQLite** | Store rules, processing history, summaries, drafts, and OAuth credentials | Encrypt OAuth credentials |
| **Gmail API** | List and retrieve messages, identify sent threads, create drafts | Decide whitelist or AI behavior |
| **Model providers** | Structured summarization, routing, and response composition | Access Gmail or the database |

## 3. Deployment and runtime topology

The MVP runs on one machine:

```text
┌──────────────────────────── USER WORKSTATION ───────────────────────────┐
│                                                                        │
│  ┌──────────────────── CHROME 114+ ───────────────────┐                 │
│  │                                                    │                 │
│  │  ┌──────────────────┐      ┌───────────────────┐  │                 │
│  │  │ Unpacked MV3     │      │ mail.google.com   │  │                 │
│  │  │ extension        │      │ Gmail UI          │  │                 │
│  │  └────────┬─────────┘      └─────────┬─────────┘  │                 │
│  └───────────┼───────────────────────────┼────────────┘                 │
│              │ HTTP REST                 │ HTTPS                        │
│              ▼                           │                              │
│  ┌──────────────────────────┐             │                              │
│  │ Uvicorn / FastAPI       │             │                              │
│  │ localhost:8000          │             │                              │
│  └────────────┬─────────────┘             │                              │
│               │                           │                              │
│               ▼                           │                              │
│  ┌──────────────────────────┐             │                              │
│  │ backend/                │             │                              │
│  │ email_assistant.db      │             │                              │
│  └──────────────────────────┘             │                              │
└───────────────┬───────────────────────────┼──────────────────────────────┘
                │ HTTPS                     │ HTTPS
        ┌───────▼────────┐          ┌───────▼────────────────┐
        │ Groq / Gemini  │          │ Google OAuth and       │
        │ model APIs     │          │ Gmail API              │
        └────────────────┘          └────────────────────────┘
```

Three independent clocks affect what the user sees:

| Clock | Location | Default | Purpose |
|---|---|---:|---|
| Gmail discovery | Backend poller | 60 seconds | Find incoming mail and sent replies |
| Open-panel refresh | React Query | 30 seconds | Refresh Inbox and Dashboard data |
| Closed-panel check | Chrome alarm | 5 minutes | Update badge and notifications |

The Chrome alarm has a one-minute platform floor. In the normal open-panel demo,
allow up to roughly one Gmail poll plus one panel refresh.

## 4. Inbound email processing

### Main sequence

```text
┌─────────────────────────────────────────────────────────────────────┐
│ 1. DISCOVER                                                        │
│                                                                     │
│  ┌───────────┐  list IDs after watermark  ┌─────────────────────┐  │
│  │ Gmail API │◄────────────────────────────│ Gmail poller        │  │
│  └─────┬─────┘────────────────────────────►└──────────┬──────────┘  │
│        │          message IDs                         │             │
│        └──── get each message, oldest first ──────────┘             │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │ InboundEmailEvent
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. RECORD AND DECIDE                                                │
│                                                                     │
│  ┌───────────────────┐     ┌─────────────────────┐                  │
│  │ Background worker │────►│ AutoReplyWorkflow   │                  │
│  └───────────────────┘     └──────────┬──────────┘                  │
│                                       │                             │
│                          ┌────────────▼────────────┐                 │
│                          │ Check message ID and   │                 │
│                          │ create MatchLog        │                 │
│                          └────────────┬────────────┘                 │
│                                       ▼                             │
│                          ┌─────────────────────────┐                 │
│                          │ Whitelist matcher       │                 │
│                          │ exact address → domain  │                 │
│                          └──────┬───────────┬──────┘                 │
│                                 │ no match  │ match                  │
│                                 ▼           ▼                        │
│                         ┌─────────────┐  ┌──────────────┐            │
│                         │ SKIPPED     │  │ PROCESSING   │            │
│                         │ no AI call  │  └──────┬───────┘            │
│                         └─────────────┘         │                    │
└────────────────────────────────────────────────┼────────────────────┘
                                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. GENERATE, STORE, AND FILE                                        │
│                                                                     │
│  ┌────────────┐    ┌────────┐    ┌─────────┐    ┌───────────────┐  │
│  │ Summarizer │───►│ Router │───►│ Drafter │───►│ SQLite        │  │
│  └────────────┘    └────────┘    └─────────┘    │ summary+draft │  │
│                                                 └───────┬───────┘  │
│                                                         ▼          │
│  ┌──────────────┐   create draft in original thread  ┌──────────┐  │
│  │ COMPLETED    │◄────────────────────────────────────│ Gmail API│  │
│  └──────────────┘          Gmail draft ID             └──────────┘  │
└─────────────────────────────────────────────────────────────────────┘

After a successful poll, the poller advances the watermark in SQLite.
```

### Processing rules

1. **Input normalization:** Gmail data is converted to an
   `InboundEmailEvent`.
2. **Sender guardrail:** the sender is normalized and validated.
3. **Idempotency:** `gmail_message_id` is unique. A replay returns the existing
   log rather than paying for the work twice.
4. **Audit-first:** a `MatchLog` is created before whitelist evaluation.
5. **Whitelist gate:** an exact email rule has precedence over a domain rule.
6. **No-match path:** the log becomes `skipped`; no model call is made.
7. **Match path:** the system summarizes, routes, and composes.
8. **Persistence before Gmail:** the expensive summary and generated text are
   stored before the system asks Gmail to create the draft.
9. **Human review:** the created draft remains unsent in the original thread.

### AI pipeline

```text
┌──────────────────┐  LLM operation 1  ┌──────────────────────────────┐
│ Normalized email │───────────────────►│ Structured summary           │
└──────────────────┘                    │ overview, key points, actions│
                                        │ language, source citations   │
                                        └──────────────┬───────────────┘
                                                       │
                                         LLM operation 2
                                                       ▼
                                        ┌──────────────────────────────┐
                                        │ Routing result               │
                                        │ template, extracted data,    │
                                        │ confidence                   │
                                        └───────┬───────────────┬──────┘
                                                │               │
                                  valid and     │               │ invalid or
                                  confident     │               │ low confidence
                                                ▼               ▼
┌──────────────────────────────┐  operation 3  ┌───────────┐  ┌──────────────┐
│ Summary supplies the context│───────────────►│ LLM draft │  │ Static safe  │
└──────────────────────────────┘                └─────┬─────┘  │ template     │
                                                     │        └──────▲───────┘
                                                     │ compose       │
                                                     │ failure ──────┘
                                                     ▼
                                              ┌────────────┐
                                              │ Reply body │
                                              └────────────┘
```

A matched message normally uses three logical model operations:

1. **Summarization** produces structured, source-cited context.
2. **Routing** selects one of the current templates:
   `TECH_SUPPORT`, `PRICING_INQUIRY`, or `GENERAL_GREETING`.
3. **Composition** writes a short reply in the detected language.

Groq is attempted first when configured. Gemini can act as its fallback or as
the sole provider. The summarizer owns its retry/fallback logic. Routing
validates model output with Pydantic and uses a generic template when output is
invalid or confidence is below the configured threshold. Composition falls
back to deterministic template rendering if the model call or output cleaning
fails.

The email subject and body are treated as untrusted model input. The
summarization prompt explicitly rejects instructions embedded in email content,
does not claim to read attachment contents, and requires source message IDs for
key points and action items.

## 5. Status and recovery model

```text
                          no whitelist match
                    ┌────────────────────────► ┌─────────┐
                    │                          │ SKIPPED │
                    │                          └─────────┘
              ┌─────┴───┐
   start ────►│ PENDING │
              └─────┬───┘
                    │ whitelist matched
                    ▼
              ┌────────────┐ ◄──── retry attempt ────┐
              │ PROCESSING │ ────────────────────────┘
              └─────┬──────┘
                    │
          ┌─────────┴───────────────┐
          │ artifacts persisted     │ terminal generation error
          ▼                         ▼
   ┌───────────┐              ┌────────┐
   │ COMPLETED │              │ FAILED │
   └─────┬─────┘              └────────┘
         │
         │ Gmail filing may still have failed after the generated
         │ text was stored. In that case gmail_draft_id is null.
         ▼
   ┌──────────────────────────────────────────────────────────────┐
   │ Processing outcome remains COMPLETED; Inbox shows a warning.│
   └──────────────────────────────────────────────────────────────┘
```

`replied_at` is deliberately separate from processing status. A completed email
can later be marked replied when the Gmail poller sees a sent message on the
same thread. This keeps the original processing outcome for reporting while
removing dealt-with mail from the default Inbox view.

### Failure behavior

| Failure | Behavior |
|---|---|
| Sender is not whitelisted | Store `skipped`; make no model call. |
| Primary summarizer has a retryable error | Retry inside the service, then try the configured fallback. |
| Routing output is invalid or low confidence | Use `GENERAL_GREETING` and mark fallback. |
| Draft composition fails | Render a deterministic template instead. |
| Gmail draft creation fails | Keep summary and generated text; complete with `gmail_draft_id = null`; show a warning in Inbox. |
| Gmail poll fails | Record poller error and back off; the worker continues running. |
| One Gmail message cannot be fetched | Log the failure and continue through the batch. |
| Reply-detection sweep fails | Keep processing new inbound mail; try reply detection on a later poll. |

The worker includes an exponential-backoff retry queue for transient workflow
failures. Before production use, the initial-processing transaction and retry
enqueue path should be hardened and covered by an integration test so a
rollback cannot remove the log that the retry lookup needs.

## 6. Backend module architecture

| Layer | Main locations | Role |
|---|---|---|
| Application entry | `backend/src/main.py` | FastAPI lifespan, routers, CORS, error handling, request IDs |
| Configuration | `backend/src/config.py` | Typed environment configuration and capability flags |
| Database | `backend/src/database.py` | Async engine, session lifecycle, first-run schema creation |
| API | `backend/src/auto_reply/api/` | Whitelist, Gmail auth, Inbox, Logs, Dashboard, draft status |
| Workflow | `backend/src/auto_reply/workflow/` | Main processing, polling loop, retry queue, explicit rescan |
| Gmail proxy | `backend/src/auto_reply/proxy/` | OAuth, Gmail HTTP client, poller, inbound adapter |
| Business tools | `backend/src/auto_reply/tools/` | Matching, whitelist rules, imports, stats, logs, draft storage |
| Persistence | `backend/src/auto_reply/infrastructure/` | SQLAlchemy models and repositories |
| Summarization | `backend/src/summarization/` | Preprocessing, provider abstraction, structured summary |
| Orchestration | `backend/src/orchestrator/` | Template routing, confidence gate, draft composition |
| Email templates | `backend/src/email_module/` | Template catalog, schemas, deterministic rendering |

The FastAPI process starts the database and one asyncio background worker in
its lifespan hook. The worker handles work in this order:

1. ready retry;
2. explicitly requested rescan;
3. manually pushed inbound event;
4. Gmail-polled event; and
5. a short idle sleep when no work exists.

The design assumes one backend process. In-memory OAuth state, whitelist cache,
rescan flag, Gmail buffer, and retry queue are not shared across processes.

## 7. Frontend architecture

| Area | Main locations | Role |
|---|---|---|
| Side-panel shell | `frontend/src/sidepanel/` | App root, tabs, header, query client |
| Feature views | `frontend/src/features/` | Inbox, Dashboard, Whitelist, Logs, Settings |
| API services | `frontend/src/services/` | Axios client for the panel, fetch client for the worker |
| Background worker | `frontend/src/background/` | Alarm, badge, notifications |
| Content script | `frontend/src/content/` | Read current Gmail sender for quick-add |
| State | `frontend/src/stores/` | Zustand UI and settings state |
| Local utilities | `frontend/src/utils/` | Storage, dates, badge, Gmail links, query keys |

TanStack Query owns remote server state. Zustand owns side-panel UI state and
settings. Persistent extension preferences live in `chrome.storage.local`.

Two Manifest V3 constraints shape the implementation:

- the background service worker uses `fetch`, because Axios expects
  `XMLHttpRequest`; and
- recurring work uses `chrome.alarms`, because `setInterval` does not survive
  service-worker suspension.

The extension requests `storage`, `sidePanel`, `alarms`, and `notifications`
permissions plus localhost host access. It does not request Gmail permissions.

## 8. Data architecture

```text
┌─────────────────────────┐   1       0..*   ┌─────────────────────────┐
│ WHITELIST_ENTRIES       │─────────────────►│ MATCH_LOGS              │
├─────────────────────────┤   matched by     ├─────────────────────────┤
│ id                  PK  │                  │ id                  PK  │
│ entry_type              │                  │ gmail_message_id    UK  │
│ value                   │                  │ gmail_thread_id         │
│ is_active               │                  │ whitelist_entry_id  FK  │
│ created_at              │                  │ sender_email            │
│ updated_at              │                  │ status                  │
└─────────────────────────┘                  │ summary_json            │
                                             │ received_at             │
                                             │ processed_at            │
                                             │ replied_at              │
                                             └────────────┬────────────┘
                                                          │ 1
                                                          │
                                                          │ 0..* versions
                                                          ▼
                                             ┌─────────────────────────┐
                                             │ GENERATED_DRAFTS        │
                                             ├─────────────────────────┤
                                             │ id                  PK  │
                                             │ match_log_id        FK  │
                                             │ version                 │
                                             │ draft_text              │
                                             │ template_id             │
                                             │ confidence_score        │
                                             │ provider_used           │
                                             │ used_fallback           │
                                             │ gmail_draft_id          │
                                             └─────────────────────────┘

┌─────────────────────────┐
│ OAUTH_CREDENTIALS       │   Standalone, single connected provider
├─────────────────────────┤
│ id                  PK  │
│ provider            UK  │
│ email_address           │
│ access_token            │
│ refresh_token           │
│ token_expiry            │
│ scopes                  │
│ last_polled_at          │
└─────────────────────────┘
```

Important storage decisions:

- Whitelist deletion is a soft delete so historical relationships remain
  meaningful.
- The summary is stored as JSON because it is read as one document and its
  model-owned shape can evolve without normalizing every field.
- Draft versions are unique per `(match_log_id, version)`.
- The Gmail draft ID is nullable because generation and Gmail filing are
  separate failure domains.
- `provider` is unique in the OAuth table, enforcing the one-connected-account
  MVP.

## 9. OAuth and trust boundaries

```text
┌──────────────┐                         ┌───────────────────┐
│ User browser │── GET /auth/start ─────►│ FastAPI backend   │
└──────────────┘                         └─────────┬─────────┘
                                                 │
                                    issue short-lived,
                                    one-time state
                                                 │
┌──────────────┐     redirect to consent         │
│ User browser │◄────────────────────────────────┘
└──────┬───────┘
       │ approve requested scopes
       ▼
┌──────────────────┐
│ Google OAuth     │
└──────┬───────────┘
       │ redirect with authorization code + state
       ▼
┌──────────────┐       GET /callback       ┌───────────────────┐
│ User browser │──────────────────────────►│ FastAPI backend   │
└──────────────┘                           └─────────┬─────────┘
                                                   │ validate and
                                                   │ consume state
                                                   ▼
                                          ┌───────────────────┐
                                          │ Google OAuth      │
                                          │ exchange code and │
                                          │ fetch account     │
                                          └─────────┬─────────┘
                                                    │ access token,
                                                    │ refresh token,
                                                    │ account email
                                                    ▼
                                          ┌───────────────────┐
                                          │ FastAPI backend   │
                                          └────┬─────────┬────┘
                                               │         │
                                    store      │         │ connection
                                    tokens     │         │ result page
                                               ▼         ▼
                                          ┌────────┐  ┌──────────────┐
                                          │ SQLite │  │ User browser │
                                          └────────┘  └──────────────┘
```

Requested Google scopes:

- `gmail.readonly` for polling and reply detection;
- `gmail.compose` for creating drafts; and
- `userinfo.email` for displaying the connected account.

### Security posture

The current MVP is suitable for localhost development and demonstration, not
public deployment:

- API endpoints are unauthenticated.
- CORS permits all origins for unpacked-extension development.
- Gmail access and refresh tokens are stored in plaintext SQLite.
- There is no tenant or user ownership column.
- In-memory OAuth state and worker coordination assume one process.

Before remote or multi-user deployment, add API authentication, per-user data
ownership, encrypted token storage, restricted CORS, centralized job state,
secret management, rate limiting, and production observability.

## 10. API surface

| Area | Endpoints |
|---|---|
| Health | `GET /health` |
| Gmail connection | `GET /api/v1/gmail/auth/start`, `/callback`, `/status`; `DELETE /api/v1/gmail/auth/` |
| Gmail ingestion | `POST /api/v1/gmail/incoming` |
| Whitelist | `GET/POST /api/v1/whitelist`; `GET/PUT/DELETE /api/v1/whitelist/{id}`; import and rescan |
| Product reads | Inbox, Logs, Dashboard summary, processing status, draft detail/history |
| Low-level AI APIs | `POST /api/v1/summaries`; `POST /api/v1/drafts` |

The live OpenAPI contract is available at
`http://127.0.0.1:8000/docs` while the backend is running.

## 11. Key architecture decisions

| Decision | Reason |
|---|---|
| Backend owns Gmail | Keeps credentials and mailbox logic out of the extension. |
| Side panel instead of injected sidebar | Uses Chrome’s supported UI surface and avoids modifying Gmail’s DOM. |
| Polling instead of Gmail push | Keeps the localhost MVP deployable without a public webhook or Pub/Sub setup. |
| Whitelist before AI | Makes processing opt-in and prevents model cost for unrelated mail. |
| Store before Gmail draft creation | Preserves the expensive generated artifact when Gmail is unavailable. |
| Never send | Keeps the user as the final reviewer and limits OAuth authority. |
| Exact sender before domain | Makes a specific rule more precise than a broad organization rule. |
| Summary feeds routing and drafting | Avoids repeatedly passing raw email into later stages and preserves structured context. |
| `replied_at` separate from status | Records a later mailbox event without erasing the processing outcome. |

## 12. Current constraints and evolution

| Current constraint | Production direction |
|---|---|
| One user and one Gmail account | Add users, account ownership, and tenant isolation |
| One FastAPI process | Move polling, retries, and rescans to a durable job queue |
| SQLite | Move to a managed relational database |
| Polling latency | Consider Gmail push notifications and Pub/Sub |
| Three fixed routing templates | Add user-owned policy and template management |
| No attachment-content analysis | Add a sandboxed extraction pipeline with explicit consent |
| Local metrics only | Add structured logs, traces, provider cost, and alerting |
| Unencrypted OAuth tokens | Encrypt with a managed key and support rotation |

## 13. Related documents

- [Demo Guide](../demo.md)
- [Gmail OAuth Setup](../setup/gmail-oauth.md)
- [Frontend Implementation Plan](frontend-plan.md)
- [Project README](../../README.md)
