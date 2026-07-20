/** Mirrors `src/auto_reply/api/gmail_auth_router.py`. */

import http from '@/services/http'
import { API_PREFIX, getApiBaseUrl } from '@/services/config'

const BASE = `${API_PREFIX}/gmail/auth`

export type GmailAuthStatus = {
  /** Whether the backend has client credentials at all. */
  configured: boolean
  connected: boolean
  email_address: string | null
  scopes: string[]
  last_polled_at: string | null
  poll_interval_seconds: number
  poller: {
    connected: boolean
    buffered: number
    next_poll_at: string | null
    last_error: string | null
  }
}

export async function getGmailAuthStatus(): Promise<GmailAuthStatus> {
  const { data } = await http.get<GmailAuthStatus>(`${BASE}/status`)
  return data
}

/**
 * The consent flow's entry point.
 *
 * Returned as a URL for the caller to open in a tab rather than fetched: the
 * flow is a chain of browser redirects ending on a page Google renders, none of
 * which can happen inside the side panel.
 */
export function getAuthorizationUrl(): string {
  return `${getApiBaseUrl()}${BASE}/start`
}

/**
 * Starts consent in a new tab, not the panel: the flow is a chain of redirects
 * ending on Google's own consent screen, which cannot render in a side panel.
 */
export function openGmailConsent(): void {
  window.open(getAuthorizationUrl(), '_blank', 'noopener')
}

export async function disconnectGmail(): Promise<void> {
  await http.delete(`${BASE}/`)
}
