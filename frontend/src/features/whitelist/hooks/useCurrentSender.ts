import { useEffect, useState } from 'react'

import { STORAGE_KEYS } from '@/utils/chromeStorage'
import { readCurrentSender, type CapturedSender } from '@/utils/currentSender'

/**
 * The Gmail sender currently on screen, if any.
 *
 * Re-reads on `chrome.storage.onChanged` so switching threads in Gmail updates
 * the suggestion while the panel is open — the side panel stays mounted beside
 * Gmail, so a value read once at mount would go stale immediately.
 */
export function useCurrentSender(): CapturedSender | null {
  const [sender, setSender] = useState<CapturedSender | null>(null)

  useEffect(() => {
    let isActive = true

    const refresh = () => {
      void readCurrentSender().then((value) => {
        if (isActive) setSender(value)
      })
    }

    refresh()

    if (typeof chrome === 'undefined' || !chrome.storage?.onChanged) {
      return () => {
        isActive = false
      }
    }

    const listener = (
      changes: Record<string, chrome.storage.StorageChange>,
      areaName: string,
    ) => {
      if (areaName === 'local' && changes[STORAGE_KEYS.currentSender]) refresh()
    }

    chrome.storage.onChanged.addListener(listener)
    return () => {
      isActive = false
      chrome.storage.onChanged.removeListener(listener)
    }
  }, [])

  return sender
}
