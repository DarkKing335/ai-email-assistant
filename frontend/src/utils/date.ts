/**
 * Timestamp handling for the API boundary.
 *
 * The backend is inconsistent about timezone offsets, and the inconsistency is
 * invisible until times are displayed:
 *
 *   logs.received_at    '2026-07-19T17:13:03.463397'         ← no offset
 *   dashboard.since     '2026-07-12T17:15:32.477385+00:00'   ← offset
 *
 * SQLite has no timezone type, so `DateTime(timezone=True)` hands back naive
 * datetimes and `.isoformat()` drops the offset. Values computed in Python
 * (`datetime.now(UTC)`) keep theirs.
 *
 * `new Date()` interprets an offset-less string as **local time**, so every log
 * timestamp would render shifted by the viewer's UTC offset — seven hours in
 * Vietnam — while dashboard values stayed correct. Parsing goes through
 * `parseApiDate`, never `new Date`, so the rule lives in one place.
 */

/** Trailing `Z`, `+07:00` or `+0700`. */
const HAS_UTC_OFFSET = /(?:Z|[+-]\d{2}:?\d{2})$/i

/** Parses an API timestamp, treating a missing offset as UTC. */
export function parseApiDate(value: string): Date {
  return new Date(HAS_UTC_OFFSET.test(value) ? value : `${value}Z`)
}

const ABSOLUTE_FORMAT = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

/** Full local date and time, for tooltips and detail rows. */
export function formatDateTime(value: string): string {
  return ABSOLUTE_FORMAT.format(parseApiDate(value))
}

const RELATIVE_FORMAT = new Intl.RelativeTimeFormat(undefined, {
  numeric: 'auto',
})

const DIVISIONS: { limit: number; seconds: number; unit: Intl.RelativeTimeFormatUnit }[] = [
  { limit: 60, seconds: 1, unit: 'second' },
  { limit: 3600, seconds: 60, unit: 'minute' },
  { limit: 86_400, seconds: 3600, unit: 'hour' },
  { limit: 604_800, seconds: 86_400, unit: 'day' },
  { limit: 2_629_800, seconds: 604_800, unit: 'week' },
  { limit: 31_557_600, seconds: 2_629_800, unit: 'month' },
]

/** "3 minutes ago", "yesterday". Falls back to an absolute date past a year. */
export function formatRelativeTime(value: string, now: Date = new Date()): string {
  const elapsedSeconds = (parseApiDate(value).getTime() - now.getTime()) / 1000
  const magnitude = Math.abs(elapsedSeconds)

  for (const { limit, seconds, unit } of DIVISIONS) {
    if (magnitude < limit) {
      return RELATIVE_FORMAT.format(Math.round(elapsedSeconds / seconds), unit)
    }
  }
  return formatDateTime(value)
}

/** ISO-8601 in UTC — the format the backend's `date_from`/`date_to` expect. */
export function toApiTimestamp(date: Date): string {
  return date.toISOString()
}
