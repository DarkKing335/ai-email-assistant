import { create } from 'zustand'

import { setApiBaseUrl } from '@/services/config'
import { STORAGE_KEYS, writeStorage } from '@/utils/chromeStorage'
import { DEFAULT_SETTINGS, loadSettings, type Settings } from '@/utils/settings'

/**
 * Panel-side settings store.
 *
 * The shape and the loading logic live in `utils/settings.ts` so the service
 * worker can reuse them without importing zustand. This file adds only what the
 * panel needs: reactive state and write-through persistence.
 *
 * Hydrated **once at boot** (see `hydrateSettings`), before React mounts, so no
 * component ever reads storage directly.
 */
export type { Settings } from '@/utils/settings'
export {
  BACKGROUND_INTERVAL_OPTIONS,
  DEFAULT_SETTINGS,
  MIN_BACKGROUND_INTERVAL_MINUTES,
} from '@/utils/settings'

type SettingsState = Settings & {
  isHydrated: boolean
  setSetting: <K extends keyof Settings>(key: K, value: Settings[K]) => void
  resetToDefaults: () => void
}

function persist(settings: Settings) {
  void writeStorage(STORAGE_KEYS.settings, settings)
}

function currentSettings(state: SettingsState): Settings {
  return {
    apiBaseUrl: state.apiBaseUrl,
    backgroundIntervalMinutes: state.backgroundIntervalMinutes,
    notificationsEnabled: state.notificationsEnabled,
  }
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  ...DEFAULT_SETTINGS,
  isHydrated: false,

  setSetting: (key, value) => {
    set({ [key]: value } as Pick<SettingsState, typeof key>)

    // The HTTP clients read the base URL per request, so this takes effect on
    // the next call without rebuilding anything.
    if (key === 'apiBaseUrl') setApiBaseUrl(value as string)

    // Written to chrome.storage, which is also how the service worker learns
    // about the change — it watches for storage events.
    persist(currentSettings(get()))
  },

  resetToDefaults: () => {
    set(DEFAULT_SETTINGS)
    setApiBaseUrl(DEFAULT_SETTINGS.apiBaseUrl)
    persist(DEFAULT_SETTINGS)
  },
}))

/** Load persisted settings into the store. Call once, before rendering. */
export async function hydrateSettings(): Promise<void> {
  const settings = await loadSettings()
  setApiBaseUrl(settings.apiBaseUrl)
  useSettingsStore.setState({ ...settings, isHydrated: true })
}
