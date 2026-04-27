import { createFileRoute } from '@tanstack/react-router';
import { useMemo, useState } from 'react';
import { Plus, Webhook as WebhookIcon, ExternalLink } from 'lucide-react';

import { Button } from '@/components/ui/button';
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
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-medium text-white">Webhooks</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Receive real-time events when wearable data is ingested.
          </p>
        </div>
        <Button onClick={() => setIsCreateOpen(true)} disabled={isSvixDisabled}>
          <Plus className="h-4 w-4" />
          Add webhook
        </Button>
      </div>

      {isSvixDisabled ? (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-6">
          <p className="text-sm text-amber-200 font-medium">
            Webhooks are not enabled on this instance.
          </p>
          <p className="text-xs text-amber-200/70 mt-1">
            Configure <code>SVIX_AUTH_TOKEN</code> or{' '}
            <code>SVIX_JWT_SECRET</code> in the backend environment to enable
            outgoing webhook delivery.
          </p>
        </div>
      ) : endpoints.isLoading ? (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6 animate-pulse space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-12 bg-zinc-800/50 rounded-md" />
          ))}
        </div>
      ) : endpoints.error ? (
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8 text-center">
          <p className="text-zinc-400 mb-4">
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
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
      <WebhookIcon className="h-12 w-12 text-zinc-700 mx-auto mb-4" />
      <p className="text-zinc-300 font-medium">No webhooks configured</p>
      <p className="text-sm text-zinc-500 mt-1 max-w-md mx-auto">
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
