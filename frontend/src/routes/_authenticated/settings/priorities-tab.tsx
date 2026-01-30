import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  useProviderPriorities,
  useBulkUpdateProviderPriorities,
} from '@/hooks/api/use-priorities';
import { Loader2, CheckCircle2, ChevronUp, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ProviderPriority } from '@/lib/api/services/priority.service';

// Provider display info
const PROVIDER_INFO: Record<string, { name: string; color: string }> = {
  apple: { name: 'Apple Health', color: 'bg-gray-500' },
  garmin: { name: 'Garmin', color: 'bg-blue-500' },
  polar: { name: 'Polar', color: 'bg-red-500' },
  suunto: { name: 'Suunto', color: 'bg-orange-500' },
  whoop: { name: 'WHOOP', color: 'bg-teal-500' },
  oura: { name: 'Oura', color: 'bg-purple-500' },
};

interface ProviderItemProps {
  provider: ProviderPriority;
  index: number;
  total: number;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

function ProviderItem({
  provider,
  index,
  total,
  onMoveUp,
  onMoveDown,
}: ProviderItemProps) {
  const info = PROVIDER_INFO[provider.provider] || {
    name: provider.provider,
    color: 'bg-zinc-500',
  };

  return (
    <div className="flex items-center gap-4 px-4 py-3 bg-zinc-900/50 border border-zinc-800 rounded-lg">
      <div className="flex flex-col gap-0.5">
        <button
          onClick={onMoveUp}
          disabled={index === 0}
          className="p-0.5 text-zinc-500 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
          title="Move up"
        >
          <ChevronUp className="h-4 w-4" />
        </button>
        <button
          onClick={onMoveDown}
          disabled={index === total - 1}
          className="p-0.5 text-zinc-500 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
          title="Move down"
        >
          <ChevronDown className="h-4 w-4" />
        </button>
      </div>

      <div className="flex items-center gap-3 flex-1">
        <div className={`w-3 h-3 rounded-full ${info.color}`} />
        <span className="text-white font-medium">{info.name}</span>
      </div>

      <div className="text-sm text-zinc-500">Priority {index + 1}</div>
    </div>
  );
}

export function PrioritiesTab() {
  const {
    data: priorities,
    isLoading,
    error,
    refetch,
  } = useProviderPriorities();
  const updateMutation = useBulkUpdateProviderPriorities();

  const [localOrder, setLocalOrder] = useState<ProviderPriority[]>([]);
  const [hasInitialized, setHasInitialized] = useState(false);

  useEffect(() => {
    if (priorities && priorities.length > 0 && !hasInitialized) {
      setLocalOrder(priorities);
      setHasInitialized(true);
    }
  }, [priorities, hasInitialized]);

  const hasChanges = useMemo(() => {
    if (!priorities || !localOrder.length) return false;

    return localOrder.some(
      (p, index) =>
        priorities.findIndex((orig) => orig.provider === p.provider) !== index
    );
  }, [priorities, localOrder]);

  const handleMoveUp = useCallback((index: number) => {
    if (index === 0) return;
    setLocalOrder((items) => {
      const newItems = [...items];
      [newItems[index - 1], newItems[index]] = [
        newItems[index],
        newItems[index - 1],
      ];
      return newItems;
    });
  }, []);

  const handleMoveDown = useCallback((index: number) => {
    setLocalOrder((items) => {
      if (index >= items.length - 1) return items;
      const newItems = [...items];
      [newItems[index], newItems[index + 1]] = [
        newItems[index + 1],
        newItems[index],
      ];
      return newItems;
    });
  }, []);

  const handleSave = async () => {
    if (!localOrder.length) return;

    const newPriorities = localOrder.map((p, index) => ({
      provider: p.provider,
      priority: index + 1,
    }));

    await updateMutation.mutateAsync({ priorities: newPriorities });
    setHasInitialized(false); // Force refresh from server
  };

  if (isLoading) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12">
        <div className="flex items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
        <p className="text-zinc-400 mb-4">Failed to load provider priorities</p>
        <Button variant="outline" onClick={() => refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-medium text-white">
            Provider Priorities
          </h2>
          <p className="text-sm text-zinc-500 mt-1">
            Use arrows to reorder which data providers take priority when data
            overlaps
          </p>
        </div>
        {hasChanges && (
          <Button onClick={handleSave} disabled={updateMutation.isPending}>
            {updateMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4" />
                Save Changes
              </>
            )}
          </Button>
        )}
      </div>

      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <h3 className="text-sm font-medium text-white">Priority Order</h3>
          <p className="text-xs text-zinc-500 mt-1">
            Higher priority providers are used when multiple sources have the
            same data
          </p>
        </div>

        <div className="p-4 space-y-2">
          {localOrder.map((provider, index) => (
            <ProviderItem
              key={provider.provider}
              provider={provider}
              index={index}
              total={localOrder.length}
              onMoveUp={() => handleMoveUp(index)}
              onMoveDown={() => handleMoveDown(index)}
            />
          ))}
        </div>
      </div>

      <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-lg p-4">
        <h4 className="text-sm font-medium text-zinc-300 mb-2">
          How priorities work
        </h4>
        <ul className="text-xs text-zinc-500 space-y-1">
          <li>
            • When data from multiple providers overlaps in time, the higher
            priority provider's data is shown
          </li>
          <li>
            • Within the same provider, watch data is preferred over phone data
          </li>
          <li>
            • Users can still disable specific data sources from their profile
          </li>
        </ul>
      </div>
    </div>
  );
}
