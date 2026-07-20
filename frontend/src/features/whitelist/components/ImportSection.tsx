import { useRef, type ChangeEvent } from 'react'

import { Button, ErrorState } from '@/components/ui'
import { BULK_IMPORT_MAX_ROWS, type BulkImportReport } from '@/types/api'

import { useImportWhitelist } from '../hooks/useWhitelist'

const TEMPLATE_CSV = ['value', 'alice@example.com', '@example.com', ''].join(
  '\n',
)

function downloadTemplate() {
  const url = URL.createObjectURL(
    new Blob([TEMPLATE_CSV], { type: 'text/csv;charset=utf-8' }),
  )
  const link = document.createElement('a')
  link.href = url
  link.download = 'whitelist-template.csv'
  link.click()
  URL.revokeObjectURL(url)
}

/**
 * Per-row outcome, rendered as a panel rather than a toast.
 *
 * A 200-row import that half-succeeded has too much to say for a notification
 * that disappears — and the row numbers are the whole point: they map straight
 * onto the spreadsheet the file came from.
 */
function ImportReport({ report }: { report: BulkImportReport }) {
  const rejected = report.validation_errors.length

  return (
    <div className="rounded-lg border border-ink-200 p-3 dark:border-ink-800">
      <p className="text-sm font-medium">
        {report.inserted} of {report.total_rows} rows imported
      </p>

      <ul className="mt-1.5 space-y-0.5 text-xs text-ink-600 dark:text-ink-400">
        <li>{report.inserted} added</li>
        {report.skipped_duplicates > 0 && (
          <li>{report.skipped_duplicates} skipped — already on the list</li>
        )}
        {rejected > 0 && (
          <li className="text-red-600 dark:text-red-400">
            {rejected} rejected
          </li>
        )}
      </ul>

      {report.warnings.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-amber-600 dark:text-amber-400">
          {report.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      {rejected > 0 && (
        <div className="mt-2 max-h-48 space-y-1.5 overflow-y-auto border-t border-ink-100 pt-2 dark:border-ink-800">
          {report.validation_errors.map((rowError) => (
            <div key={rowError.row_index} className="text-xs">
              {/* row_index counts the header, so it is the literal spreadsheet
                  row number — say "Row 12", not "the 11th entry". */}
              <span className="font-medium">Row {rowError.row_index}</span>
              {rowError.raw_value && (
                <span className="ml-1.5 font-mono break-all text-ink-500 dark:text-ink-400">
                  {rowError.raw_value}
                </span>
              )}
              <ul className="mt-0.5 ml-3 list-disc text-red-600 dark:text-red-400">
                {rowError.errors.map((message) => (
                  <li key={message}>{message}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function ImportSection() {
  const fileInput = useRef<HTMLInputElement>(null)
  const importFile = useImportWhitelist()

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (file) importFile.mutate(file)
    // Cleared so picking the same file again still fires a change event.
    event.target.value = ''
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={fileInput}
          type="file"
          accept=".csv,.xlsx,.xls"
          onChange={handleFile}
          className="hidden"
        />
        <Button
          size="sm"
          onClick={() => fileInput.current?.click()}
          disabled={importFile.isPending}
        >
          {importFile.isPending ? 'Importing…' : 'Import CSV or Excel'}
        </Button>
        <Button size="sm" variant="ghost" onClick={downloadTemplate}>
          Template
        </Button>
      </div>

      <p className="text-xs text-ink-500 dark:text-ink-400">
        One column: <code className="font-mono">value</code>. Up to{' '}
        {BULK_IMPORT_MAX_ROWS.toLocaleString()} rows. Extra columns are ignored.
      </p>

      {importFile.isError && (
        <ErrorState
          error={importFile.error}
          onRetry={() => importFile.reset()}
        />
      )}

      {importFile.isSuccess && <ImportReport report={importFile.data} />}
    </div>
  )
}
