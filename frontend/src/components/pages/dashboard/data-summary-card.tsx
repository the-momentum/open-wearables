import { cn } from '@/lib/utils';

export interface DataSummaryCardProps {
  count: number;
  label: string;
  mostRecentDate?: string | null;
  className?: string;
}

export function DataSummaryCard({
  count,
  label,
  mostRecentDate,
  className,
}: DataSummaryCardProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center h-full',
        className
      )}
    >
      <div className="text-3xl font-medium text-foreground">{count}</div>
      <p className="text-xs text-muted-foreground mt-2">{label}</p>
      {mostRecentDate && (
        <div className="mt-4 pt-4 border-t border-border/60 w-full flex justify-center">
          <p className="text-xs text-muted-foreground">
            Most recent: {new Date(mostRecentDate).toLocaleDateString()}
          </p>
        </div>
      )}
    </div>
  );
}
