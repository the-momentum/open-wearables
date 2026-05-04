import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface PageHeaderProps {
  title: string;
  description?: string;
  /** Optional content rendered on the right (typically a primary action button). */
  action?: ReactNode;
  /** Optional badge displayed above the title (e.g. "Live", "Beta"). */
  badge?: ReactNode;
  className?: string;
}

/**
 * Consistent page header used across authenticated routes.
 * Provides a gradient-tinted title and matching description, with an optional
 * action slot on the right. Uses design tokens only (no hardcoded colors).
 */
export function PageHeader({
  title,
  description,
  action,
  badge,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-4 md:flex-row md:items-end md:justify-between',
        className
      )}
    >
      <div>
        {badge ? <div className="mb-2">{badge}</div> : null}
        <h1 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">
          {title}
        </h1>
        {description ? (
          <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action ? (
        <div className="flex shrink-0 items-center gap-3">{action}</div>
      ) : null}
    </div>
  );
}
