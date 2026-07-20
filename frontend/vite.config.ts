import { fileURLToPath, URL } from 'node:url'

import { crx } from '@crxjs/vite-plugin'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

import manifest from './manifest.config'

export default defineConfig({
  plugins: [react(), tailwindcss(), crx({ manifest })],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  server: {
    port: 5173,
    strictPort: true,
    // HMR requests arrive from the chrome-extension:// origin, which the dev
    // server rejects by default.
    cors: { origin: [/chrome-extension:\/\//] },
  },

  build: {
    // Matches `minimum_chrome_version` in the manifest. The default target is
    // chrome87, which is both needlessly conservative for an extension that
    // requires 114 for `chrome.sidePanel`, and too old for the top-level await
    // that hydrates settings before the first render.
    target: 'chrome114',
    outDir: 'dist',
    emptyOutDir: true,
    // The panel is the only meaningful bundle; source maps make the service
    // worker debuggable from chrome://extensions.
    sourcemap: true,
  },
})
