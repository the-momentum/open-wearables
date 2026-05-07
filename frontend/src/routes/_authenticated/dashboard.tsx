import { createFileRoute } from '@tanstack/react-router';
import { useDashboardStats } from '@/hooks/api/use-dashboard';
import { useUsers } from '@/hooks/api/use-users';
import { PageHeader } from '@/components/ui/page-header';
import {
  StatsGrid,
  DataMetricsSection,
  RecentUsersSection,
  DashboardLoadingState,
  DashboardErrorState,
} from '@/components/pages/dashboard';

export const Route = createFileRoute('/_authenticated/dashboard')({
  component: DashboardPage,
});

function DashboardPage() {
  const { data: stats, isLoading, error, refetch } = useDashboardStats();
  const { data: users, isLoading: isLoadingUsers } = useUsers({
    sort_by: 'created_at',
    sort_order: 'desc',
    limit: 5,
  });

  if (isLoading) {
    return <DashboardLoadingState />;
  }

  if (error || !stats) {
    return <DashboardErrorState onRetry={refetch} />;
  }

  return (
    <div className="relative min-h-full p-6 md:p-8">
      {/* Ambient background gradient (very subtle) */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute -left-32 top-0 h-72 w-72 rounded-full bg-[hsl(var(--primary)/0.04)] blur-3xl" />
        <div className="absolute right-0 bottom-0 h-72 w-72 rounded-full bg-[hsl(var(--accent)/0.03)] blur-3xl" />
      </div>

      <div className="relative space-y-6">
        <PageHeader
          title="Dashboard"
          description="Your platform overview and key metrics"
          badge={
            <div className="inline-flex items-center gap-2 rounded-full border border-[hsl(var(--success-muted)/0.3)] bg-[hsl(var(--success-muted)/0.08)] px-3 py-1">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[hsl(var(--success-muted))] opacity-60" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[hsl(var(--success-muted))]" />
              </span>
              <span className="text-[10px] font-medium uppercase tracking-wider text-[hsl(var(--success-muted))]">
                Live
              </span>
            </div>
          }
        />

        {/* Stats Grid */}
        <StatsGrid stats={stats} />

        {/* Charts Section */}
        <div className="grid gap-6 lg:grid-cols-7">
          <DataMetricsSection
            topSeriesTypes={stats.data_points.top_series_types}
            topWorkoutTypes={stats.data_points.top_workout_types}
            className="lg:col-span-4"
          />
          <RecentUsersSection
            users={users?.items ?? []}
            totalUsersCount={stats.total_users.count}
            isLoading={isLoadingUsers}
            className="lg:col-span-3"
          />
        </div>
      </div>
    </div>
  );
}
