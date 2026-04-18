import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ChevronDown, Copy, Send, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
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
  useWebhookEventTypes,
} from '@/hooks/api/use-webhooks';
import { ROUTES } from '@/lib/constants/routes';
import type { WebhookAttemptsParams } from '@/lib/api/types';

export const Route = createFileRoute('/_authenticated/webhooks/$endpointId')({
  component: WebhookDetailPage,
});

function WebhookDetailPage() {
  const { endpointId } = Route.useParams();
  const navigate = useNavigate();
  const endpoint = useWebhookEndpoint(endpointId);
  const update = useUpdateWebhookEndpoint();

  const [tab, setTab] = useState<'overview' | 'deliveries'>('overview');
  const [isTestOpen, setIsTestOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const [attemptsParams, setAttemptsParams] = useState<WebhookAttemptsParams>({
    limit: 50,
  });
  const [iteratorStack, setIteratorStack] = useState<(string | null)[]>([]);

  const attempts = useWebhookAttempts(endpointId, attemptsParams);

  const hasPrev = iteratorStack.length > 0;
  const hasNext = !attempts.data?.done && !!attempts.data?.iterator;

  function handleNext() {
    const nextIterator = attempts.data?.iterator ?? null;
    setIteratorStack((s) => [...s, attemptsParams.iterator ?? null]);
    setAttemptsParams((p) => ({ ...p, iterator: nextIterator }));
  }

  function handlePrev() {
    const stack = [...iteratorStack];
    const prevIterator = stack.pop() ?? null;
    setIteratorStack(stack);
    setAttemptsParams((p) => ({ ...p, iterator: prevIterator }));
  }

  function handleFilterChange(patch: Partial<WebhookAttemptsParams>) {
    setIteratorStack([]);
    setAttemptsParams((p) => ({ ...p, ...patch, iterator: null }));
  }

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
          <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5 space-y-3">
            <p className="text-[10px] uppercase tracking-wide text-zinc-500 font-medium">
              Endpoint ID
            </p>
            <div className="flex items-center gap-2">
              <code className="font-mono text-xs text-zinc-300 flex-1 break-all">
                {ep.id}
              </code>
              <Button
                variant="ghost"
                size="sm"
                className="shrink-0 h-7 w-7 p-0 text-zinc-500 hover:text-zinc-300"
                onClick={() => {
                  navigator.clipboard.writeText(ep.id);
                  toast.success('Endpoint ID copied');
                }}
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>

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

        <TabsContent value="deliveries" className="space-y-4">
          <DeliveriesFilters
            params={attemptsParams}
            onChange={handleFilterChange}
          />
          <DeliveriesPagination
            hasPrev={hasPrev}
            hasNext={hasNext}
            onPrev={handlePrev}
            onNext={handleNext}
            isLoading={attempts.isLoading}
          />
          <WebhookAttemptsTable
            attempts={attempts.data?.data ?? []}
            isLoading={attempts.isLoading}
          />
          <DeliveriesPagination
            hasPrev={hasPrev}
            hasNext={hasNext}
            onPrev={handlePrev}
            onNext={handleNext}
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

const STATUS_OPTIONS = [
  { label: 'All statuses', value: '' },
  { label: 'Success', value: '0' },
  { label: 'Pending', value: '1' },
  { label: 'Failed', value: '2' },
  { label: 'Sending', value: '3' },
];

const LIMIT_OPTIONS = [25, 50, 100, 250];

function DeliveriesFilters({
  params,
  onChange,
}: {
  params: WebhookAttemptsParams;
  onChange: (patch: Partial<WebhookAttemptsParams>) => void;
}) {
  const eventTypes = useWebhookEventTypes();
  const [etOpen, setEtOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const selected = new Set(params.event_types ?? []);

  useEffect(() => {
    if (!etOpen) return;
    function handleClick(e: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setEtOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [etOpen]);

  function toggleEventType(name: string) {
    const next = new Set(selected);
    if (next.has(name)) {
      next.delete(name);
    } else {
      next.add(name);
    }
    onChange({ event_types: next.size > 0 ? Array.from(next) : undefined });
  }

  function clearEventTypes() {
    onChange({ event_types: undefined });
  }

  return (
    <div className="flex flex-wrap gap-3 items-center">
      <select
        className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-zinc-600"
        value={params.status ?? ''}
        onChange={(e) =>
          onChange({
            status: e.target.value !== '' ? Number(e.target.value) : null,
          })
        }
      >
        {STATUS_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>

      <select
        className="bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-zinc-600"
        value={params.limit ?? 50}
        onChange={(e) => onChange({ limit: Number(e.target.value) })}
      >
        {LIMIT_OPTIONS.map((n) => (
          <option key={n} value={n}>
            {n} per page
          </option>
        ))}
      </select>

      {/* Event type multi-select */}
      <div className="relative" ref={dropdownRef}>
        <button
          type="button"
          onClick={() => setEtOpen((o) => !o)}
          className="flex items-center gap-1.5 bg-zinc-900 border border-zinc-700 text-zinc-300 text-xs rounded-md px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-zinc-600 hover:border-zinc-600"
        >
          {selected.size > 0 ? (
            <span className="text-indigo-400">
              {selected.size} event type{selected.size > 1 ? 's' : ''}
            </span>
          ) : (
            'All event types'
          )}
          <ChevronDown className="h-3 w-3 text-zinc-500" />
        </button>

        {etOpen && (
          <div className="absolute z-20 top-full mt-1 left-0 w-72 bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
              <span className="text-[10px] uppercase tracking-wide text-zinc-500">
                Filter by event type
              </span>
              {selected.size > 0 && (
                <button
                  type="button"
                  onClick={clearEventTypes}
                  className="text-[10px] text-zinc-500 hover:text-zinc-300"
                >
                  Clear all
                </button>
              )}
            </div>
            <div className="max-h-72 overflow-y-auto">
              {eventTypes.isLoading ? (
                <p className="text-xs text-zinc-500 px-3 py-4">Loading…</p>
              ) : (
                eventTypes.data?.map((et) => (
                  <label
                    key={et.name}
                    className="flex items-center gap-2.5 px-3 py-1.5 hover:bg-zinc-800 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      className="accent-indigo-500"
                      checked={selected.has(et.name)}
                      onChange={() => toggleEventType(et.name)}
                    />
                    <span className="font-mono text-[11px] text-zinc-300">
                      {et.name}
                    </span>
                  </label>
                ))
              )}
            </div>
            {selected.size > 0 && (
              <div className="px-3 py-2 border-t border-zinc-800 flex flex-wrap gap-1">
                {Array.from(selected).map((name) => (
                  <Badge
                    key={name}
                    className="bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 text-[10px] cursor-pointer"
                    onClick={() => toggleEventType(name)}
                  >
                    {name} ×
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function DeliveriesPagination({
  hasPrev,
  hasNext,
  onPrev,
  onNext,
  isLoading,
}: {
  hasPrev: boolean;
  hasNext: boolean;
  onPrev: () => void;
  onNext: () => void;
  isLoading: boolean;
}) {
  if (!hasPrev && !hasNext) return null;
  return (
    <div className="flex justify-end gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={onPrev}
        disabled={!hasPrev || isLoading}
      >
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={onNext}
        disabled={!hasNext || isLoading}
      >
        Next
      </Button>
    </div>
  );
}
