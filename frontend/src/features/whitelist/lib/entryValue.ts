/**
 * Client-side mirror of `backend/src/auto_reply/agent/guardrails.py`.
 *
 * The panel shows the inferred rule type as you type, so this has to agree with
 * the server exactly — a hint that says "Domain rule" followed by a 422 is
 * worse than no hint. The regexes below are ported character-for-character from
 * `_EMAIL_RE` and `_DOMAIN_RE`, and a test harness runs the same vectors
 * through both implementations.
 *
 * **Keep in sync with the Python.** If a guardrail changes there, change it
 * here in the same commit.
 */

import type { EntryType } from '@/types/api'

const EMAIL_RE =
  /^[a-zA-Z0-9.!#$%&'*+\/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/

const DOMAIN_RE =
  /^@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z]{2,})+$/

const MAX_EMAIL_LENGTH = 320
const MAX_DOMAIN_LENGTH = 255

export type ValueInference =
  | { kind: 'empty' }
  | {
      kind: 'valid'
      entryType: EntryType
      /** Lowercased and trimmed, exactly as the backend will store it. */
      normalized: string
      hint: string
    }
  | { kind: 'invalid'; entryType: EntryType; message: string }

/**
 * A leading `@` is the entire type-inference rule — the same branch the backend
 * takes in `validate_whitelist_value`.
 */
export function inferEntryType(raw: string): EntryType {
  return raw.trim().startsWith('@') ? 'domain' : 'email'
}

/** Normalisation the backend applies before storing or comparing. */
export function normalizeValue(raw: string): string {
  return raw.trim().toLowerCase()
}

/** Everything the QuickAdd bar and inline editor need to describe a value. */
export function inspectValue(raw: string): ValueInference {
  const stripped = raw.trim()
  if (!stripped) return { kind: 'empty' }

  const normalized = normalizeValue(stripped)
  const entryType = inferEntryType(stripped)

  if (entryType === 'domain') {
    if (normalized.length > MAX_DOMAIN_LENGTH) {
      return {
        kind: 'invalid',
        entryType,
        message: `Domain entry exceeds ${MAX_DOMAIN_LENGTH} characters.`,
      }
    }
    if (!DOMAIN_RE.test(normalized)) {
      return {
        kind: 'invalid',
        entryType,
        message: `'${stripped}' is not a valid domain entry. Use the format '@domain.com'.`,
      }
    }
    return {
      kind: 'valid',
      entryType,
      normalized,
      hint: `Domain rule — matches everyone at ${normalized.slice(1)}.`,
    }
  }

  if (normalized.length > MAX_EMAIL_LENGTH) {
    return {
      kind: 'invalid',
      entryType,
      message: `Email address exceeds ${MAX_EMAIL_LENGTH} characters.`,
    }
  }
  if (!EMAIL_RE.test(normalized)) {
    return {
      kind: 'invalid',
      entryType,
      message: `'${stripped}' is not a valid email address.`,
    }
  }
  return {
    kind: 'valid',
    entryType,
    normalized,
    hint: 'Exact address — matches this one sender.',
  }
}
