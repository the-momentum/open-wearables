import { useState } from 'react';
import { Check, Copy, Eye, EyeOff, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useWebhookSecret } from '@/hooks/api/use-webhooks';
import { copyToClipboard } from '@/lib/utils/clipboard';

interface WebhookSecretRevealProps {
  endpointId: string;
}

export function WebhookSecretReveal({ endpointId }: WebhookSecretRevealProps) {
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState(false);

  const { data, isLoading, error } = useWebhookSecret(endpointId, {
    enabled: revealed,
  });

  const handleCopy = async () => {
    if (!data?.key) return;
    const ok = await copyToClipboard(data.key);
    if (ok) {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  return (
    <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-5 space-y-3">
      <div>
        <h3 className="text-sm font-medium text-foreground">Signing secret</h3>
        <p className="text-xs text-muted-foreground mt-0.5">
          Use this secret to verify the <code>svix-signature</code> header on
          incoming webhook requests.
        </p>
      </div>

      {!revealed && (
        <Button variant="outline" size="sm" onClick={() => setRevealed(true)}>
          <Eye className="h-4 w-4" />
          Reveal secret
        </Button>
      )}

      {revealed && isLoading && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground py-2">
          <Loader2 className="h-3 w-3 animate-spin" />
          Loading secret...
        </div>
      )}

      {revealed && error && (
        <p className="text-xs text-[hsl(var(--destructive-muted))]">
          Failed to load secret.
        </p>
      )}

      {revealed && data && (
        <div className="flex items-center gap-2">
          <code className="flex-1 font-mono text-xs text-foreground bg-muted px-3 py-2 rounded-md break-all">
            {data.key}
          </code>
          <Button variant="outline" size="sm" onClick={handleCopy}>
            {copied ? (
              <>
                <Check className="h-4 w-4" />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                Copy
              </>
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setRevealed(false)}
            title="Hide secret"
          >
            <EyeOff className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
