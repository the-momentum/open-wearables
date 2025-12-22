import { cn } from '@/lib/utils';

export type DateRangeValue = 7 | 30 | 90 | 365;

interface DateRangeSelectorProps {
  value: DateRangeValue;
  onChange: (value: DateRangeValue) => void;
  className?: string;
}

export function DateRangeSelector({
  value,
  onChange,
  className,
}: DateRangeSelectorProps) {
  const ranges: DateRangeValue[] = [7, 30, 90, 365];

  return (
    <div
      className={cn(
        'flex items-center gap-1 bg-zinc-800/50 p-1 rounded-lg',
        className
      )}
    >
      {ranges.map((days) => (
        <button
          key={days}
          onClick={() => onChange(days)}
          className={cn(
            'px-2 py-1 text-xs font-medium rounded-md transition-colors',
            value === days
              ? 'bg-zinc-700 text-white'
              : 'text-zinc-400 hover:text-zinc-300 hover:bg-zinc-800'
          )}
        >
          {days}d
        </button>
      ))}
    </div>
  );
}
