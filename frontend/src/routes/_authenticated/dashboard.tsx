import { createFileRoute } from '@tanstack/react-router';
import { Users, Activity, Database, TrendingUp, TrendingDown } from 'lucide-react';
import { useDashboardStats } from '@/hooks/api/use-dashboard';
import { useUsers } from '@/hooks/api/use-users';
import { NumberTicker } from '@/components/ui/number-ticker';

export const Route = createFileRoute('/_authenticated/dashboard')({
  component: DashboardPage,
});

function DashboardPage() {
  const { data: stats, isLoading, error, refetch } = useDashboardStats();
  const { data: users, isLoading: isLoadingUsers } = useUsers();

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-medium text-white">Dashboard</h1>
          <p className="text-sm text-zinc-500 mt-1">Your platform overview</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6"
            >
              <div className="animate-pulse space-y-3">
                <div className="h-4 w-24 bg-zinc-800 rounded" />
                <div className="h-8 w-16 bg-zinc-800 rounded" />
                <div className="h-3 w-32 bg-zinc-800/50 rounded" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="p-8">
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
          <p className="text-zinc-400 mb-4">
            Failed to load dashboard data. Please try again.
          </p>
          <button
            onClick={() => refetch()}
            className="px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const statCards = [
    {
      title: 'Total Users',
      value: stats.total_users.count,
      suffix: '',
      description: 'Registered users',
      icon: Users,
      growth: stats.total_users.weekly_growth,
    },
    {
      title: 'Active Connections',
      value: stats.active_conn.count,
      suffix: '',
      description: 'Connected wearables',
      icon: Activity,
      growth: stats.active_conn.weekly_growth,
    },
    {
      title: 'Data Points',
      value: stats.data_points.count / 1000,
      suffix: 'K',
      description: 'Health data collected',
      icon: Database,
      decimalPlaces: 1,
      growth: stats.data_points.weekly_growth,
    },
  ];

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
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {statCards.map((stat) => (
          <div
            key={stat.title}
            className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6 hover:border-zinc-700 transition-colors group"
          >
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm font-medium text-zinc-400">
                {stat.title}
              </span>
              <stat.icon className="h-4 w-4 text-zinc-600 group-hover:text-zinc-400 transition-colors" />
            </div>
            <div className="text-2xl font-medium text-white">
              <NumberTicker
                value={stat.value}
                decimalPlaces={stat.decimalPlaces || 0}
                className="text-white"
              />
              {stat.suffix && (
                <span className="text-zinc-500 ml-0.5">{stat.suffix}</span>
              )}
            </div>
            <div className="flex items-center justify-between mt-2">
              <p className="text-xs text-zinc-500">{stat.description}</p>
              {stat.growth !== undefined && (
                <div
                  className={`flex items-center text-xs ${
                    stat.growth >= 0 ? 'text-emerald-400' : 'text-red-400'
                  }`}
                >
                  {stat.growth >= 0 ? (
                    <TrendingUp className="h-3 w-3 mr-1" />
                  ) : (
                    <TrendingDown className="h-3 w-3 mr-1" />
                  )}
                  <span>{Math.abs(stat.growth).toFixed(1)}%</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Charts Section */}
      <div className="grid gap-6 lg:grid-cols-7">
        {/* Data Points Metrics */}
        <div className="lg:col-span-4 bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800">
            <h2 className="text-sm font-medium text-white">Data Points Metrics</h2>
            <p className="text-xs text-zinc-500 mt-1">
              Breakdown by series type and workout type
            </p>
          </div>
          <div className="p-6 space-y-6">
            {/* Top Series Types */}
            <div>
              <h3 className="text-xs font-medium text-zinc-400 mb-3">Top Series Types</h3>
              <div className="space-y-2">
                {stats.data_points.top_series_types.length > 0 ? (
                  stats.data_points.top_series_types.map((metric, index) => (
                    <div key={metric.series_type} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-zinc-500 w-4">{index + 1}.</span>
                        <span className="text-sm text-zinc-300 capitalize">
                          {metric.series_type.replace(/_/g, ' ')}
                        </span>
                      </div>
                      <span className="text-sm font-medium text-white">
                        {metric.count.toLocaleString()}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-zinc-600">No data available</p>
                )}
              </div>
            </div>

            {/* Top Workout Types */}
            <div>
              <h3 className="text-xs font-medium text-zinc-400 mb-3">Top Workout Types</h3>
              <div className="space-y-2">
                {stats.data_points.top_workout_types.length > 0 ? (
                  stats.data_points.top_workout_types.map((metric, index) => (
                    <div key={metric.workout_type || 'unknown'} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-zinc-500 w-4">{index + 1}.</span>
                        <span className="text-sm text-zinc-300">
                          {metric.workout_type || 'Unknown'}
                        </span>
                      </div>
                      <span className="text-sm font-medium text-white">
                        {metric.count.toLocaleString()}
                      </span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-zinc-600">No data available</p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Recent Users */}
        <div className="lg:col-span-3 bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800">
            <h2 className="text-sm font-medium text-white">Recent Users</h2>
            <p className="text-xs text-zinc-500 mt-1">
              Total users: {stats.total_users.count}
            </p>
          </div>
          <div className="p-6 space-y-4">
            {isLoadingUsers ? (
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="animate-pulse">
                    <div className="h-4 w-32 bg-zinc-800 rounded mb-1" />
                    <div className="h-3 w-48 bg-zinc-800/50 rounded" />
                  </div>
                ))}
              </div>
            ) : users && users.length > 0 ? (
              users
                .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                .slice(0, 5)
                .map((user) => {
                  const userName = user.first_name || user.last_name
                    ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
                    : user.email || 'Unknown User';
                  const createdDate = new Date(user.created_at);
                  const formattedDate = createdDate.toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  });
                  return (
                    <div key={user.id} className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-medium text-zinc-300">{userName}</p>
                        <p className="text-xs text-zinc-500">
                          {user.email || user.external_user_id || 'No email'}
                        </p>
                        <p className="text-xs text-zinc-600 mt-0.5">
                          Created on {formattedDate}
                        </p>
                      </div>
                      <span className="text-xs text-emerald-400">Active</span>
                    </div>
                  );
                })
            ) : (
              <div className="flex items-center justify-center h-[200px] text-zinc-600">
                <p className="text-sm">No users found</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
