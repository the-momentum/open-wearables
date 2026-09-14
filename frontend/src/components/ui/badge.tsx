import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/lib/utils';

const badgeVariants = cva(
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-primary text-primary-foreground hover:bg-primary/80 shadow-[0_0_10px_hsla(185,100%,50%,0.3)]',
        secondary:
          'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80 shadow-[0_0_10px_hsla(315,100%,60%,0.2)]',
        destructive:
          'border-destructive/30 bg-destructive/10 text-destructive-glow hover:bg-destructive/20',
        outline:
          'text-foreground border-primary/30 hover:border-primary/50 hover:shadow-[0_0_8px_hsla(185,100%,50%,0.2)]',
        success:
          'border-success/30 bg-success/10 text-success-glow hover:bg-success/20',
        warning:
          'border-warning/30 bg-warning/10 text-warning-glow hover:bg-warning/20',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface BadgeProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
