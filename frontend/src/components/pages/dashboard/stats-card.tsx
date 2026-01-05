import type { LucideIcon } from 'lucide-react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { NumberTicker } from '@/components/ui/number-ticker';
import { cn } from '@/lib/utils';

export interface StatsCardProps {
  title: string;
  value: number;
  suffix?: string;
  description: string;
  icon: LucideIcon;
  growth?: number;
  decimalPlaces?: number;
  className?: string;
}

export function StatsCard({
  title,
  value,
  suffix,
  description,
  icon: Icon,
  growth,
  decimalPlaces = 0,
  className,
}: StatsCardProps) {
  return (
    <div
      className={cn(
        'bg-zinc-900/50 border border-zinc-800 rounded-xl p-6',
        'hover:border-zinc-700 transition-colors group',
        className
      )}
    >
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-zinc-400">{title}</span>
        <Icon className="h-4 w-4 text-zinc-600 group-hover:text-zinc-400 transition-colors" />
      </div>
      <div className="text-2xl font-medium text-white">
        <NumberTicker
          value={value}
          decimalPlaces={decimalPlaces}
          className="text-white"
        />
        {suffix && <span className="text-zinc-500 ml-0.5">{suffix}</span>}
      </div>
      <div className="flex items-center justify-between mt-2">
        <p className="text-xs text-zinc-500">{description}</p>
        {growth !== undefined && (
          <div
            className={cn(
              'flex items-center text-xs',
              growth >= 0 ? 'text-emerald-400' : 'text-red-400'
            )}
          >
            {growth >= 0 ? (
              <TrendingUp className="h-3 w-3 mr-1" />
            ) : (
              <TrendingDown className="h-3 w-3 mr-1" />
            )}
            <span>{Math.abs(growth).toFixed(1)}%</span>
          </div>
        )}
      </div>
    </div>
  );
}
