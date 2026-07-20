import { DashboardPanel } from '@/features/dashboard/DashboardPanel'
import { InboxPanel } from '@/features/inbox/InboxPanel'
import { LogsPanel } from '@/features/logs/LogsPanel'
import { GmailGate } from '@/features/settings/GmailGate'
import { SettingsPanel } from '@/features/settings/SettingsPanel'
import { useGmailAuthStatus } from '@/features/settings/useGmailAuthStatus'
import { WhitelistPanel } from '@/features/whitelist/WhitelistPanel'
import { PanelLayout } from '@/layouts/PanelLayout'
import { useUiStore } from '@/stores/uiStore'

import { PanelHeader } from './PanelHeader'
import { TabNav } from './TabNav'
import type { TabId } from './tabs'

const PANELS: Record<TabId, () => React.JSX.Element> = {
  inbox: InboxPanel,
  dashboard: DashboardPanel,
  whitelist: WhitelistPanel,
  logs: LogsPanel,
}

export default function App() {
  const activeTab = useUiStore((state) => state.activeTab)
  const isSettingsOpen = useUiStore((state) => state.isSettingsOpen)
  const ActivePanel = PANELS[activeTab]

  // Shares its cache entry with the gate below, so this costs no extra request.
  const isConnected = useGmailAuthStatus().data?.connected === true

  return (
    // Tabs are hidden until an account is linked: behind the gate they all lead
    // to the same connect screen, so offering four of them is noise. Settings
    // stays reachable from the header — the backend URL may need fixing before
    // connecting is even possible.
    <PanelLayout header={<PanelHeader />} nav={isConnected ? <TabNav /> : null}>
      {/* Keyed so switching views remounts rather than reusing state across two
          unrelated panels. Inactive panels stay unmounted, which also stops
          their queries polling in the background. */}
      <div
        key={isSettingsOpen ? 'settings' : activeTab}
        role="tabpanel"
        id={`panel-${activeTab}`}
        aria-labelledby={`tab-${activeTab}`}
        className="p-4"
      >
        {isSettingsOpen ? (
          <SettingsPanel />
        ) : (
          <GmailGate>
            <ActivePanel />
          </GmailGate>
        )}
      </div>
    </PanelLayout>
  )
}
