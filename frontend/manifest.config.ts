import { defineManifest } from '@crxjs/vite-plugin'

import pkg from './package.json'

/**
 * MV3 manifest, authored in TypeScript so paths are checked at build time.
 *
 * `side_panel` requires Chrome 114+. There is deliberately no `default_popup`:
 * the toolbar icon opens the side panel instead (wired up in
 * `src/background/index.ts`), so there is only one UI to build and maintain.
 */
export default defineManifest({
  manifest_version: 3,
  name: 'AI Email Assistant',
  version: pkg.version,
  description: pkg.description,
  minimum_chrome_version: '114',

  icons: {
    16: 'icons/icon-16.png',
    32: 'icons/icon-32.png',
    48: 'icons/icon-48.png',
    128: 'icons/icon-128.png',
  },

  action: {
    default_title: 'Open AI Email Assistant',
  },

  background: {
    service_worker: 'src/background/index.ts',
    type: 'module',
  },

  side_panel: {
    default_path: 'src/sidepanel/index.html',
  },

  // Kept intentionally tiny: it only ever reads the open thread's sender so it
  // can be quick-added to the whitelist. All Gmail polling happens server-side.
  content_scripts: [
    {
      matches: ['https://mail.google.com/*'],
      js: ['src/content/index.ts'],
      run_at: 'document_idle',
    },
  ],

  // Deliberately free of prompted permissions. "See details" in the Inbox opens
  // Gmail with `window.open`, which needs none — reusing the already-open Gmail
  // tab would have meant `tabs`, and that re-prompts every installed user on
  // update with a "Read your browsing history" warning. Weigh that before
  // adding anything here.
  permissions: ['storage', 'sidePanel', 'alarms', 'notifications'],

  // Both spellings: the backend binds 127.0.0.1, but users type localhost.
  host_permissions: ['http://localhost:8000/*', 'http://127.0.0.1:8000/*'],
})
