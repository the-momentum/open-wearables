import { useState } from 'react';
import { FlaskConical, X } from 'lucide-react';

export function EarlyAccessBanner() {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  return (
    <div className="relative flex items-center gap-3 px-4 py-2.5 bg-[hsl(var(--warning-muted)/0.1)] border border-[hsl(var(--warning-muted)/0.2)] rounded-lg text-[hsl(var(--warning-muted))]">
      <FlaskConical className="h-4 w-4 shrink-0 text-[hsl(var(--warning-muted))]" />
      <p className="flex-1 text-xs font-medium">
        <span className="font-semibold text-[hsl(var(--warning-muted))]">
          Early Access
        </span>
        {' — '}
        This feature is not yet ready for production use.
      </p>
      <button
        onClick={() => setVisible(false)}
        className="shrink-0 rounded p-0.5 text-[hsl(var(--warning-muted))]/60 hover:text-[hsl(var(--warning-muted))] hover:bg-[hsl(var(--warning-muted)/0.1)] transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
