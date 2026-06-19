import { useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Info } from 'lucide-react';
import { useCoverage } from '@/hooks/api/use-coverage';
import { PageHeader } from '@/components/ui/page-header';
import { CoverageMatrix } from '@/components/pages/coverage/coverage-matrix';
import { ProviderDetail } from '@/components/pages/coverage/provider-detail';
import { SourceBadge } from '@/components/common/source-badge';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';

export const Route = createFileRoute('/_authenticated/coverage')({
  component: CoveragePage,
});

function LoadingSkeleton() {
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6">
        {Array.from({ length: 11 }).map((_, i) => (
          <Skeleton key={i} className="h-32 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-96 rounded-xl" />
    </div>
  );
}

function CoveragePage() {
  const { data, isLoading, error } = useCoverage();
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="relative min-h-full p-6 md:p-8">
      <div className="relative space-y-8 max-w-7xl">
        <PageHeader
          title="Data Coverage"
          description="What each provider is capable of delivering, by API layer."
        />

        <div className="flex items-start gap-2.5 rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-3 text-sm text-zinc-400">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-zinc-500" />
          <p>
            This matrix shows provider{' '}
            <span className="text-zinc-200">capabilities</span> — the data types
            Open Wearables can ingest from each provider. A green dot means the
            type is supported and normalized in code; it does{' '}
            <span className="text-zinc-200">not</span> reflect what has actually
            been synced for your users in this instance.
          </p>
        </div>

        {isLoading && <LoadingSkeleton />}

        {error && (
          <div className="rounded-lg border border-red-900/40 bg-red-950/20 px-4 py-3 text-sm text-red-400">
            Failed to load coverage data.
          </div>
        )}

        {data && (
          <div className="space-y-6">
            <div className="space-y-3">
              <p className="text-xs font-medium uppercase tracking-wider text-zinc-500">
                Inspect a provider
              </p>
              <div className="flex flex-wrap gap-2.5">
                {data.providers.map((p) => {
                  const active = selected === p;
                  return (
                    <button
                      key={p}
                      type="button"
                      aria-pressed={active}
                      onClick={() => setSelected(active ? null : p)}
                      className={cn(
                        'rounded-md transition-opacity duration-150',
                        active ? 'opacity-100' : 'opacity-40 hover:opacity-80'
                      )}
                    >
                      <SourceBadge provider={p} />
                    </button>
                  );
                })}
              </div>
            </div>

            {selected && <ProviderDetail data={data} provider={selected} />}

            <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
              <CoverageMatrix data={data} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
