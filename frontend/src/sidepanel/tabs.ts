/**
 * The panel's top-level sections.
 *
 * `blockedReason` marks a tab whose backend does not exist yet. The tab is
 * still shown — during development it is more useful to see the gap and its
 * cause than to wonder why a section from the design is missing. Clear the
 * field when the backend lands.
 */
export const TABS = [
  { id: 'inbox', label: 'Inbox', blockedReason: null },
  { id: 'dashboard', label: 'Dashboard', blockedReason: null },
  { id: 'whitelist', label: 'Whitelist', blockedReason: null },
  { id: 'logs', label: 'Logs', blockedReason: null },
] as const

export type TabId = (typeof TABS)[number]['id']

/** The centre of the product: what arrived, what it said, what to reply. */
export const DEFAULT_TAB: TabId = 'inbox'
