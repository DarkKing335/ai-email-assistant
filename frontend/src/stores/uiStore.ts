import { create } from 'zustand'

import { DEFAULT_TAB, type TabId } from '@/sidepanel/tabs'

/**
 * UI state only — never server data.
 *
 * Anything that comes from the backend belongs to TanStack Query, which already
 * handles caching, refetching and invalidation. Duplicating it here would mean
 * two sources of truth that drift.
 *
 * Kept deliberately small: fields are added when a panel actually needs them
 * (`selectedLogId` with the draft module), not in advance.
 */
type UiState = {
  activeTab: TabId
  /**
   * Settings is reached from the header gear rather than a fifth tab — it is a
   * destination you leave again, not a peer of the four content sections. Held
   * alongside `activeTab` so returning from it restores the tab you were on.
   */
  isSettingsOpen: boolean
  setActiveTab: (tab: TabId) => void
  toggleSettings: () => void
  closeSettings: () => void
}

export const useUiStore = create<UiState>((set) => ({
  activeTab: DEFAULT_TAB,
  isSettingsOpen: false,
  // Choosing a tab always leaves settings — otherwise the tab bar would look
  // active while showing something else.
  setActiveTab: (tab) => set({ activeTab: tab, isSettingsOpen: false }),
  toggleSettings: () => set((state) => ({ isSettingsOpen: !state.isSettingsOpen })),
  closeSettings: () => set({ isSettingsOpen: false }),
}))
