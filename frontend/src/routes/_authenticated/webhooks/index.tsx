import { createFileRoute } from '@tanstack/react-router';
import { useMemo, useState } from 'react';
import { Plus, Webhook as WebhookIcon, ExternalLink } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/ui/page-header';
import { WebhooksTable } from '@/components/webhooks/webhooks-table';
import { WebhookCreateDialog } from '@/components/webhooks/webhook-create-dialog';
import { WebhookDeleteDialog } from '@/components/webhooks/webhook-delete-dialog';
import { useWebhookEndpoints } from '@/hooks/api/use-webhooks';
import { ApiError } from '@/lib/errors/api-error';

export const Route = createFileRoute('/_authenticated/webhooks/')({
  component: WebhooksPage,
});

function WebhooksPage() {
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const endpoints = useWebhookEndpoints();

  const deleteUrl = useMemo(
    () => endpoints.data?.find((e) => e.id === deleteId)?.url,
    [endpoints.data, deleteId]
  );

  const isSvixDisabled =
    endpoints.error instanceof ApiError && endpoints.error.statusCode === 503;

  return (
    <div className="p-6 md:p-8 space-y-6">
      <PageHeader
        title="Webhooks"
        description="Receive real-time events when wearable data is ingested."
        action={
          <Button
            onClick={() => setIsCreateOpen(true)}
            disabled={isSvixDisabled}
          >
            <Plus className="h-4 w-4" />
            Add webhook
          </Button>
        }
      />

      {isSvixDisabled ? (
        <div className="rounded-2xl border border-[hsl(var(--warning-muted)/0.4)] bg-[hsl(var(--warning-muted)/0.08)] p-6">
          <p className="text-sm font-medium text-[hsl(var(--warning-muted))]">
            Webhooks are not enabled on this instance.
          </p>
          <p className="text-xs text-muted-foreground mt-1">
            Configure <code>SVIX_AUTH_TOKEN</code> or{' '}
            <code>SVIX_JWT_SECRET</code> in the backend environment to enable
            outgoing webhook delivery.
          </p>
        </div>
      ) : endpoints.isLoading ? (
        <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 p-6 backdrop-blur-xl animate-pulse space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-muted/50 rounded-md" />
          ))}
        </div>
      ) : endpoints.error ? (
        <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 p-8 text-center backdrop-blur-xl">
          <p className="text-muted-foreground mb-4">
            Failed to load webhooks. Please try again.
          </p>
          <Button onClick={() => endpoints.refetch()}>Retry</Button>
        </div>
      ) : endpoints.data && endpoints.data.length > 0 ? (
        <WebhooksTable data={endpoints.data} onDelete={setDeleteId} />
      ) : (
        <EmptyState onCreate={() => setIsCreateOpen(true)} />
      )}

      <WebhookCreateDialog open={isCreateOpen} onOpenChange={setIsCreateOpen} />
      <WebhookDeleteDialog
        endpointId={deleteId}
        url={deleteUrl}
        onClose={() => setDeleteId(null)}
      />
    </div>
  );
}

function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 p-12 text-center backdrop-blur-xl">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl border border-border/60 bg-muted/40">
        <WebhookIcon className="h-6 w-6 text-muted-foreground" />
      </div>
      <p className="font-medium text-foreground">No webhooks configured</p>
      <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
        Subscribe to events like <code>workout.created</code> or{' '}
        <code>sleep.created</code> and we'll POST signed payloads to your URL.
      </p>
      <div className="mt-5 flex justify-center gap-3">
        <Button onClick={onCreate}>
          <Plus className="h-4 w-4" />
          Create your first webhook
        </Button>
        <a
          href="https://openwearables.io/docs"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Button variant="outline">
            Read the docs
            <ExternalLink className="h-3 w-3" />
          </Button>
        </a>
      </div>
    </div>
  );
}
