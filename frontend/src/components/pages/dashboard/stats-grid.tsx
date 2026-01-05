import { Users, Activity, Database } from 'lucide-react';
import { StatsCard } from './stats-card';
import { cn } from '@/lib/utils';
import type { DashboardStats } from '@/lib/api/types';

export interface StatsGridProps {
  stats: DashboardStats;
  className?: string;
}

export function StatsGrid({ stats, className }: StatsGridProps) {
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
    <div className={cn('grid gap-4 md:grid-cols-2 lg:grid-cols-3', className)}>
      {statCards.map((stat) => (
        <StatsCard
          key={stat.title}
          title={stat.title}
          value={stat.value}
          suffix={stat.suffix}
          description={stat.description}
          icon={stat.icon}
          growth={stat.growth}
          decimalPlaces={stat.decimalPlaces}
        />
      ))}
    </div>
  );
}
