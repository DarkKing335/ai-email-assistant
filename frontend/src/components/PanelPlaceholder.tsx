import { EmptyState } from '@/components/ui'
import { SectionHeader } from '@/layouts/SectionHeader'

/**
 * Temporary scaffolding for sections that are not built yet.
 *
 * Distinguishes "scheduled, nothing blocking it" from "blocked on a backend
 * gap", because those need different responses: one is waiting its turn, the
 * other needs someone to go change the backend. Deleted as each panel lands.
 */
export function PanelPlaceholder({
  title,
  description,
  step,
  blockedReason,
}: {
  title: string
  description: string
  step: string
  blockedReason?: string | null
}) {
  return (
    <>
      <SectionHeader title={title} description={description} />

      {blockedReason ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-500/40 dark:bg-amber-500/10">
          <p className="text-xs font-semibold text-amber-900 dark:text-amber-200">
            Blocked on the backend
          </p>
          <p className="mt-1 text-xs leading-relaxed text-amber-900/80 dark:text-amber-200/80">
            {blockedReason}
          </p>
        </div>
      ) : (
        <EmptyState title="Not built yet" description={`Arrives in ${step}.`} />
      )}
    </>
  )
}
