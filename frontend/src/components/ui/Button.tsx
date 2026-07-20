import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md'

/**
 * `primary` darkens on hover rather than brightening, which is the opposite of
 * the usual move here. White text needs brand-700 (5.36:1); brand-600 is 3.66:1
 * and fails, so the lighter step is not available to a filled button.
 */
const VARIANT_CLASSES: Record<Variant, string> = {
  primary:
    'bg-brand-700 text-white hover:bg-brand-800 focus-visible:outline-brand-700',
  secondary:
    'border border-brand-200 text-ink-700 hover:bg-brand-50 focus-visible:outline-brand-400 dark:border-ink-700 dark:text-ink-200 dark:hover:bg-ink-900',
  ghost:
    'text-ink-600 hover:bg-brand-50 focus-visible:outline-brand-400 dark:text-ink-300 dark:hover:bg-ink-800',
  danger: 'bg-red-600 text-white hover:bg-red-500 focus-visible:outline-red-600',
}

const SIZE_CLASSES: Record<Size, string> = {
  sm: 'h-7 px-2 text-xs',
  md: 'h-9 px-3 text-sm',
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant
  size?: Size
}

export function Button({
  variant = 'secondary',
  size = 'md',
  className = '',
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      // Explicit, because a bare <button> inside a form defaults to submit.
      type={type}
      className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      {...props}
    />
  )
}
