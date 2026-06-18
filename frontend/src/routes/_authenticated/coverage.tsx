import { createFileRoute } from '@tanstack/react-router';
import { useCoverage } from '@/hooks/api/use-coverage';
import { PageHeader } from '@/components/ui/page-header';
import { CoverageMatrix } from '@/components/pages/coverage/coverage-matrix';
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

  return (
    <div className="relative min-h-full p-6 md:p-8">
      <div className="relative space-y-8 max-w-7xl">
        <PageHeader
          title="Data Coverage"
          description="What data each provider delivers, by API layer."
        />

        {isLoading && <LoadingSkeleton />}

        {error && (
          <div className="rounded-lg border border-red-900/40 bg-red-950/20 px-4 py-3 text-sm text-red-400">
            Failed to load coverage data.
          </div>
        )}

        {data && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
            <CoverageMatrix data={data} />
          </div>
        )}
      </div>
    </div>
  );
}
