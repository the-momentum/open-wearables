import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

interface LoadingSpinnerProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}

export function LoadingSpinner({
  className,
  size = 'md',
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'h-4 w-4',
    md: 'h-6 w-6',
    lg: 'h-8 w-8',
  };

  return (
    <Loader2
      className={cn(
        'animate-spin text-primary drop-shadow-[0_0_8px_hsla(185,100%,60%,0.6)]',
        sizeClasses[size],
        className
      )}
    />
  );
}

interface LoadingStateProps {
  message?: string;
  className?: string;
}

export function LoadingState({
  message = 'Loading...',
  className,
}: LoadingStateProps) {
  return (
    <div
      className={cn('flex flex-col items-center justify-center p-8', className)}
    >
      <div className="relative">
        <LoadingSpinner size="lg" />
        <div className="absolute inset-0 animate-pulse-glow rounded-full bg-primary/20 blur-xl" />
      </div>
      <p className="mt-4 text-sm text-muted-foreground">{message}</p>
    </div>
  );
}
