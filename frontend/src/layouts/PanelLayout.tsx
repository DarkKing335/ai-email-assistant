import type { ReactNode } from 'react'

/**
 * The panel frame: a fixed header/nav block above a single scrolling region.
 *
 * Only `main` scrolls. The panel is narrow and resizable, so the tab bar has to
 * stay reachable no matter how long the content gets.
 */
export function PanelLayout({
  header,
  nav,
  children,
}: {
  header: ReactNode
  nav: ReactNode
  children: ReactNode
}) {
  return (
    <div className="flex h-full flex-col bg-white text-ink-900 dark:bg-ink-950 dark:text-ink-100">
      {/* A mint hairline rather than a grey one: it is the only thing dividing
          the fixed block from the scrolling content, so it sets the tone. */}
      <div className="shrink-0 border-b border-brand-100 dark:border-ink-800">
        {header}
        {nav}
      </div>
      <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
    </div>
  )
}
