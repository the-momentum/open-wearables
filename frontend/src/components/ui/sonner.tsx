import {
  CircleCheck,
  Info,
  LoaderCircle,
  OctagonX,
  TriangleAlert,
} from 'lucide-react';
import { Toaster as Sonner } from 'sonner';

type ToasterProps = React.ComponentProps<typeof Sonner>;

const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="dark"
      className="toaster group"
      icons={{
        success: <CircleCheck className="h-4 w-4" />,
        info: <Info className="h-4 w-4" />,
        warning: <TriangleAlert className="h-4 w-4" />,
        error: <OctagonX className="h-4 w-4" />,
        loading: <LoaderCircle className="h-4 w-4 animate-spin" />,
      }}
      toastOptions={{
        classNames: {
          toast:
            'group toast group-[.toaster]:bg-card group-[.toaster]:text-foreground group-[.toaster]:border-border/50 group-[.toaster]:shadow-lg',
          description: 'group-[.toast]:text-muted-foreground',
          actionButton:
            'group-[.toast]:bg-primary group-[.toast]:text-primary-foreground',
          cancelButton:
            'group-[.toast]:bg-muted group-[.toast]:text-muted-foreground',
          success:
            'group-[.toaster]:!bg-success/10 group-[.toaster]:!border-success/30 group-[.toaster]:!text-success',
          error:
            'group-[.toaster]:!bg-destructive/10 group-[.toaster]:!border-destructive/30 group-[.toaster]:!text-destructive',
          warning:
            'group-[.toaster]:!bg-warning/10 group-[.toaster]:!border-warning/30 group-[.toaster]:!text-warning',
          info: 'group-[.toaster]:!bg-primary/10 group-[.toaster]:!border-primary/30 group-[.toaster]:!text-primary',
        },
      }}
      {...props}
    />
  );
};

export { Toaster };
