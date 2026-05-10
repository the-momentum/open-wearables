import { cn } from '@/lib/utils';

interface SourceBadgeProps {
  provider: string;
  className?: string;
}

const PROVIDER_STYLES: Record<
  string,
  { bg: string; text: string; label: string }
> = {
  garmin: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'Garmin' },
  fitbit: { bg: 'bg-teal-500/20', text: 'text-teal-400', label: 'Fitbit' },
  oura: { bg: 'bg-violet-500/20', text: 'text-violet-400', label: 'Oura' },
  whoop: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: 'WHOOP' },
  strava: { bg: 'bg-orange-500/20', text: 'text-orange-400', label: 'Strava' },
  google: { bg: 'bg-green-500/20', text: 'text-green-400', label: 'Google' },
  'google-fit': {
    bg: 'bg-green-500/20',
    text: 'text-green-400',
    label: 'Google Fit',
  },
  withings: { bg: 'bg-cyan-500/20', text: 'text-cyan-400', label: 'Withings' },
  polar: { bg: 'bg-red-500/20', text: 'text-red-400', label: 'Polar' },
  suunto: { bg: 'bg-orange-600/20', text: 'text-orange-300', label: 'Suunto' },
  samsung: { bg: 'bg-sky-500/20', text: 'text-sky-400', label: 'Samsung' },
  ultrahuman: {
    bg: 'bg-purple-500/20',
    text: 'text-purple-400',
    label: 'Ultrahuman',
  },
  apple: { bg: 'bg-zinc-500/20', text: 'text-zinc-400', label: 'Apple' },
  internal: {
    bg: 'bg-[hsl(var(--success-muted)/0.15)]',
    text: 'text-[hsl(var(--success-muted))]',
    label: 'OW',
  },
};

const DEFAULT_STYLE = { bg: 'bg-muted/40', text: 'text-muted-foreground' };

export function SourceBadge({ provider, className = '' }: SourceBadgeProps) {
  const style = PROVIDER_STYLES[provider] ?? DEFAULT_STYLE;
  const label = PROVIDER_STYLES[provider]?.label ?? provider;

  return (
    <span
      className={cn(
        'inline-flex items-center text-[10px] font-medium leading-none px-2 py-1 rounded-md border border-current/20',
        style.bg,
        style.text,
        className
      )}
    >
      {label}
    </span>
  );
}
