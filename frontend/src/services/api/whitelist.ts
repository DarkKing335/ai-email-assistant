/** Mirrors `src/auto_reply/api/whitelist_router.py`. */

import http from '@/services/http'
import { API_PREFIX } from '@/services/config'
import { clientError } from '@/services/errors'
import type {
  BulkImportReport,
  EntryType,
  Paginated,
  WhitelistEntry,
  WhitelistEntryCreate,
  WhitelistEntryUpdate,
} from '@/types/api'

const BASE = `${API_PREFIX}/whitelist`

export type ListWhitelistParams = {
  page?: number
  /** Capped at 100 by the backend. */
  page_size?: number
  entry_type?: EntryType
}

export async function listWhitelist(
  params: ListWhitelistParams = {},
): Promise<Paginated<WhitelistEntry>> {
  const { data } = await http.get<Paginated<WhitelistEntry>>(BASE, { params })
  return data
}

export async function getWhitelistEntry(id: number): Promise<WhitelistEntry> {
  const { data } = await http.get<WhitelistEntry>(`${BASE}/${id}`)
  return data
}

/** 409 if the value already exists, 422 if a guardrail rejects it. */
export async function createWhitelistEntry(
  payload: WhitelistEntryCreate,
): Promise<WhitelistEntry> {
  const { data } = await http.post<WhitelistEntry>(BASE, payload)
  return data
}

/**
 * Partial update.
 *
 * The backend applies `exclude_unset` and returns **400** for an empty patch,
 * so an empty one is rejected here instead — a guaranteed-failing round trip
 * is not worth making, and "No fields provided for update" is a confusing
 * thing to show someone who simply did not change anything.
 */
export async function updateWhitelistEntry(
  id: number,
  patch: WhitelistEntryUpdate,
): Promise<WhitelistEntry> {
  const hasChanges = Object.values(patch).some((value) => value !== undefined)
  if (!hasChanges) {
    throw clientError('Nothing has changed.', 'empty_patch')
  }

  const { data } = await http.put<WhitelistEntry>(`${BASE}/${id}`, patch)
  return data
}

/**
 * Soft delete — the row is flagged `is_active=False`, not removed. There is no
 * restore endpoint, so do not offer undo. Re-adding the same value reactivates
 * the original row rather than creating a new one.
 */
export async function deleteWhitelistEntry(id: number): Promise<void> {
  await http.delete(`${BASE}/${id}`)
}

/** CSV or Excel. Returns a per-row report; render it, do not toast it. */
export async function importWhitelist(file: File): Promise<BulkImportReport> {
  const form = new FormData()
  form.append('file', file)

  const { data } = await http.post<BulkImportReport>(`${BASE}/import`, form, {
    // Let the browser set multipart/form-data with its own boundary.
    headers: { 'Content-Type': undefined },
  })
  return data
}
