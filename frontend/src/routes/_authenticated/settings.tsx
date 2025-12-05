import { createFileRoute } from '@tanstack/react-router';
import { useState } from 'react';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { CredentialsTab } from './settings/credentials-tab';
import { ProvidersTab } from './settings/providers-tab';

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
        <TabsList>
          {tabs.map((tab) => (
            <TabsTrigger key={tab.id} value={tab.id}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>

        {tabs.map((tab) => (
          <TabsContent key={tab.id} value={tab.id}>
            <tab.component />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
