/**
 * Boundary types, hand-mirrored from the backend (version 0.2.0).
 *
 * These are *assertions*, not validations — nothing checks at runtime that a
 * response really has this shape. Each block names the Python source it mirrors
 * so the two can be diffed when the backend changes.
 *
 * Verified against a running server, not just read from the source.
 */

// ---------------------------------------------------------------------------
// Enums — src/auto_reply/infrastructure/models.py
// ---------------------------------------------------------------------------

/** Declared as arrays so filter tabs can iterate them at runtime. */
export const EXECUTION_STATUSES = [
  'pending',
  'processing',
  'completed',
  'failed',
  'skipped',
] as const
export type ExecutionStatus = (typeof EXECUTION_STATUSES)[number]

export const ENTRY_TYPES = ['email', 'domain'] as const
export type EntryType = (typeof ENTRY_TYPES)[number]

/**
 * Not DB-enforced — the column is `String(100)`. Constrained in practice by the
 * orchestrator's TemplateID enum.
 */
export const TEMPLATE_IDS = [
  'TECH_SUPPORT',
  'PRICING_INQUIRY',
  'GENERAL_GREETING',
] as const
export type TemplateId = (typeof TEMPLATE_IDS)[number]

/** `mock` is the keyword router used when no API keys are configured. */
export const PROVIDERS = ['groq', 'gemini', 'mock'] as const
export type Provider = (typeof PROVIDERS)[number]

// ---------------------------------------------------------------------------
// Pagination — shared by the whitelist and log routers
// ---------------------------------------------------------------------------

