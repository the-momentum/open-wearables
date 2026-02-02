import { Loader2, Database } from 'lucide-react';
import {
  useUserDataSources,
  useUpdateDataSourceEnabled,
} from '@/hooks/api/use-priorities';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import type { DataSource } from '@/lib/api/services/priority.service';

// Device type icons and labels
const DEVICE_TYPE_INFO: Record<
  string,
  { label: string; icon: string; color: string }
> = {
  watch: { label: 'Watch', icon: '⌚', color: 'text-blue-400' },
  band: { label: 'Band', icon: '📿', color: 'text-purple-400' },
  ring: { label: 'Ring', icon: '💍', color: 'text-amber-400' },
  phone: { label: 'Phone', icon: '📱', color: 'text-green-400' },
  scale: { label: 'Scale', icon: '⚖️', color: 'text-cyan-400' },
  other: { label: 'Other', icon: '📊', color: 'text-zinc-400' },
  unknown: { label: 'Unknown', icon: '❓', color: 'text-zinc-500' },
};

interface DataSourceItemProps {
  dataSource: DataSource;
  userId: string;
}

function DataSourceItem({ dataSource, userId }: DataSourceItemProps) {
  const updateMutation = useUpdateDataSourceEnabled();

  const deviceInfo =
    DEVICE_TYPE_INFO[dataSource.device_type || 'unknown'] ||
    DEVICE_TYPE_INFO.unknown;

  const handleToggle = () => {
    updateMutation.mutate({
      userId,
      dataSourceId: dataSource.id,
      isEnabled: !dataSource.is_enabled,
    });
  };

  return (
    <div className="flex items-center justify-between px-4 py-3 bg-zinc-900/30 border border-zinc-800/50 rounded-lg">
      <div className="flex items-center gap-3">
        <span className="text-xl" title={deviceInfo.label}>
          {deviceInfo.icon}
        </span>
        <div>
          <div className="text-white font-medium">
            {dataSource.display_name || dataSource.device_model || 'Unknown'}
          </div>
          <div className="text-xs text-zinc-500 flex items-center gap-2">
            {dataSource.source && (
              <span className="bg-zinc-800 px-1.5 py-0.5 rounded">
                {dataSource.source}
              </span>
            )}
            {dataSource.original_source_name && (
              <span>via {dataSource.original_source_name}</span>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-xs text-zinc-500">
          {dataSource.is_enabled ? 'Enabled' : 'Disabled'}
        </span>
        <Switch
          checked={dataSource.is_enabled}
          onCheckedChange={handleToggle}
          disabled={updateMutation.isPending}
        />
      </div>
    </div>
  );
}

interface DataSourcesSectionProps {
  userId: string;
}

export function DataSourcesSection({ userId }: DataSourcesSectionProps) {
  const {
    data: dataSources,
    isLoading,
    error,
    refetch,
  } = useUserDataSources(userId);

  if (isLoading) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8">
        <div className="flex items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8 text-center">
        <p className="text-zinc-400 mb-4">Failed to load data sources</p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  if (!dataSources || dataSources.length === 0) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8 text-center">
        <Database className="h-8 w-8 text-zinc-600 mx-auto mb-3" />
        <p className="text-zinc-400">No data sources found</p>
        <p className="text-xs text-zinc-500 mt-1">
          Data sources are created when health data is synced
        </p>
      </div>
    );
  }

  const enabledCount = dataSources.filter((ds) => ds.is_enabled).length;

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-medium text-white flex items-center gap-2">
            <Database className="h-4 w-4" />
            Data Sources
          </h3>
          <p className="text-xs text-zinc-500 mt-0.5">
            {enabledCount} of {dataSources.length} enabled
          </p>
        </div>
      </div>

      <div className="p-3 space-y-2">
        {dataSources.map((ds) => (
          <DataSourceItem key={ds.id} dataSource={ds} userId={userId} />
        ))}
      </div>

      <div className="px-4 py-3 border-t border-zinc-800/50 bg-zinc-800/20">
        <p className="text-xs text-zinc-500">
          Disabled data sources won't appear in summaries or timeseries data.
          Data is preserved and can be re-enabled anytime.
        </p>
      </div>
    </div>
  );
}
