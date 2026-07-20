import { setApiBaseUrl } from '@/services/config'
import { setBadgeCount } from '@/utils/badge'
import {
  getLastNotifiedCount,
  getLastSeenAt,
  setLastNotifiedCount,
} from '@/utils/lastSeen'
import { loadSettings } from '@/utils/settings'

import { notifyNewEmails } from './notifications'
import { fetchNewSince } from './workerApi'

/**
 * One poll: how many logs have arrived since the user last looked?
 *
 * Runs from a cold start every time — the worker is torn down between alarms,
 * so settings and the watermark are re-read from storage on each pass rather
 * than cached in module scope.
 */
export async function checkForNewEmails(): Promise<void> {
  const settings = await loadSettings()
  // The worker has its own module instance of the HTTP config; the panel's
  // hydration does not reach it.
  setApiBaseUrl(settings.apiBaseUrl)

  const since = await getLastSeenAt()

  let result: Awaited<ReturnType<typeof fetchNewSince>>
  try {
    result = await fetchNewSince(since)
  } catch (error) {
    // The backend being unreachable is the normal case for a local dev server,
    // and it is not news. Leave the badge showing whatever it last showed —
    // clearing it would claim there is nothing new, which is not what we know.
    console.debug('[ai-email-assistant] poll failed', error)
    return
  }

  await setBadgeCount(result.total)

  // Notify only on an increase. Without the persisted high-water mark, every
  // poll would re-announce the same backlog until the user opened the panel.
  const alreadyNotified = await getLastNotifiedCount()
  if (result.total > alreadyNotified) {
    if (settings.notificationsEnabled) {
      await notifyNewEmails(result.total, result.latest)
    }
    await setLastNotifiedCount(result.total)
  }
}
