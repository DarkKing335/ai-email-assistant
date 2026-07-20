import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { hydrateSettings } from '@/stores/settingsStore'

import App from './App'
import { createQueryClient } from './queryClient'
import '@/styles/index.css'

const container = document.getElementById('root')
if (!container) {
  throw new Error('#root is missing from the side panel document')
}

// One client per panel instance. The side panel is torn down when closed, so
// the cache goes with it — see the note in the frontend plan: no persistence
// for MVP, just accept the refetch on reopen.
const queryClient = createQueryClient()

// Settings are read from chrome.storage *before* the first render, so the very
// first request already uses the saved backend URL. Rendering first would fire
// a round of queries at the default address and then repoint mid-flight.
// `hydrateSettings` swallows its own storage errors and falls back to defaults,
// so this cannot block the panel from opening.
await hydrateSettings()

createRoot(container).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
