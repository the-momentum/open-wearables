import { Copy, Globe } from 'lucide-react';
import { copyToClipboard } from '@/lib/utils/clipboard';
import { API_CONFIG } from '@/lib/api/config';
import { Button } from '@/components/ui/button';
import { ApiKeysSection } from './-api-keys-section';
import { ApplicationsSection } from './-applications-section';

export function CredentialsTab() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-medium text-foreground">
          API and Application Credentials
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Manage API keys and SDK application credentials
        </p>
      </div>

      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Globe className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-xs text-muted-foreground">API Base URL</p>
              <code className="font-mono text-sm text-foreground/90">
                {API_CONFIG.baseUrl}
              </code>
            </div>
          </div>
          <Button
            variant="ghost-faded"
            size="icon-sm"
            aria-label="Copy API URL"
            onClick={() =>
              copyToClipboard(API_CONFIG.baseUrl, 'API URL copied')
            }
          >
            <Copy className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <ApiKeysSection />
      <ApplicationsSection />
    </div>
  );
}
