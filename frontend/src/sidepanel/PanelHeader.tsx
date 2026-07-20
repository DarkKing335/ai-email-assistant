import { useHealth } from '@/hooks/useHealth'
import { getApiBaseUrl } from '@/services/config'
import { useUiStore } from '@/stores/uiStore'

/**
 * Live backend indicator.
 *
 * Worth the pixels because it separates the two failure modes that otherwise
 * look identical in a panel: "the backend is down" and "this particular request
 * failed". Without it, a dead server reads as a broken feature.
 */
function ConnectionDot() {
  const { isSuccess, isError, isLoading } = useHealth()

  const { tone, label } = isLoading
    ? { tone: 'bg-ink-300 dark:bg-ink-600', label: 'Checking backend…' }
    : isSuccess
      ? { tone: 'bg-emerald-500', label: `Connected to ${getApiBaseUrl()}` }
      : isError
        ? { tone: 'bg-red-500', label: `Cannot reach ${getApiBaseUrl()}` }
        : { tone: 'bg-ink-300 dark:bg-ink-600', label: 'Unknown' }

  return (
    <span className="flex items-center gap-1.5" title={label}>
      <span className={`size-2 rounded-full ${tone}`} aria-hidden />
      <span className="sr-only">{label}</span>
    </span>
  )
}

function GearIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-4"
      aria-hidden
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  )
}

export function PanelHeader() {
  const isSettingsOpen = useUiStore((state) => state.isSettingsOpen)
  const toggleSettings = useUiStore((state) => state.toggleSettings)

  return (
    <header className="flex items-center justify-between gap-2 px-4 py-3">
      <h1 className="truncate text-sm font-semibold">AI Email Assistant</h1>
      <div className="flex items-center gap-2">
        <ConnectionDot />
        <button
          type="button"
          onClick={toggleSettings}
          aria-pressed={isSettingsOpen}
          aria-label={isSettingsOpen ? 'Close settings' : 'Open settings'}
          title="Settings"
          className={`rounded p-1 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 ${
            isSettingsOpen
              ? 'bg-brand-200 text-ink-950 dark:bg-brand-300 dark:text-ink-950'
              : 'text-ink-500 hover:bg-brand-50 dark:text-ink-400 dark:hover:bg-ink-800'
          }`}
        >
          <GearIcon />
        </button>
      </div>
    </header>
  )
}
