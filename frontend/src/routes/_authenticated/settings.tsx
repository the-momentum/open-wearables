import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import type { AppConfig } from '@/lib/api/services/config.service';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { PageHeader } from '@/components/ui/page-header';
import { CredentialsTab } from './settings/-credentials-tab';
import { ProvidersTab } from './settings/-providers-tab';
import { PrioritiesTab } from './settings/-priorities-tab';
import { TeamTab } from './settings/-team-tab';
import { DataLifecycleTab } from './settings/-data-lifecycle-tab';
import { ChangePasswordTab } from './settings/-change-password-tab';
import { SeedDataTab } from './settings/-seed-data-tab';
import { useConfig } from '@/hooks/api/use-config';

export const Route = createFileRoute('/_authenticated/settings')({
  component: SettingsPage,
});

interface TabConfig {
  id: string;
  label: string;
  component: React.ComponentType;
  hidden?: (config: AppConfig) => boolean;
}

const tabs: TabConfig[] = [
  {
    id: 'credentials',
    label: 'Credentials',
    component: CredentialsTab,
  },
  {
    id: 'providers',
    label: 'Providers',
    component: ProvidersTab,
  },
  {
    id: 'priorities',
    label: 'Priorities',
    component: PrioritiesTab,
  },
  {
    id: 'data-lifecycle',
    label: 'Data Lifecycle',
    component: DataLifecycleTab,
    hidden: (config) => config.data_lifecycle_enabled === false,
  },
  {
    id: 'team',
    label: 'Team',
    component: TeamTab,
  },
  {
    id: 'change-password',
    label: 'Change Password',
    component: ChangePasswordTab,
  },
  {
    id: 'seed-data',
    label: 'Seed Data',
    component: SeedDataTab,
  },
];

function SettingsPage() {
  const [activeTab, setActiveTab] = useState(tabs[0].id);
  const config = useConfig();
  // Flag-gated tabs stay hidden until the config loads, so a disabled feature never flashes in.
  const visibleTabs = tabs.filter(
    (tab) => !tab.hidden || (config.data && !tab.hidden(config.data))
  );

  return (
    <div className="p-6 md:p-8 space-y-6">
      <PageHeader
        title="Settings"
        description="Manage your settings and preferences"
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="border border-border/60 bg-card/40 backdrop-blur-xl">
          {visibleTabs.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {visibleTabs.map((tab) => (
          <TabsContent
            key={tab.id}
            value={tab.id}
            className="mt-6 focus-visible:outline-none"
          >
            <tab.component />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
