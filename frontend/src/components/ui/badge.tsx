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
          'border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80 shadow-[0_0_10px_hsla(350,100%,55%,0.3)]',
        outline:
          'text-foreground border-primary/30 hover:border-primary/50 hover:shadow-[0_0_8px_hsla(185,100%,50%,0.2)]',
        success:
          'border-transparent bg-success text-success-foreground hover:bg-success/80 shadow-[0_0_10px_hsla(145,100%,50%,0.3)]',
        warning:
          'border-transparent bg-warning text-warning-foreground hover:bg-warning/80 shadow-[0_0_10px_hsla(45,100%,55%,0.3)]',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
