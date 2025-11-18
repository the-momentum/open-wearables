import { FileQuestion } from 'lucide-react';
import { cn } from '../../lib/utils';

interface EmptyStateProps {
  title?: string;
  message?: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title = 'No data found',
  message = 'There is no data to display at this time.',
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center p-8 text-center',
        className
      )}
    >
      <div className="rounded-full bg-muted p-3">
        <FileQuestion className="h-6 w-6 text-muted-foreground" />
      </div>
      <h3 className="mt-4 text-lg font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-muted-foreground max-w-md">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
