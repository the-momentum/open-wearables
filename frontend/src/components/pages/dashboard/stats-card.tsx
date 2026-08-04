import type { LucideIcon } from 'lucide-react';
import { NumberTicker } from '@/components/ui/number-ticker';
import { cn } from '@/lib/utils';

export type StatsCardAccent = 'cyan' | 'magenta' | 'purple' | 'green';

export interface StatsCardProps {
  title: string;
  value: number;
  suffix?: string;
  description: string;
  icon: LucideIcon;
  decimalPlaces?: number;
  format?: (value: number) => string;
  accent?: StatsCardAccent;
  className?: string;
}

// Muted, single-tone accents for the icon chip only.
const ACCENT_STYLES: Record<
  StatsCardAccent,
  {
    iconBg: string;
    iconColor: string;
  }
> = {
  cyan: {
    iconBg:
      'bg-[hsl(var(--primary-muted)/0.12)] border-[hsl(var(--primary-muted)/0.25)]',
    iconColor: 'text-[hsl(var(--primary-muted))]',
  },
  magenta: {
    iconBg:
      'bg-[hsl(var(--secondary-muted)/0.12)] border-[hsl(var(--secondary-muted)/0.25)]',
    iconColor: 'text-[hsl(var(--secondary-muted))]',
  },
  purple: {
    iconBg:
      'bg-[hsl(var(--accent-muted)/0.12)] border-[hsl(var(--accent-muted)/0.25)]',
    iconColor: 'text-[hsl(var(--accent-muted))]',
  },
  green: {
    iconBg:
      'bg-[hsl(var(--success-muted)/0.12)] border-[hsl(var(--success-muted)/0.25)]',
    iconColor: 'text-[hsl(var(--success-muted))]',
  },
};

export function StatsCard({
  title,
  value,
  suffix,
  description,
  icon: Icon,
  decimalPlaces = 0,
  format,
  accent = 'cyan',
  className,
}: StatsCardProps) {
  const styles = ACCENT_STYLES[accent];

  return (
    <div
      className={cn(
        'group relative overflow-hidden rounded-2xl p-6',
        'bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl',
        'border border-border/60',
        'transition-all duration-300 ease-out',
        'hover:border-border-hover hover:-translate-y-0.5',
        className
      )}
    >
      <div className="flex items-start justify-between mb-5">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {title}
        </span>
        <div
          className={cn(
            'flex h-10 w-10 items-center justify-center rounded-xl border',
            styles.iconBg
          )}
        >
          <Icon className={cn('h-5 w-5', styles.iconColor)} />
        </div>
      </div>

      <div className="flex items-baseline gap-1">
        <span className="text-4xl font-semibold tracking-tight text-foreground tabular-nums">
          <NumberTicker
            value={value}
            decimalPlaces={decimalPlaces}
            format={format}
            className="text-foreground"
          />
        </span>
        {suffix && (
          <span className="text-xl font-medium text-muted-foreground">
            {suffix}
          </span>
        )}
      </div>

      <div className="mt-4">
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}
