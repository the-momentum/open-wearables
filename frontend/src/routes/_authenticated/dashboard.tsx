import { createFileRoute } from '@tanstack/react-router';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Users, Activity, Database, Zap } from 'lucide-react';
import { useDashboardStats } from '@/hooks/api/use-dashboard';
import { LoadingState } from '@/components/common/loading-spinner';
import { ErrorState } from '@/components/common/error-state';

export const Route = createFileRoute('/_authenticated/dashboard')({
  component: DashboardPage,
});

function DashboardPage() {
  const { data: stats, isLoading, error, refetch } = useDashboardStats();

  if (isLoading) {
    return (
      <div className="flex-1 p-8">
        <LoadingState message="Loading dashboard..." />
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex-1 p-8">
        <ErrorState
          message="Failed to load dashboard data. Please try again."
          onRetry={refetch}
        />
      </div>
    );
  }

  const statCards = [
    {
      title: 'Total Users',
      value: stats.totalUsers.toLocaleString(),
      description: 'Registered users',
      icon: Users,
    },
    {
      title: 'Active Connections',
      value: stats.activeConnections.toLocaleString(),
      description: 'Connected wearables',
      icon: Activity,
    },
    {
      title: 'Data Points',
      value: (stats.dataPoints / 1000).toFixed(1) + 'K',
      description: 'Health data collected',
      icon: Database,
    },
    {
      title: 'API Calls',
      value: (stats.apiCalls / 1000).toFixed(1) + 'K',
      description: 'This month',
      icon: Zap,
    },
  ];

  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between space-y-2">
        <h2 className="text-3xl font-bold tracking-tight">Dashboard</h2>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {stat.title}
              </CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-xs text-muted-foreground">
                {stat.description}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Recent Activity */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>Overview</CardTitle>
            <CardDescription>
              Your platform performance this month
            </CardDescription>
          </CardHeader>
          <CardContent className="pl-2">
            <div className="h-[300px] flex items-center justify-center text-muted-foreground">
              Chart will be rendered here
            </div>
          </CardContent>
        </Card>

        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>Recent Users</CardTitle>
            <CardDescription>You have 234 new users this month</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-8">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex items-center">
                  <div className="space-y-1">
                    <p className="text-sm font-medium leading-none">User {i}</p>
                    <p className="text-sm text-muted-foreground">
                      user{i}@example.com
                    </p>
                  </div>
                  <div className="ml-auto font-medium">Connected</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
