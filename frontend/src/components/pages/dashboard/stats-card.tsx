import type { LucideIcon } from 'lucide-react';
import { NumberTicker } from '@/components/ui/number-ticker';
import { formatCompactNumber } from '@/lib/utils/format';
import { cn } from '@/lib/utils';

export type StatsCardAccent = 'cyan' | 'magenta' | 'purple' | 'green';

export interface StatsCardProps {
  title: string;
  value: number;
  suffix?: string;
  icon: LucideIcon;
  decimalPlaces?: number;
  format?: (value: number) => string;
  /** Optional compact sub-metrics shown as a small row at the bottom. */
  breakdown?: { label: string; value: number }[];
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
    iconBg: 'bg-primary-muted/12 border-primary-muted/25',
    iconColor: 'text-primary-muted',
  },
  magenta: {
    iconBg: 'bg-secondary-muted/12 border-secondary-muted/25',
    iconColor: 'text-secondary-muted',
  },
  purple: {
    iconBg: 'bg-accent-muted/12 border-accent-muted/25',
    iconColor: 'text-accent-muted',
  },
  green: {
    iconBg: 'bg-success-muted/12 border-success-muted/25',
    iconColor: 'text-success-muted',
  },
};

export function StatsCard({
  title,
  value,
  suffix,
  icon: Icon,
  decimalPlaces = 0,
  format,
  breakdown,
  accent = 'cyan',
  className,
}: StatsCardProps) {
  const styles = ACCENT_STYLES[accent];
  const hasBreakdown = !!breakdown?.length;

  return (
    <div
      className={cn(
        'group relative flex flex-col overflow-hidden rounded-2xl p-5',
        'bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl',
        'border border-border/60',
        'transition-all duration-300 ease-out',
        'hover:border-border-hover hover:-translate-y-0.5',
        className
      )}
    >
      <div className="flex items-start justify-between">
        <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {title}
        </span>
        <div
          className={cn(
            'flex h-9 w-9 items-center justify-center rounded-xl border',
            styles.iconBg
          )}
        >
          <Icon className={cn('h-4 w-4', styles.iconColor)} />
        </div>
      </div>

      {/* Value centered in the flexible middle so cards stay balanced even when stretched. */}
      <div className="flex flex-1 items-center justify-center py-4">
        <div className="flex items-baseline gap-1">
          <span className="text-3xl font-semibold tracking-tight text-foreground tabular-nums">
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
      </div>

      {/* Always reserve the bottom row (invisible placeholder when there's no breakdown) so the
          centered value sits at the same height on every card, with or without sub-metrics. */}
      <div
        className={cn(
          'flex border-t border-border/60 pt-4',
          !hasBreakdown && 'invisible'
        )}
        aria-hidden={!hasBreakdown || undefined}
      >
        {(hasBreakdown ? breakdown! : [{ label: ' ', value: 0 }]).map(
          (item) => (
            <div
              key={item.label}
              className="flex flex-1 flex-col items-center gap-0.5 text-center"
            >
              <span className="text-sm font-semibold tabular-nums text-foreground">
                {formatCompactNumber(item.value)}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {item.label}
              </span>
            </div>
          )
        )}
      </div>
    </div>
  );
}
