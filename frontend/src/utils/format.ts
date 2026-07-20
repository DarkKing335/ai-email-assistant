/**
 * Stat-tile values: exact up to 1,000, compact above it (12.9K, 4.2M).
 * Long numbers would otherwise wrap in a two-column grid this narrow.
 */
export function formatCompact(value: number): string {
  if (Math.abs(value) < 1000) return String(value)
  return new Intl.NumberFormat(undefined, {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(value)
}

/** Processing durations come from the backend in whole milliseconds. */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`
  return `${(ms / 60_000).toFixed(1)} min`
}
