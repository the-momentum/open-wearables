import { useState } from 'react';
import { FlaskConical, X } from 'lucide-react';

export function EarlyAccessBanner() {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  return (
    <div className="relative flex items-center gap-3 px-4 py-2.5 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-300">
      <FlaskConical className="h-4 w-4 shrink-0 text-amber-400" />
      <p className="flex-1 text-xs font-medium">
        <span className="font-semibold text-amber-200">Early Access</span>
        {' — '}
        This feature is not yet ready for production use.
      </p>
      <button
        onClick={() => setVisible(false)}
        className="shrink-0 rounded p-0.5 text-amber-400/60 hover:text-amber-300 hover:bg-amber-500/10 transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
