import { AlertTriangle, RefreshCw } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

export interface DashboardErrorStateProps {
  onRetry: () => void;
  className?: string;
}

export function DashboardErrorState({
  onRetry,
  className,
}: DashboardErrorStateProps) {
  return (
    <div className={cn('p-6 md:p-8', className)}>
      <div className="relative overflow-hidden rounded-2xl border border-[hsl(var(--destructive)/0.3)] bg-gradient-to-br from-card/80 to-card/40 p-12 text-center backdrop-blur-xl">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-12 -top-12 h-48 w-48 rounded-full bg-[hsl(var(--destructive)/0.15)] blur-3xl"
        />
        <div className="relative mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-[hsl(var(--destructive)/0.3)] bg-[hsl(var(--destructive)/0.1)]">
          <AlertTriangle className="h-6 w-6 text-[hsl(var(--destructive))]" />
        </div>
        <h2 className="relative text-lg font-semibold text-foreground">
          Something went wrong
        </h2>
        <p className="relative mb-6 mt-1 text-sm text-muted-foreground">
          Failed to load dashboard data. Please try again.
        </p>
        <Button variant="outline" onClick={onRetry} className="relative">
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    </div>
  );
}
