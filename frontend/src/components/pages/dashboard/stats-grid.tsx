import { Users, Activity, Database, CalendarClock } from 'lucide-react';
import { StatsCard, type StatsCardProps } from './stats-card';
import { cn } from '@/lib/utils';
import { formatCompactNumber } from '@/lib/utils/format';
import type { DashboardStats } from '@/lib/api/types';

export interface StatsGridProps {
  stats: DashboardStats;
  className?: string;
}

export function StatsGrid({ stats, className }: StatsGridProps) {
  const cards: StatsCardProps[] = [
    {
      title: 'Total Users',
      value: stats.total_users.count,
      icon: Users,
      accent: 'cyan',
      format: formatCompactNumber,
    },
    {
      title: 'Active Connections',
      value: stats.active_conn.count,
      icon: Activity,
      accent: 'magenta',
      format: formatCompactNumber,
    },
    {
      title: 'Data Points',
      value: stats.data_points.count,
      icon: Database,
      accent: 'purple',
      format: formatCompactNumber,
      breakdown: [{ label: 'Archived', value: stats.data_points.archived }],
    },
    {
      title: 'Event Records',
      value: stats.event_records.count,
      icon: CalendarClock,
      accent: 'green',
      format: formatCompactNumber,
      breakdown: [
        { label: 'Workouts', value: stats.event_records.workouts },
        { label: 'Sleep', value: stats.event_records.sleep },
        { label: 'Cycles', value: stats.event_records.menstrual_cycles },
      ],
    },
  ];

  return (
    <div className={cn('grid gap-4 md:grid-cols-2 lg:grid-cols-4', className)}>
      {cards.map((card) => (
        <StatsCard key={card.title} {...card} />
      ))}
    </div>
  );
}
