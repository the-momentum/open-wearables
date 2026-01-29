import { Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { GarminSummarySyncStatus } from '@/lib/api/types';
import { cn } from '@/lib/utils';

interface SyncProgressProps {
  status: GarminSummarySyncStatus;
  onCancel?: () => void;
  className?: string;
}

/**
 * Displays Garmin sync progress with visual feedback.
 * Shows progress bar, current operation, and cancel button.
 */
export function SyncProgress({
  status,
  onCancel,
  className,
}: SyncProgressProps) {
  const isActive = status.status === 'SYNCING' || status.status === 'WAITING';
  const isCompleted = status.status === 'COMPLETED';
  const hasFailed = status.status === 'FAILED';

  // Format data type for display (e.g., "stressDetails" -> "Stress Details")
  const formatDataType = (type: string): string => {
    return type
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, (str) => str.toUpperCase())
      .trim();
  };

  return (
    <div className={cn('space-y-2', className)}>
      {/* Progress bar */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
          <div
            className={cn(
              'h-full transition-all duration-300 ease-out rounded-full',
              isCompleted
                ? 'bg-green-500'
                : hasFailed
                  ? 'bg-destructive'
                  : 'bg-primary'
            )}
            style={{ width: `${Math.min(status.progress_percent, 100)}%` }}
          />
        </div>
        <span className="text-sm text-muted-foreground w-12 text-right">
          {status.progress_percent.toFixed(0)}%
        </span>
      </div>

      {/* Current operation and progress details */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          {isActive && <Loader2 className="h-3 w-3 animate-spin" />}
          <span>
            {status.status === 'WAITING'
              ? 'Waiting (rate limit)...'
              : status.status === 'COMPLETED'
                ? 'Sync complete'
                : status.status === 'FAILED'
                  ? 'Sync failed'
                  : `Syncing ${formatDataType(status.current_data_type)}`}
          </span>
        </div>
        <span>
          Type {status.current_type_index + 1}/{status.total_types} - Day{' '}
          {status.current_day}/{status.target_days}
        </span>
      </div>

      {/* Cancel button */}
      {isActive && onCancel && (
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
          onClick={onCancel}
        >
          <X className="h-3 w-3 mr-1" />
          Cancel sync
        </Button>
      )}

      {/* Latest error */}
      {status.errors.length > 0 && (
        <div className="text-xs text-destructive bg-destructive/10 rounded px-2 py-1">
          {status.errors[status.errors.length - 1].error}
        </div>
      )}
    </div>
  );
}
