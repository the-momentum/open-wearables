import { cn } from '@/lib/utils';

interface DataSummaryCardProps {
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
    <div className={cn("flex flex-col items-center justify-center text-center h-full", className)}>
      <div className="text-3xl font-medium text-white">
        {count}
      </div>
      <p className="text-xs text-zinc-500 mt-2">{label}</p>
      {mostRecentDate && (
        <div className="mt-4 pt-4 border-t border-zinc-800 w-full flex justify-center">
          <p className="text-xs text-zinc-500">
            Most recent: {new Date(mostRecentDate).toLocaleDateString()}
          </p>
        </div>
      )}
    </div>
  );
}
