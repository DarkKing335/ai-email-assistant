import { useState } from 'react'

import { Badge, Button, Input } from '@/components/ui'
import { normalizeError } from '@/services/errors'
import type { WhitelistEntry, WhitelistEntryUpdate } from '@/types/api'
import { formatDateTime } from '@/utils/date'

import {
  useDeleteWhitelistEntry,
  useUpdateWhitelistEntry,
} from '../hooks/useWhitelist'
import { inspectValue } from '../lib/entryValue'

export function EntryRow({ entry }: { entry: WhitelistEntry }) {
  const [mode, setMode] = useState<'view' | 'edit' | 'confirmDelete'>('view')
  const [draftValue, setDraftValue] = useState(entry.value)

  const update = useUpdateWhitelistEntry()
  const remove = useDeleteWhitelistEntry()

  const inference = inspectValue(draftValue)

  /**
   * Only genuinely-changed fields go in. A `PUT` with an empty body is a 400
   * (`exclude_unset` on the backend), and comparing against the *normalised*
   * value stops "Bob@X.com" from looking like an edit of "bob@x.com".
   */
  const patch: WhitelistEntryUpdate = {}
  if (inference.kind === 'valid' && inference.normalized !== entry.value) {
    patch.value = inference.normalized
  }
  const hasChanges = Object.keys(patch).length > 0

  const typeWillChange =
    inference.kind === 'valid' && inference.entryType !== entry.entry_type

  function resetDraft() {
    setDraftValue(entry.value)
    update.reset()
    setMode('view')
  }

  function handleSave() {
    if (!hasChanges) return
    update.mutate({ id: entry.id, patch }, { onSuccess: () => setMode('view') })
  }

  const updateError = update.isError ? normalizeError(update.error) : null
  const deleteError = remove.isError ? normalizeError(remove.error) : null

  // ---------------------------------------------------------------- editing
  if (mode === 'edit') {
    // The border needs a strong step, not the pastel: mint is now the ambient
    // colour of the whole panel, so a light mint border would stop reading as
    // "this row is being edited". brand-600 is 3.66:1 on white.
    return (
      <li className="rounded-lg border border-brand-600 p-2.5 dark:border-brand-500/60">
        <Input
          value={draftValue}
          onChange={(event) => setDraftValue(event.target.value)}
          aria-label="Value"
          invalid={inference.kind === 'invalid'}
          autoComplete="off"
          spellCheck={false}
        />

        <div className="mt-2 flex items-center gap-2">
          <div className="ml-auto flex gap-1.5">
            <Button size="sm" variant="ghost" onClick={resetDraft}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant="primary"
              onClick={handleSave}
              // Disabled rather than allowed-then-rejected: an unchanged save
              // would return 400 "No fields provided for update", which reads
              // like a bug to someone who simply changed their mind.
              disabled={!hasChanges || update.isPending || inference.kind !== 'valid'}
            >
              {update.isPending ? 'Saving…' : 'Save'}
            </Button>
          </div>
        </div>

        {inference.kind === 'invalid' && (
          <p className="mt-1.5 text-xs text-amber-600 dark:text-amber-400">
            {inference.message}
          </p>
        )}

        {typeWillChange && (
          <p className="mt-1.5 text-xs text-amber-600 dark:text-amber-400">
            {inference.kind === 'valid' && inference.entryType === 'domain'
              ? `This stops being a single address and becomes a domain rule — everyone at ${inference.normalized.slice(1)} will match.`
              : 'This narrows from a whole domain to a single address.'}
          </p>
        )}

        {updateError && (
          <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">
            {updateError.message}
          </p>
        )}
      </li>
    )
  }

  // ------------------------------------------------------- delete confirming
  if (mode === 'confirmDelete') {
    return (
      <li className="rounded-lg border border-red-300 p-2.5 dark:border-red-500/50">
        <p className="font-mono text-sm break-all">{entry.value}</p>
        <p className="mt-1 text-xs leading-relaxed text-ink-600 dark:text-ink-400">
          There is no undo. Adding this value again later reactivates{' '}
          <em>this same rule</em> rather than creating a new one — it keeps its
          original id and creation date, so it is not a clean slate.
        </p>
        <div className="mt-2 flex justify-end gap-1.5">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              remove.reset()
              setMode('view')
            }}
          >
            Cancel
          </Button>
          <Button
            size="sm"
            variant="danger"
            onClick={() => remove.mutate(entry.id)}
            disabled={remove.isPending}
          >
            {remove.isPending ? 'Deleting…' : 'Delete'}
          </Button>
        </div>
        {deleteError && (
          <p className="mt-1.5 text-xs text-red-600 dark:text-red-400">
            {deleteError.message}
          </p>
        )}
      </li>
    )
  }

  // ---------------------------------------------------------------- viewing
  return (
    <li className="rounded-lg border border-ink-200 p-2.5 dark:border-ink-800">
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 font-mono text-sm break-all">{entry.value}</p>
        <Badge tone={entry.entry_type === 'domain' ? 'warning' : 'info'}>
          {entry.entry_type}
        </Badge>
      </div>
      <div className="mt-1 flex items-center justify-between gap-2">
        <p className="truncate text-xs text-ink-500 dark:text-ink-400">
          {formatDateTime(entry.created_at)}
        </p>
        <div className="flex shrink-0 gap-0.5">
          <Button size="sm" variant="ghost" onClick={() => setMode('edit')}>
            Edit
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setMode('confirmDelete')}
          >
            Delete
          </Button>
        </div>
      </div>
    </li>
  )
}
