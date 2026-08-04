import { Users, Activity, Database } from 'lucide-react';
import { StatsCard, type StatsCardAccent } from './stats-card';
import { cn } from '@/lib/utils';
import { formatCompactNumber } from '@/lib/utils/format';
import type { DashboardStats } from '@/lib/api/types';

export interface StatsGridProps {
  stats: DashboardStats;
  className?: string;
}

export function StatsGrid({ stats, className }: StatsGridProps) {
  const statCards: Array<{
    title: string;
    value: number;
    description: string;
    icon: typeof Users;
    accent: StatsCardAccent;
  }> = [
    {
      title: 'Total Users',
      value: stats.total_users.count,
      description: 'Registered users',
      icon: Users,
      accent: 'cyan',
    },
    {
      title: 'Active Connections',
      value: stats.active_conn.count,
      description: 'Connected wearables',
      icon: Activity,
      accent: 'magenta',
    },
    {
      title: 'Data Points',
      value: stats.data_points.count,
      description: 'Health data collected',
      icon: Database,
      accent: 'purple',
    },
  ];

  return (
    <div className={cn('grid gap-4 md:grid-cols-2 lg:grid-cols-3', className)}>
      {statCards.map((stat) => (
        <StatsCard
          key={stat.title}
          title={stat.title}
          value={stat.value}
          description={stat.description}
          icon={stat.icon}
          format={formatCompactNumber}
          accent={stat.accent}
        />
      ))}
    </div>
  );
}
