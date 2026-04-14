import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { CredentialsTab } from './settings/credentials-tab';
import { ProvidersTab } from './settings/providers-tab';
import { PrioritiesTab } from './settings/priorities-tab';
import { TeamTab } from './settings/team-tab';
import { DataLifecycleTab } from './settings/data-lifecycle-tab';
import { SecurityTab } from './settings/security-tab';
import { SeedDataTab } from './settings/seed-data-tab';

export const Route = createFileRoute('/_authenticated/settings')({
  component: SettingsPage,
});

interface TabConfig {
  id: string;
  label: string;
  component: React.ComponentType;
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
  },
  {
    id: 'team',
    label: 'Team',
    component: TeamTab,
  },
  {
    id: 'security',
    label: 'Security',
    component: SecurityTab,
  },
  {
    id: 'seed-data',
    label: 'Seed Data',
    component: SeedDataTab,
  },
];

function SettingsPage() {
  const [activeTab, setActiveTab] = useState(tabs[0].id);

  return (
    <div className="p-8 space-y-6">
      <div className="mb-6">
        <h1 className="text-2xl font-medium text-white">Settings</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Manage your settings and preferences
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-zinc-900/50 border border-zinc-800">
          {tabs.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {tabs.map((tab) => (
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
