/**
 * Shown when the backend has no Google OAuth client credentials.
 *
 * Deliberately not a "Connect Gmail" button: there is nothing to connect to
 * yet, and the button would only ever return a 503. This is a setup task for
 * whoever runs the backend, so it says so.
 */
export function GmailNotConfiguredNotice() {
  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 dark:border-amber-500/40 dark:bg-amber-500/10">
      <p className="text-xs font-semibold text-amber-900 dark:text-amber-200">
        Gmail is not set up
      </p>
      <p className="mt-1 text-xs leading-relaxed text-amber-900/80 dark:text-amber-200/80">
        The backend has no Google OAuth credentials. Follow{' '}
        <code className="font-mono">docs/setup/gmail-oauth.md</code> to create
        them, then restart the backend.
      </p>
    </div>
  )
}
