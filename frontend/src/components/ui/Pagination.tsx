import { Button } from './Button'

/**
 * Both paginated endpoints return `{ items, total, page, page_size }`, so one
 * control serves the whole app. Renders nothing when everything fits on a page.
 */
export function Pagination({
  page,
  pageSize,
  total,
  isFetching = false,
  onPageChange,
}: {
  page: number
  pageSize: number
  total: number
  isFetching?: boolean
  onPageChange: (page: number) => void
}) {
  if (total <= pageSize) return null

  const lastPage = Math.max(1, Math.ceil(total / pageSize))
  const firstRow = (page - 1) * pageSize + 1
  const lastRow = Math.min(page * pageSize, total)

  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs text-ink-500 tabular-nums dark:text-ink-400">
        {firstRow}–{lastRow} of {total}
      </span>
      <div className="flex gap-1.5">
        <Button
          size="sm"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1 || isFetching}
        >
          Previous
        </Button>
        <Button
          size="sm"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= lastPage || isFetching}
        >
          Next
        </Button>
      </div>
    </div>
  )
}
