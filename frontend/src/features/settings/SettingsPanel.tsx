import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Button, Input } from '@/components/ui'
import { SectionHeader } from '@/layouts/SectionHeader'
import {
  BACKGROUND_INTERVAL_OPTIONS,
  MIN_BACKGROUND_INTERVAL_MINUTES,
  useSettingsStore,
} from '@/stores/settingsStore'

import { GmailConnection } from './GmailConnection'

/**
 * Origins the manifest grants access to. Pointing the app at anything else
 * fails as an opaque network error — the browser blocks the request before it
 * leaves, and the response looks identical to a backend that is simply down.
 * Worth warning about explicitly rather than letting someone debug a dead
 * panel.
 */
const GRANTED_ORIGINS = ['http://localhost:8000', 'http://127.0.0.1:8000']

function isOriginGranted(url: string): boolean {
  try {
    return GRANTED_ORIGINS.includes(new URL(url).origin)
  } catch {
    return false
  }
}

function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

type TestResult = { ok: boolean; message: string }

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-medium">{label}</label>
      {children}
      {hint && (
        <p className="text-xs leading-relaxed text-ink-500 dark:text-ink-400">
          {hint}
        </p>
      )}
    </div>
  )
}

export function SettingsPanel() {
  const queryClient = useQueryClient()
  const settings = useSettingsStore()

  const [draftUrl, setDraftUrl] = useState(settings.apiBaseUrl)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [isTesting, setTesting] = useState(false)

  const trimmedUrl = draftUrl.trim().replace(/\/+$/, '')
  const urlChanged = trimmedUrl !== settings.apiBaseUrl
  const urlValid = isValidUrl(trimmedUrl)

  async function handleTest() {
    setTesting(true)
    setTestResult(null)
    try {
      // Deliberately a raw fetch against the *draft* URL — the shared client
      // reads the saved one, which is not what is being tested here.
      const response = await fetch(`${trimmedUrl}/health`, {
        headers: { Accept: 'application/json' },
      })
      setTestResult(
        response.ok
          ? { ok: true, message: 'Backend responded.' }
          : { ok: false, message: `Backend returned ${response.status}.` },
      )
    } catch {
      setTestResult({
        ok: false,
        message: 'No response — backend not running, or origin not permitted.',
      })
    } finally {
      setTesting(false)
    }
  }

  function handleSaveUrl() {
    settings.setSetting('apiBaseUrl', trimmedUrl)
    // Cached data belongs to the previous backend. It is not stale — it is
    // from somewhere else — so drop it rather than revalidate.
    queryClient.clear()
    setTestResult(null)
  }

  const version =
    typeof chrome !== 'undefined' && chrome.runtime?.getManifest
      ? chrome.runtime.getManifest().version
      : null

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Settings"
        description="Stored on this device only."
      />

      <Field
        label="Gmail account"
        hint="Connected to the backend, not to this extension — the extension holds no Gmail credentials and requests no Gmail permissions."
      >
        <GmailConnection />
      </Field>

      <Field
        label="Backend URL"
        hint="Where the FastAPI server is listening. Must include the scheme and port."
      >
        <div className="flex gap-2">
          <Input
            value={draftUrl}
            onChange={(event) => {
              setDraftUrl(event.target.value)
              setTestResult(null)
            }}
            placeholder="http://127.0.0.1:8000"
            invalid={draftUrl.trim().length > 0 && !urlValid}
            autoComplete="off"
            spellCheck={false}
          />
          <Button
            size="md"
            onClick={() => void handleTest()}
            disabled={!urlValid || isTesting}
          >
            {isTesting ? 'Testing…' : 'Test'}
          </Button>
        </div>

        {testResult && (
          <p
            className={`text-xs ${
              testResult.ok
                ? 'text-emerald-600 dark:text-emerald-400'
                : 'text-red-600 dark:text-red-400'
            }`}
          >
            {testResult.message}
          </p>
        )}

        {urlValid && !isOriginGranted(trimmedUrl) && (
          <p className="rounded border border-amber-300 bg-amber-50 p-2 text-xs leading-relaxed text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200">
            The extension is only permitted to reach{' '}
            <code className="font-mono">localhost:8000</code> and{' '}
            <code className="font-mono">127.0.0.1:8000</code>. Any other address
            needs a matching entry in{' '}
            <code className="font-mono">host_permissions</code> and a rebuild —
            without it every request fails silently.
          </p>
        )}

        {urlChanged && (
          <Button
            size="sm"
            variant="primary"
            onClick={handleSaveUrl}
            disabled={!urlValid}
          >
            Save and reconnect
          </Button>
        )}
      </Field>

      <Field
        label="Background check"
        hint={`How often to look for new mail while the panel is closed. Chrome will not run an alarm more than once a minute, so ${MIN_BACKGROUND_INTERVAL_MINUTES} minute is the floor. Takes effect in step 8.`}
      >
        <select
          value={settings.backgroundIntervalMinutes}
          onChange={(event) =>
            settings.setSetting(
              'backgroundIntervalMinutes',
              Number(event.target.value),
            )
          }
          className="h-9 w-full rounded-md border border-ink-300 bg-white px-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-[-1px] focus-visible:outline-brand-500 dark:border-ink-700 dark:bg-ink-950"
        >
          {BACKGROUND_INTERVAL_OPTIONS.map((minutes) => (
            <option key={minutes} value={minutes}>
              Every {minutes} minute{minutes === 1 ? '' : 's'}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Notifications">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={settings.notificationsEnabled}
            onChange={(event) =>
              settings.setSetting('notificationsEnabled', event.target.checked)
            }
            className="size-4 rounded border-ink-300 dark:border-ink-700"
          />
          <span>Notify me when new emails are processed</span>
        </label>
      </Field>

      <div className="flex items-center justify-between border-t border-ink-200 pt-4 dark:border-ink-800">
        <span className="text-xs text-ink-500 dark:text-ink-400">
          {version ? `Version ${version}` : 'Not running as an extension'}
        </span>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            settings.resetToDefaults()
            setDraftUrl(useSettingsStore.getState().apiBaseUrl)
            setTestResult(null)
            queryClient.clear()
          }}
        >
          Reset to defaults
        </Button>
      </div>
    </div>
  )
}
