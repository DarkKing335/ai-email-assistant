/**
 * MV3 service worker.
 *
 * Two constraints shape everything here:
 *
 *   - **No axios.** Its browser build needs `XMLHttpRequest`, absent in a
 *     service worker. All network calls go through `workerApi.ts`, which uses
 *     `fetchJson`.
 *   - **No `setInterval`, and no module state.** The worker is terminated after
 *     ~30s idle and restarted for each event, so timers do not survive and
 *     anything that must persist between runs lives in `chrome.storage`.
 *
 * Every top-level statement below re-runs on each wake, so all of it is
 * idempotent.
 */

import { STORAGE_KEYS } from '@/utils/chromeStorage'
import { loadSettings, MIN_BACKGROUND_INTERVAL_MINUTES } from '@/utils/settings'

import { checkForNewEmails } from './poller'

const ALARM_NAME = 'check-new-emails'

/**
 * Create or re-create the polling alarm.
 *
 * Only rewrites the alarm when the period actually changed. Calling
 * `alarms.create` unconditionally on every wake would restart the countdown
 * each time, and a worker that wakes often would never reach its own deadline.
 */
async function ensureAlarm(): Promise<void> {
  const settings = await loadSettings()
  const periodInMinutes = Math.max(
    MIN_BACKGROUND_INTERVAL_MINUTES,
    settings.backgroundIntervalMinutes,
  )

  const existing = await chrome.alarms.get(ALARM_NAME)
  if (existing?.periodInMinutes === periodInMinutes) return

  await chrome.alarms.create(ALARM_NAME, { periodInMinutes })
  console.debug(
    `[ai-email-assistant] alarm scheduled every ${periodInMinutes} min`,
  )
}

// Toolbar icon opens the side panel. Set at top level rather than inside
// onInstalled so it is re-applied whenever the worker restarts.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error: unknown) => {
    console.error('[ai-email-assistant] setPanelBehavior failed', error)
  })

chrome.runtime.onInstalled.addListener(() => {
  void ensureAlarm()
  // One immediate poll so a fresh install shows a badge without waiting out a
  // whole interval.
  void checkForNewEmails()
})

chrome.runtime.onStartup.addListener(() => {
  void ensureAlarm()
})

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name !== ALARM_NAME) return
  void checkForNewEmails()
})

/**
 * The panel writes settings to `chrome.storage`; this is how the worker finds
 * out. Changing the interval takes effect on the next tick rather than
 * requiring a reload.
 */
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== 'local') return
  if (changes[STORAGE_KEYS.settings]) void ensureAlarm()
})

// Covers the case neither lifecycle event does: the worker being revived for
// some other reason after the alarm was somehow lost.
void ensureAlarm()

console.debug('[ai-email-assistant] service worker ready')
