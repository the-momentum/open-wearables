import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import { ArrowLeft, Send, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { WebhookForm } from '@/components/webhooks/webhook-form';
import { WebhookSecretReveal } from '@/components/webhooks/webhook-secret-reveal';
import { WebhookTestEventDialog } from '@/components/webhooks/webhook-test-event-dialog';
import { WebhookDeleteDialog } from '@/components/webhooks/webhook-delete-dialog';
import { WebhookAttemptsTable } from '@/components/webhooks/webhook-attempts-table';
import {
  useUpdateWebhookEndpoint,
  useWebhookAttempts,
  useWebhookEndpoint,
} from '@/hooks/api/use-webhooks';
import { ROUTES } from '@/lib/constants/routes';

export const Route = createFileRoute('/_authenticated/webhooks/$endpointId')({
  component: WebhookDetailPage,
});

function WebhookDetailPage() {
  const { endpointId } = Route.useParams();
  const navigate = useNavigate();
  const endpoint = useWebhookEndpoint(endpointId);
  const update = useUpdateWebhookEndpoint();
  const attempts = useWebhookAttempts(endpointId);

  const [tab, setTab] = useState<'overview' | 'deliveries'>('overview');
  const [isTestOpen, setIsTestOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  if (endpoint.isLoading) {
    return (
      <div className="p-8">
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6 animate-pulse space-y-3">
          <div className="h-6 w-1/3 bg-zinc-800 rounded" />
          <div className="h-32 bg-zinc-800/50 rounded" />
        </div>
      </div>
    );
  }

  if (endpoint.error || !endpoint.data) {
    return (
      <div className="p-8">
        <Link to={ROUTES.webhooks}>
          <Button variant="ghost" size="sm" className="mb-4">
            <ArrowLeft className="h-4 w-4" />
            Back
          </Button>
        </Link>
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-8 text-center">
          <p className="text-zinc-400">Webhook not found or failed to load.</p>
        </div>
      </div>
    );
  }

  const ep = endpoint.data;

  return (
    <div className="p-8">
      <Link to={ROUTES.webhooks}>
        <Button variant="ghost" size="sm" className="mb-4 -ml-2">
          <ArrowLeft className="h-4 w-4" />
          Back to webhooks
        </Button>
      </Link>

      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div className="min-w-0">
          <h1 className="text-xl font-medium text-white truncate">
            {ep.description || 'Webhook endpoint'}
          </h1>
          <code className="font-mono text-xs text-zinc-500 break-all">
            {ep.url}
          </code>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button variant="outline" onClick={() => setIsTestOpen(true)}>
            <Send className="h-4 w-4" />
            Send test
          </Button>
          <Button
            variant="outline"
            className="text-red-400 border-red-500/30 hover:bg-red-500/10"
            onClick={() => setIsDeleteOpen(true)}
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as 'overview' | 'deliveries')}
      >
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="deliveries">Deliveries</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
            <h3 className="text-sm font-medium text-white mb-4">
              Configuration
            </h3>
            <WebhookForm
              initial={ep}
              submitLabel="Save changes"
              isSubmitting={update.isPending}
              onSubmit={(data) =>
                update.mutate({
                  id: ep.id,
                  data: {
                    url: data.url,
                    description: data.description ?? null,
                    filter_types: data.filter_types ?? null,
                    user_id: data.user_id ?? null,
                  },
                })
              }
            />
          </div>

          <WebhookSecretReveal endpointId={ep.id} />
        </TabsContent>

        <TabsContent value="deliveries">
          <WebhookAttemptsTable
            attempts={attempts.data?.data ?? []}
            isLoading={attempts.isLoading}
          />
        </TabsContent>
      </Tabs>

      <WebhookTestEventDialog
        endpointId={ep.id}
        open={isTestOpen}
        onOpenChange={setIsTestOpen}
      />
      <WebhookDeleteDialog
        endpointId={isDeleteOpen ? ep.id : null}
        url={ep.url}
        onClose={() => setIsDeleteOpen(false)}
        onDeleted={() => navigate({ to: ROUTES.webhooks })}
      />
    </div>
  );
}
