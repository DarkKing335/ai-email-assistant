import { useState, type FormEvent } from 'react'

import { Badge, Button, Input } from '@/components/ui'
import { normalizeError } from '@/services/errors'

import { useCurrentSender } from '../hooks/useCurrentSender'
import { useCreateWhitelistEntry } from '../hooks/useWhitelist'
import { inspectValue } from '../lib/entryValue'

/**
 * One input, no type dropdown.
 *
 * The rule type is inferred from a leading `@`, exactly as the backend does it,
 * and shown live — so the consequence of typing `@fpt.edu.vn` instead of
 * `me@fpt.edu.vn` is visible *before* submitting, not after a whole department
 * starts getting automatic replies.
 */
export function QuickAddBar() {
  const [value, setValue] = useState('')
  const create = useCreateWhitelistEntry()
  const currentSender = useCurrentSender()

  const inference = inspectValue(value)
  const canSubmit = inference.kind === 'valid' && !create.isPending

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (inference.kind !== 'valid') return

    create.mutate(
      { value: inference.normalized },
      // Only cleared on success — a rejected value stays put so it can be
      // corrected rather than retyped.
      { onSuccess: () => setValue('') },
    )
  }

  const serverError = create.isError ? normalizeError(create.error) : null

  // Hidden once the field is in use — the suggestion is a shortcut for an empty
  // field, not a competing option to whatever is being typed.
  const showSuggestion =
    currentSender !== null && value.trim() === '' && !create.isPending

  return (
    <form onSubmit={handleSubmit} className="space-y-1.5">
      {showSuggestion && (
        <button
          type="button"
          onClick={() => setValue(currentSender.email)}
          className="flex w-full items-center gap-2 rounded-md border border-dashed border-ink-300 px-2 py-1.5 text-left transition-colors hover:bg-brand-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-400 dark:border-ink-700 dark:hover:bg-ink-900"
        >
          <span className="shrink-0 text-xs text-ink-500 dark:text-ink-400">
            Open in Gmail
          </span>
          <span className="min-w-0 flex-1 truncate font-mono text-xs">
            {currentSender.email}
          </span>
          {/* Fills the field rather than submitting: the inferred type and any
              guardrail feedback should be visible before anything is created. */}
          {/* brand-700, not the lighter 600: this is 12px text, and 600 is
              3.66:1 on white. */}
          <span className="shrink-0 text-xs font-medium text-brand-700 dark:text-brand-400">
            Use
          </span>
        </button>
      )}

      <div className="flex gap-2">
        <Input
          value={value}
          onChange={(event) => {
            setValue(event.target.value)
            if (create.isError) create.reset()
          }}
          placeholder="alice@example.com or @example.com"
          aria-label="Email address or domain"
          invalid={inference.kind === 'invalid' || serverError !== null}
          autoComplete="off"
          spellCheck={false}
        />
        <Button type="submit" variant="primary" disabled={!canSubmit}>
          {create.isPending ? 'Adding…' : 'Add'}
        </Button>
      </div>

      <div className="min-h-[1.25rem] text-xs">
        {serverError ? (
          // 409 and 422 bodies are written for humans; shown as-is.
          <span className="text-red-600 dark:text-red-400">
            {serverError.message}
          </span>
        ) : inference.kind === 'valid' ? (
          <span className="flex items-center gap-1.5 text-ink-500 dark:text-ink-400">
            <Badge tone={inference.entryType === 'domain' ? 'warning' : 'info'}>
              {inference.entryType}
            </Badge>
            <span>{inference.hint}</span>
          </span>
        ) : inference.kind === 'invalid' ? (
          <span className="text-amber-600 dark:text-amber-400">
            {inference.message}
          </span>
        ) : (
          <span className="text-ink-400 dark:text-ink-500">
            Start with <code className="font-mono">@</code> to match a whole
            domain.
          </span>
        )}
      </div>
    </form>
  )
}
