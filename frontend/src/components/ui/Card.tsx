import type { HTMLAttributes } from 'react'

type CardProps = HTMLAttributes<HTMLDivElement>

export function Card({ className = '', ...props }: CardProps) {
  return (
    <div
      className={`rounded-lg border border-brand-100 bg-white dark:border-ink-800 dark:bg-ink-900/40 ${className}`}
      {...props}
    />
  )
}
