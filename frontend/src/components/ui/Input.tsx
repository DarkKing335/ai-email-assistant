import type { InputHTMLAttributes } from 'react'

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  invalid?: boolean
}

export function Input({ invalid = false, className = '', ...props }: InputProps) {
  return (
    <input
      aria-invalid={invalid || undefined}
      className={`h-9 w-full min-w-0 rounded-md border bg-white px-2 text-sm placeholder:text-ink-400 focus-visible:outline-2 focus-visible:outline-offset-[-1px] disabled:opacity-50 dark:bg-ink-950 ${
        invalid
          ? 'border-red-400 focus-visible:outline-red-500 dark:border-red-500/60'
          : 'border-ink-300 focus-visible:outline-brand-500 dark:border-ink-700'
      } ${className}`}
      {...props}
    />
  )
}
