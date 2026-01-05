import { createFileRoute } from '@tanstack/react-router';
import { useDashboardStats } from '@/hooks/api/use-dashboard';
import { useUsers } from '@/hooks/api/use-users';
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
    <div className="p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-medium text-white">Dashboard</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Your platform overview and key metrics
        </p>
      </div>

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
  );
}
