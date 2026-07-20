# AI Email Assistant — Frontend Implementation Plan

> **Status:** Design — not yet implemented
> **Date:** 2026-07-19
> **Scope:** MVP Chrome Extension (Gmail sidebar)
> **Backend version:** 0.2.0

A Chrome Extension that surfaces the existing backend pipeline as an AI assistant
sidebar inside Gmail. Behaves like ChatGPT Sidebar / Grammarly — **not** a chatbot.

---

## Contents

1. [Reality check — what is blocked](#1-reality-check--what-is-blocked)
2. [System architecture](#2-system-architecture)
3. [Chrome extension architecture](#3-chrome-extension-architecture)
4. [Folder structure](#4-folder-structure)
5. [UI/UX and component hierarchy](#5-uiux-and-component-hierarchy)
6. [API integration design](#6-api-integration-design)
7. [State management](#7-state-management)
8. [Gmail integration](#8-gmail-integration)
9. [Gotchas](#9-gotchas)
10. [Roadmap](#10-roadmap--two-parallel-tracks)
11. [Scalability notes](#11-scalability-notes)
12. [Appendix — backend endpoint reference](#appendix--backend-endpoint-reference)

---

## 1. Reality check — what is blocked

Every planned sidebar feature, mapped against the **actual** backend:

| Sidebar section | Backend status |
|---|---|
| Whitelist | ✅ **Complete** — build today |
| Dashboard | ✅ **Works** — except a "summarized" count, which does not exist |
| Logs | ✅ **Complete** — build today |
| Settings | ✅ Client-side only |
| Notification / badge | ⚠️ Poll logs by `date_from`; no unread concept exists |
| **Email Summary** | ❌ **Not persisted — discarded after generation** |
| **Open Gmail Draft** | ❌ No OAuth, no `drafts.create`, no stored draft ID |
| **Regenerate draft** | ❌ No endpoint (DB versioning exists but is unexposed) |

### The summary is computed and thrown away

In `src/auto_reply/proxy/llm_adapter.py`:

```
summarize(email)          →  summary     ← full structured summary, right here
orchestrator.run(summary) →  draft
return draft                            ← only the draft comes back
```

`SummarizationResult` (overview, key points, action items, language) is a **local
variable that goes out of scope**. `DraftResult` does not carry it, and the
`generated_drafts` table has no column for it.

The centerpiece of the sidebar has no data source until this is fixed. It is
plumbing, not new capability — every whitelisted email already pays for that LLM
call.

### Cut from MVP

**"Summarize only whitelist" toggle.** There is no backend setting, and flipping
it means restructuring `AutoReplyWorkflow.process_initial()` to summarize
*before* whitelist matching. Hardcode it on.

### Start here

**Whitelist + Dashboard + Logs are fully buildable today** against endpoints that
already exist. Begin with those — visible progress while backend gaps close.

---

## 2. System architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CHROME EXTENSION (MV3)                                      │
│                                                              │
│  ┌────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │ Content    │   │  Service     │   │  Side Panel      │  │
│  │ Script     │   │  Worker      │   │  (React app)     │  │
│  │            │   │              │   │                  │  │
│  │ detect     │◄─►│ chrome.alarms│◄─►│ Dashboard        │  │
│  │ Gmail;     │   │ badge count  │   │ Inbox + Summary  │  │
│  │ quick-add  │   │ notifications│   │ Drafts           │  │
│  │ sender     │   │ (fetch only) │   │ Whitelist / Logs │  │
│  └────────────┘   └──────┬───────┘   └────────┬─────────┘  │
└──────────────────────────┼────────────────────┼────────────┘
                           │   REST + CORS      │
                    ┌──────▼────────────────────▼───────┐
                    │  FastAPI backend (localhost:8000) │
                    │  whitelist · logs · dashboard     │
                    │  summaries · drafts · inbox (new) │
                    └──────┬────────────────────────────┘
                           │ OAuth (server-side)
                    ┌──────▼────────────┐
                    │  Gmail API        │
                    │  poll · drafts.   │
                    │  create           │
                    └───────────────────┘
```

**Key principle: the extension never talks to Gmail's API.** The backend owns
OAuth, polling, and draft creation. The extension is a *view* over the database.
This is what the `auto_reply` background worker was built for.

### Pipeline (unchanged, server-side)

```
New email → whitelist match → summarize → generate draft
          → save Gmail draft → store summary → user reviews → user sends
```

---

## 3. Chrome extension architecture

### Use `chrome.sidePanel`, not an injected DOM sidebar

| | `chrome.sidePanel` (native) | Injected content-script sidebar |
|---|---|---|
| Gmail DOM changes break it | ❌ Never | ✅ Constantly |
| CSS collisions | None | Needs Shadow DOM + reset |
| Survives Gmail SPA navigation | Automatic | Needs MutationObserver |
| Full `chrome.*` API access | Direct | Via message passing |
| Build time | Low | High |
| Overlays Gmail content | No | Yes |

**Why this applies here specifically:** because the backend polls Gmail
server-side, the sidebar mostly *renders backend data*. It barely needs Gmail's
DOM, so the main justification for DOM injection evaporates.

ChatGPT's own Chrome extension uses the side panel. Requires **Chrome 114+**.
Set `sidePanel.setPanelBehavior({ openPanelOnActionClick: true })` so the toolbar
icon opens the panel.

**Keep a content script, but tiny:** detect `mail.google.com`, read the
currently-open sender for quick-add-to-whitelist. Nothing else.

**Skip the popup.** Two UIs doubles the work with no MVP benefit.

---

## 4. Folder structure

```
frontend/
├── public/icons/                    16/32/48/128 png
├── src/
│   ├── background/                  ── MV3 service worker
│   │   ├── index.ts                 registers alarms + listeners
│   │   ├── poller.ts                chrome.alarms → fetch new logs
│   │   ├── badge.ts                 chrome.action.setBadgeText
│   │   └── notifications.ts         chrome.notifications
│   │
│   ├── content/                     ── minimal, Gmail page only
│   │   ├── index.ts
│   │   └── readSender.ts            current thread sender → quick-add
│   │
│   ├── sidepanel/                   ── the product
│   │   ├── index.html
│   │   ├── main.tsx                 React root + QueryClientProvider
│   │   └── App.tsx                  nav shell + routing
│   │
│   ├── features/                    ── one folder per sidebar section
│   │   ├── dashboard/
│   │   │   ├── DashboardPanel.tsx
│   │   │   ├── components/StatCard.tsx
│   │   │   └── hooks/useDashboard.ts
│   │   ├── inbox/                   new emails + summaries list
│   │   ├── summary/
│   │   ├── draft/
│   │   ├── whitelist/
│   │   ├── logs/
│   │   └── settings/
│   │
│   ├── components/ui/               Button Badge Card Skeleton Empty Error
│   ├── layouts/                     PanelLayout SectionHeader ScrollArea
│   │
│   ├── services/
│   │   ├── http.ts                  axios instance  (PANEL ONLY)
│   │   ├── fetchClient.ts           fetch wrapper   (WORKER ONLY — see §9)
│   │   ├── errors.ts                normalize both backend error shapes
│   │   └── api/                     mirrors backend routers 1:1
│   │       ├── dashboard.ts   logs.ts    whitelist.ts
│   │       ├── drafts.ts      inbox.ts   summaries.ts
│   │
│   ├── stores/                      ── zustand: UI state ONLY
│   │   ├── uiStore.ts               activeTab, selectedLogId, theme
│   │   └── settingsStore.ts         hydrated from chrome.storage
│   │
│   ├── hooks/                       shared tanstack hooks
│   ├── types/api.ts                 hand-mirrored from Pydantic models
│   ├── utils/                       chromeStorage, format, queryKeys
│   └── styles/index.css             tailwind
│
├── manifest.config.ts               typed manifest (@crxjs)
├── vite.config.ts
└── package.json
```

**Use `@crxjs/vite-plugin`** — it handles MV3 HMR, which is otherwise painful.

### Stack

React · TypeScript · TailwindCSS · Vite · Zustand · TanStack Query · Axios ·
Manifest V3

---

## 5. UI/UX and component hierarchy

```
App
├── PanelHeader          "AI Email Assistant" · 3 new · ⚙
├── TabNav               Inbox │ Dashboard │ Whitelist │ Logs
└── <TabContent>
    │
    ├── InboxPanel                    ◄── DEFAULT TAB
    │   ├── NewCountBanner            "3 new emails"
    │   └── EmailCard[]               sender · subject · time
    │       └── (expand) SummaryView
    │           ├── OverviewBlock
    │           ├── KeyPointList      → cited message ids
    │           ├── ActionItemList    task · owner · deadline
    │           ├── LanguageBadge
    │           └── DraftSection
    │               ├── DraftPreview
    │               ├── ConfidenceMeter    ◄── color by threshold 0.6
    │               ├── FallbackWarning    ◄── if used_fallback
    │               ├── RegenerateButton
    │               └── OpenGmailDraftButton
    │
    ├── DashboardPanel
    │   ├── StatCardGrid    today · summarized · drafts · failed
    │   ├── StatusBreakdownBar
    │   └── TopSendersList
    │
    ├── WhitelistPanel
    │   ├── QuickAddBar      one input + live type hint
    │   ├── ImportCsvButton → ImportResultPanel
    │   └── EntryTable → EntryRow (inline edit)
    │
    └── LogsPanel
        ├── StatusFilterTabs   all │ completed │ failed │ skipped
        └── LogRow[]
```

### Three details grounded in the backend

- **ConfidenceMeter** — the threshold is `0.6` (`src/config.py`,
  `confidence_threshold`). Color the meter against that exact value.
- **FallbackWarning** — when `used_fallback: true`, the AI was not confident and
  degraded to `GENERAL_GREETING`. Say so plainly:
  *"Low confidence — generic template used."*
- **WhitelistQuickAdd** — one input, no type dropdown. Type is **inferred** from a
  leading `@` (`guardrails.validate_whitelist_value`). Show the inference live:
  typing `@fpt.edu.vn` → *"Domain rule — matches everyone at fpt.edu.vn."*

### Whitelist API quirks the UI must handle

| # | Behaviour | UI consequence |
|---|---|---|
| 1 | `PUT` returns **400** on an empty body (`exclude_unset`) | Send only changed fields; disable Save when unchanged |
| 2 | Editing `value` **re-infers the type** | Warn when `bob@x.com` → `@x.com` — it becomes a whole-domain rule |
| 3 | `DELETE` is soft (`is_active=False`), **no restore endpoint** | Do not offer Restore or a trash view |
| 4 | Re-adding a deleted value **reactivates the old row** and overwrites `priority` | "Delete → re-add" is not a clean slate |
| 5 | `409` duplicate / `422` validation | Surface `detail` verbatim — guardrail messages are user-readable |
| 6 | **Exact email always beats domain**, regardless of priority | Explain it inline, or users will set priority 999 on a domain and file a bug |
| 7 | Import returns a per-row report | Render a results panel, not a toast |
| 8 | `row_index` starts at 2 (row 1 = header) | Maps directly to spreadsheet row numbers — say "Row 47" |

CSV template columns: `value`, optional `priority`. Ship a downloadable sample.

---

## 6. API integration design

### The backend returns TWO error shapes

```
Summarization / LLM errors  →  { request_id, code, message, retryable }
Whitelist / draft errors    →  { detail: "..." }        ← FastAPI HTTPException
```

Normalize both in `services/errors.ts` into one `ApiError { code, message,
retryable, status }`. Never let raw shapes reach components.

### Status codes

| Code | Source | UI response |
|---|---|---|
| 409 | duplicate whitelist value | Inline field error |
| 422 | validation | Show `detail` verbatim |
| 429 | `/gmail/incoming` queue full | Toast, back off |
| 502 | `routing_unavailable` | Retry button |
| 503 | not configured / unavailable | Banner: "AI provider not configured" |
| 413 | input too large | Non-retryable notice |

### Retry strategy — driven by the backend's own flag

`ErrorResponse` carries `retryable: bool`. Wire TanStack Query directly to it:

```
retry: (failureCount, error) => error.retryable && failureCount < 2
```

Do not invent a client-side retry policy. The backend already decided.

### Polling — two independent clocks

| Context | Mechanism | Interval | Scope |
|---|---|---|---|
| Panel open | TanStack `refetchInterval` | 30s | inbox + dashboard only |
| Panel closed | `chrome.alarms` | **60s minimum** | badge count only |

MV3 enforces a ~1-minute alarm floor — clamp the Settings slider accordingly.

⚠️ This is the **client** refresh interval. The backend's Gmail poll is a
separate, more expensive interval. Label the setting "Refresh interval" to keep
them distinct.

### Query keys

```
['dashboard', sinceDays]
['inbox', sinceTimestamp]
['logs', { page, status, sender, dateFrom, dateTo }]
['draft', draftId]
['draftHistory', logId]
['whitelist', { page, entryType }]
```

Invalidate `['whitelist']` after every mutation — the backend clears its own
match cache, but the client cache is separate.

### Loading & empty states

Every panel needs three states beyond success: `Skeleton` (first load),
`EmptyState` (no data yet — common on a fresh DB), `ErrorState` (with a Retry
button gated on `retryable`).

---

## 7. State management

| Layer | Owns | Never holds |
|---|---|---|
| **TanStack Query** | All server data | UI state |
| **Zustand** | activeTab, selectedLogId, theme, panel state | Server data |
| **chrome.storage.local** | settings, `lastSeenAt`, apiBaseUrl | Anything transient |

Hydrate `chrome.storage` → zustand **once on boot**. Never read storage inside
components.

### Tracking "new" needs no backend work

Store `lastSeenAt` in `chrome.storage.local` → query logs with
`date_from=lastSeenAt` → advance it when the user views the Inbox tab. The badge
count is `total` from that response.

### Cache caveat

The side panel unmounts when closed, so TanStack's in-memory cache dies with it.
For MVP, accept the refetch. Do not build cache persistence.

---

## 8. Gmail integration

**Detect Gmail** — `content_scripts.matches: ["https://mail.google.com/*"]`. The
content script pings the worker; the worker enables the side panel for that tab.

**Open Gmail Draft** — requires backend work first: store the Gmail draft ID
returned by `drafts.create` on `match_logs` (new column). The button is then just
`chrome.tabs.create({ url })`.

> ⚠️ **Verify the deep-link format empirically before building on it.** Likely
> `https://mail.google.com/mail/u/0/#drafts/<messageId>` or `?compose=<draftId>`,
> but Gmail's URL scheme is not reliably documented. Test with a real draft ID
> early — 10 minutes, and it de-risks a demo-critical button.

**Notifications** — `chrome.notifications.create` from the worker when the alarm
finds new completed logs. Gate on the Settings toggle.

**Badge** — `chrome.action.setBadgeText`. Clear when the Inbox tab is viewed.

### Draft threading (backend)

A draft reply that is not threaded under the original conversation looks broken.
`drafts.create` needs **both**:

- `threadId` on the draft, and
- `In-Reply-To` + `References` headers matching the original `Message-ID`

`MatchLog.gmail_thread_id` already exists. The RFC-2822 `Message-ID` header does
**not** — `gmail_message_id` is Gmail's internal API ID, a different value. It
must be captured and stored.

### OAuth scope

Use consent screen **Testing** status with your own account as a test user — up
to 100 users, no review, no security assessment. An "unverified app" warning
appears; click through. Fine for a demo.

Verify the current classification of `gmail.compose` vs `gmail.modify` on
Google's docs before any thought of publishing — it decides the verification
cost. Irrelevant in testing mode.

---

## 9. Gotchas

**① Axios does not work in the MV3 service worker.**
Axios's browser build uses `XMLHttpRequest`, which does not exist in service
workers. Use axios in the side panel (normal document context) and plain `fetch`
in the worker. This is why `services/` has both `http.ts` and `fetchClient.ts`.

**② `setInterval` does not survive in the worker.**
MV3 service workers terminate after ~30s idle. Background polling **must** use
`chrome.alarms`.

**③ CORS with a moving extension ID.**
Unpacked extensions get a new ID on reload. Either pin it with a `key` in the
manifest, or for localhost MVP use `allow_origins=["*"]` with
`allow_credentials=False` (browsers reject `*` + credentials; there is no auth
anyway).

**④ `create_all` will not add new columns.**
`init_db()` calls `create_all`, which does **not** ALTER existing tables. Adding
`summary_json` / `gmail_draft_id` to an existing `email_assistant.db` produces
"no such column" errors. Delete the .db file, or write the Alembic migration
(alembic is already configured).

**⑤ Emails with no text body land as FAILED.**
`InvalidEmailContentError` is non-retryable, so `_execute_core` marks the log
`FAILED`. Image-only mail, calendar invites, and some HTML newsletters hit this.
A live inbox will show red rows during a demo. Consider marking them `SKIPPED`.

**⑥ The test suite is broken.**
Six modules import `app.summarization.*` but the package is `src.*` —
`uv run pytest` aborts during collection. Only the 12 `auto_reply` tests run. Fix
before touching backend code, or you are changing untested code.

**⑦ Each whitelisted email costs 2 LLM calls** (summarize + route). A free-tier
Groq key will hit RPM limits on a live inbox. `StatsTool.StatusBreakdown` already
has a dead `rate_limited` field — `ExecutionStatus` has no such value. It is
about to become useful.

---

## 10. Roadmap — two parallel tracks

The point of this ordering: **frontend never waits on backend.**

| Phase | 🔵 Backend track | 🟢 Frontend track |
|---|---|---|
| **0** | CORS + fix 6 broken test imports | Vite + React + TS + Tailwind + @crxjs scaffold |
| **1** | **`LLMDrafter`** ← highest value | Side panel shell, tab nav, `services/`, error normalizer |
| **2** | Persist summary → `match_logs.summary_json` | **Whitelist module** (works today — full CRUD + CSV) |
| **3** | `GET /inbox?since=` combined endpoint | **Dashboard + Logs** (both work today) |
| **4** | Gmail OAuth (testing mode, self as test user) | Settings + chrome.storage + zustand hydration |
| **5** | `drafts.create` + threading headers + store draft ID | Service worker: alarms, badge, notifications |
| **6** | `POST /logs/{id}/regenerate` (versioning already in DB) | **Inbox + Summary module** ← unblocked by Phase 2 |
| **7** | `summarized` count in StatsTool; revive `rate_limited` | **Draft module** ← unblocked by Phases 5–6 |
| **8** | — | Polish: empty / loading / error states, dark mode |
| **9** | — | End-to-end test on a real inbox |
| **10** | — | Demo prep: seed whitelist, stage emails, dry run |

### Critical path: `LLMDrafter`

"Generate Draft" can currently only emit **3 canned Vietnamese sentences** from
hardcoded templates (`src/email_module/templates.py`). Everything else can look
perfect and the demo will still fall flat.

The `Drafter` protocol in `src/orchestrator/contracts.py` exists exactly for
this: implement the interface, pass it to `EmailOrchestrator`, change nothing
else. Have it respect `summary.language`.

### If working solo

Phase 0 → 1 → 2 (backend), then 2 → 3 (frontend) for morale, then 4 → 5 (the
risky OAuth stretch), then 6 → 7.

### Avoid the N+1

`GET /inbox?since=` should return log + summary + latest draft id **in one
response**. Without it the extension makes 1 call for logs then N calls for
details — it will feel slow in the demo.

---

## 11. Scalability notes

Leave hooks for these; do not build them now.

- **The whitelist is overloaded.** It currently means both "auto-draft for these
  senders" and "summarize these senders." Those sets diverge — you would
  summarize your boss but never auto-reply to them. The future fix is two
  booleans on `WhitelistEntry`, not two tables.
- **The match cache is per-process.** `invalidate_whitelist_cache()` clears
  in-memory state only. Running `uvicorn --workers 2` makes caches diverge for up
  to 60s. Single worker for MVP; needs Redis to scale.
- **Auth is the first post-MVP addition.** Every endpoint is public. Fine on
  localhost, unacceptable deployed — anyone with the URL reads every stored email
  summary.
- **Keep `services/api/` mirroring backend routers 1:1.** Adding auth then means
  touching one interceptor, not 30 components.
- **Do not persist the TanStack cache yet.** Add it only if panel-reopen latency
  becomes a real complaint.

---

## Appendix — backend endpoint reference

Verified against the generated OpenAPI schema (backend 0.2.0).

| Method | Path | Notes |
|---|---|---|
| POST | `/api/v1/summaries` | Summarize a thread |
| POST | `/api/v1/drafts` | Route + draft; takes a full `SummarizationResult` |
| GET | `/api/v1/whitelist` | Paginated; `?page`, `?page_size` (≤100), `?entry_type` |
| POST | `/api/v1/whitelist` | `{ value, priority }` → 201 |
| GET | `/api/v1/whitelist/{id}` | |
| PUT | `/api/v1/whitelist/{id}` | Partial; **400 on empty body** |
| DELETE | `/api/v1/whitelist/{id}` | Soft delete → 204 |
| POST | `/api/v1/whitelist/import` | multipart CSV/Excel → per-row report |
| GET | `/api/v1/auto-reply/logs` | `?sender_filter`, `?status_filter`, `?date_from`, `?date_to` |
| GET | `/api/v1/auto-reply/status/{log_id}` | status, retry_count, error_detail, processing_ms |
| GET | `/api/v1/auto-reply/drafts/{draft_id}` | |
| GET | `/api/v1/auto-reply/logs/{log_id}/drafts` | Version history, oldest first |
| GET | `/api/v1/auto-reply/dashboard/summary` | `?since_days` (1–365, default 7) |
| POST | `/api/v1/gmail/incoming` | Push inbound email → 202; **429 if queue full** |
| GET | `/health` | |

### To be added

| Method | Path | Unblocks |
|---|---|---|
| GET | `/api/v1/auto-reply/inbox?since=` | Inbox module (avoids N+1) |
| POST | `/api/v1/auto-reply/logs/{id}/regenerate` | Regenerate button |

### Enums

```
ExecutionStatus : pending | processing | completed | failed | skipped
EntryType       : email | domain
TemplateID      : TECH_SUPPORT | PRICING_INQUIRY | GENERAL_GREETING
provider_used   : groq | gemini | mock
```

> `mock` is a keyword-based router used when no API keys are configured — useful
> for frontend development without burning quota.

### Config values the UI should mirror

| Setting | Default | Source |
|---|---|---|
| `confidence_threshold` | `0.6` | ConfidenceMeter coloring |
| `whitelist_cache_ttl_seconds` | `60` | Explains stale-match window |
| `auto_reply_max_retries` | `3` | Retry count display |
| `bulk_import_max_rows` | `10000` | Import file size warning |
