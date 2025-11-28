import { createFileRoute } from '@tanstack/react-router';
import { Users, Activity, Database, Zap } from 'lucide-react';
import { useDashboardStats } from '@/hooks/api/use-dashboard';
import { NumberTicker } from '@/components/ui/number-ticker';

export const Route = createFileRoute('/_authenticated/dashboard')({
  component: DashboardPage,
});

function DashboardPage() {
  const { data: stats, isLoading, error, refetch } = useDashboardStats();

  if (isLoading) {
    return (
      <div className="p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-medium text-white">Dashboard</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Your platform overview
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
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
      value: stats.totalUsers,
      suffix: '',
      description: 'Registered users',
      icon: Users,
    },
    {
      title: 'Active Connections',
      value: stats.activeConnections,
      suffix: '',
      description: 'Connected wearables',
      icon: Activity,
    },
    {
      title: 'Data Points',
      value: stats.dataPoints / 1000,
      suffix: 'K',
      description: 'Health data collected',
      icon: Database,
      decimalPlaces: 1,
    },
    {
      title: 'API Calls',
      value: stats.apiCalls / 1000,
      suffix: 'K',
      description: 'This month',
      icon: Zap,
      decimalPlaces: 1,
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
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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
            <p className="text-xs text-zinc-500 mt-2">{stat.description}</p>
          </div>
        ))}
      </div>

      {/* Charts Section */}
      <div className="grid gap-6 lg:grid-cols-7">
        {/* Overview Chart */}
        <div className="lg:col-span-4 bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800">
            <h2 className="text-sm font-medium text-white">Overview</h2>
            <p className="text-xs text-zinc-500 mt-1">
              Your platform performance this month
            </p>
          </div>
          <div className="h-[300px] flex items-center justify-center text-zinc-600">
            <p className="text-sm">Chart will be rendered here</p>
          </div>
        </div>

        {/* Recent Users */}
        <div className="lg:col-span-3 bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800">
            <h2 className="text-sm font-medium text-white">Recent Users</h2>
            <p className="text-xs text-zinc-500 mt-1">
              You have 234 new users this month
            </p>
          </div>
          <div className="p-6 space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-zinc-300">User {i}</p>
                  <p className="text-xs text-zinc-500">user{i}@example.com</p>
                </div>
                <span className="text-xs text-emerald-400">Connected</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
