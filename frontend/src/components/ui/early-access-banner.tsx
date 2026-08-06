import { useState } from 'react';
import { FlaskConical, X } from 'lucide-react';

export function EarlyAccessBanner() {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  return (
    <div className="relative flex items-center gap-3 px-4 py-2.5 bg-warning-muted/10 border border-warning-muted/20 rounded-lg text-warning-muted">
      <FlaskConical className="h-4 w-4 shrink-0 text-warning-muted" />
      <p className="flex-1 text-xs font-medium">
        <span className="font-semibold text-warning-muted">Early Access</span>
        {' — '}
        This feature is not yet ready for production use.
      </p>
      <button
        onClick={() => setVisible(false)}
        className="shrink-0 rounded p-0.5 text-warning-muted/60 hover:text-warning-muted hover:bg-warning-muted/10 transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
