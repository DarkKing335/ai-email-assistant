import { useUiStore } from '@/stores/uiStore'

import { TABS } from './tabs'

export function TabNav() {
  const activeTab = useUiStore((state) => state.activeTab)
  const setActiveTab = useUiStore((state) => state.setActiveTab)

  return (
    <nav
      role="tablist"
      aria-label="Sections"
      // The panel can be dragged narrow; let the tabs scroll rather than wrap
      // into a second row that pushes the content down.
      className="flex gap-1 overflow-x-auto px-2 pb-2"
    >
      {TABS.map((tab) => {
        const isActive = tab.id === activeTab
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-controls={`panel-${tab.id}`}
            id={`tab-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            // The active tab is the panel's one full-strength use of the
            // pastel. It carries dark ink, never white — see the theme note.
            className={`rounded-md px-2.5 py-1 text-xs font-medium whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 ${
              isActive
                ? 'bg-brand-200 text-ink-950 dark:bg-brand-300 dark:text-ink-950'
                : 'text-ink-600 hover:bg-brand-50 dark:text-ink-400 dark:hover:bg-ink-800'
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </nav>
  )
}
