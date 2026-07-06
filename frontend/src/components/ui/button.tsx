import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 cursor-pointer',
  {
    variants: {
      variant: {
        default:
          'bg-white text-black hover:bg-zinc-200 border border-transparent',
        destructive:
          'bg-[hsl(var(--destructive-muted)/0.1)] text-[hsl(var(--destructive-muted))] border border-red-500/30 hover:border-red-500/50 hover:shadow-[0_0_15px_hsla(350,100%,55%,0.3)]',
        'destructive-outline':
          'border border-border/50 bg-background hover:bg-card hover:border-red-500/50 hover:text-[hsl(var(--destructive-muted))] hover:shadow-[0_0_10px_hsla(350,100%,55%,0.2)]',
        outline:
          'border border-border/50 bg-background hover:bg-card hover:border-primary/50 hover:shadow-[0_0_10px_hsla(185,100%,50%,0.2)]',
        secondary:
          'bg-muted text-foreground hover:bg-muted-foreground/40 border border-border/50',
        ghost:
          'border border-transparent hover:border-border/50 hover:bg-card hover:text-foreground hover:shadow-[0_0_8px_hsla(185,100%,50%,0.15)]',
        'ghost-faded':
          'border border-transparent text-muted-foreground hover:border-border/50 hover:bg-card hover:text-foreground/90 hover:shadow-[0_0_8px_hsla(185,100%,50%,0.15)]',
        link: 'text-primary underline-offset-4 hover:underline',
        neon: 'bg-primary text-primary-foreground border border-border/50 hover:bg-primary-hover hover:shadow-[0_0_20px_hsla(185,100%,50%,0.4)] transition-all duration-300 ease-out active:scale-[0.98]',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-md px-3',
        lg: 'h-11 rounded-md px-8',
        icon: 'h-10 w-10',
        'icon-sm': 'h-8 w-8',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
);

export interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button';
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button, buttonVariants };