export type Paginated<T> = {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** `page_size` is capped at 100 by `Query(..., le=100)` on both routers. */
export const MAX_PAGE_SIZE = 100

// ---------------------------------------------------------------------------
// Whitelist — src/auto_reply/api/whitelist_router.py
// ---------------------------------------------------------------------------

export type WhitelistEntry = {
  id: number
  /** Inferred from the value by the backend; never sent by the client. */
  entry_type: EntryType
  value: string
  created_at: string
}

export type WhitelistEntryCreate = {
  /** A leading `@` makes it a domain rule; anything else is an exact email. */
  value: string
}

/**
 * Partial by design. Sending `{}` is a **400** (`exclude_unset` on the backend),
 * so only ever send fields that actually changed — `updateWhitelistEntry`
 * rejects an empty patch before it reaches the network.
 *
 * Changing `value` re-infers `entry_type`, which can silently widen a
 * single-address rule into a whole-domain one.
 */
export type WhitelistEntryUpdate = {
  value?: string
}

// ---------------------------------------------------------------------------
// Bulk import — src/auto_reply/tools/bulk_import_tool.py
// ---------------------------------------------------------------------------

export type ImportRowError = {
  /** 1-based *including* the header row, so the first data row is 2. */
  row_index: number
  raw_value: string
  errors: string[]
}

export type BulkImportReport = {
  total_rows: number
  inserted: number
  skipped_duplicates: number
  validation_errors: ImportRowError[]
  warnings: string[]
}

// ---------------------------------------------------------------------------
// Match logs — src/auto_reply/api/log_router.py
// ---------------------------------------------------------------------------

/**
 * Note what is *absent*: the ORM model has `sender_name`, `gmail_thread_id` and
 * `retry_count`, but this response omits all three. The logs list can only show
 * raw email addresses; `retry_count` needs the per-log status endpoint.
 */
export type MatchLog = {
  id: number
  gmail_message_id: string
  sender_email: string
  subject: string | null
  whitelist_entry_id: number | null
  /** The matched whitelist value, denormalised. Null when nothing matched. */
  matched_rule: string | null
  status: ExecutionStatus
  error_detail: string | null
  processing_ms: number | null
  /** Naive ISO-8601 (no offset) — parse with `parseApiDate`, never `new Date`. */
  received_at: string
  processed_at: string | null
}

export type LogQueryParams = {
  page?: number
  page_size?: number
  sender_filter?: string
  status_filter?: ExecutionStatus
  /** ISO-8601. Also drives "what is new since I last looked". */
  date_from?: string
  date_to?: string
}

/** `GET /auto-reply/status/{log_id}` — an untyped dict on the backend. */
export type ProcessingStatus = {
  log_id: number
  status: ExecutionStatus
  retry_count: number
  error_detail: string | null
  processing_ms: number | null
}

// ---------------------------------------------------------------------------
// Drafts — src/auto_reply/api/draft_router.py
// ---------------------------------------------------------------------------

/**
 * The ORM model also carries `extracted_data`, which this response does not
 * expose.
 */
export type GeneratedDraft = {
  id: number
  match_log_id: number
  /** 1 is the first generation; later versions come from regeneration. */
  version: number
  draft_text: string
  template_id: TemplateId
  /** Compare against `CONFIDENCE_THRESHOLD`, not a hardcoded number. */
  confidence_score: number
  provider_used: Provider
  /** True when confidence fell short and a canned template was substituted. */
  used_fallback: boolean
  created_at: string
}

// ---------------------------------------------------------------------------
// Summaries — src/summarization/models.py::SummarizationResult
// ---------------------------------------------------------------------------

/** A claim backed by the messages it came from. */
export type CitedItem = {
  text: string
  source_message_ids: string[]
}

export type ActionItem = {
  task: string
  owner: string | null
  deadline: string | null
  source_message_ids: string[]
}

/**
 * Stored on `match_logs.summary_json` once the email is summarised.
 *
 * Note `language` is the language of the *original email*, which drives what
 * language the draft is written in. The summary prose itself is not guaranteed
 * to be in that language.
 */
export type EmailSummary = {
  overview: string
  key_points: CitedItem[]
  action_items: ActionItem[]
  language: string
  request_id: string
  source_message_ids: string[]
  omitted_message_ids: string[]
  /** True when the original was too long and got cut before summarising. */
  truncated: boolean
}

// ---------------------------------------------------------------------------
// Inbox — src/auto_reply/api/inbox_router.py
// ---------------------------------------------------------------------------

export type InboxDraft = {
  id: number
  version: number
  draft_text: string
  template_id: TemplateId
  confidence_score: number
  provider_used: Provider
  used_fallback: boolean
  created_at: string
  /** Gmail's id for the filed draft. Null when the row predates draft creation,
   *  or Gmail was unreachable at the time. */
  gmail_draft_id: string | null
}

/** Log + summary + latest draft in one row — deliberately avoids an N+1. */
export type InboxItem = {
  id: number
  gmail_message_id: string
  gmail_thread_id: string | null
  sender_email: string
  sender_name: string | null
  subject: string | null
  matched_rule: string | null
  status: ExecutionStatus
  error_detail: string | null
  received_at: string
  processed_at: string | null
  /** Null when skipped, failed early, or processed before summaries persisted. */
  summary: EmailSummary | null
  latest_draft: InboxDraft | null
  draft_count: number
}

// ---------------------------------------------------------------------------
// Dashboard — src/auto_reply/tools/stats_tool.py
// ---------------------------------------------------------------------------

/**
 * `rate_limited` is dead: `ExecutionStatus` has no such member, so the backend
 * can never increment it. Always 0 today. Do not render it as a status until
 * the backend grows that state.
 */
export type StatusBreakdown = {
  pending: number
  processing: number
  completed: number
  failed: number
  skipped: number
  rate_limited: number
}

export type TopSender = {
  sender: string
  count: number
}

/**
 * There is deliberately no "summarized" count — summaries are not persisted, so
 * the backend cannot compute one. Use `total_drafts_generated` instead.
 *
 * Unlike every other timestamp in the API, `since`/`until` *are* offset-aware
 * (they are built in Python, not read back from SQLite). `parseApiDate` handles
 * both.
 */
export type DashboardSummary = {
  since: string
  until: string
  total_inbound_emails: number
  matched_whitelist: number
  unmatched: number
  total_drafts_generated: number
  failed_generation: number
  avg_processing_ms: number | null
  status_breakdown: StatusBreakdown
  active_whitelist_entries: number
  top_senders: TopSender[]
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

export type HealthResponse = {
  status: string
}

// ---------------------------------------------------------------------------
// Error payloads — the backend returns TWO different shapes
// ---------------------------------------------------------------------------

/**
 * Shape A — `src/summarization/models.py::ErrorResponse`.
 * Emitted by the summarization, routing and request-validation handlers.
 * `retryable` is the backend's own judgement; the client must not second-guess
 * it.
 */
export type BackendErrorResponse = {
  request_id: string
  code: string
  message: string
  retryable: boolean
}

/**
 * Shape B — FastAPI's `HTTPException`, used throughout the auto_reply routers.
 * The string is written for humans (guardrail messages) and is safe to show
 * verbatim.
 *
 * `detail` is an array only for FastAPI's built-in validation errors, which
 * this backend intercepts and re-emits as shape A — handled defensively anyway.
 */
export type BackendDetailResponse = {
  detail: string | unknown[]
}

// ---------------------------------------------------------------------------
// Config mirrored from src/config.py — keep in sync
// ---------------------------------------------------------------------------

/** Routing below this degrades to the fallback template. */
export const CONFIDENCE_THRESHOLD = 0.6

/** Explains why a whitelist edit can take up to a minute to take effect. */
export const WHITELIST_CACHE_TTL_SECONDS = 60

export const AUTO_REPLY_MAX_RETRIES = 3

export const BULK_IMPORT_MAX_ROWS = 10_000
