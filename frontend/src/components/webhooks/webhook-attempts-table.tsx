import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';

import { Badge } from '@/components/ui/badge';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { WebhookMessageAttempt } from '@/lib/api/types';

interface WebhookAttemptsTableProps {
  attempts: WebhookMessageAttempt[];
  isLoading?: boolean;
}

const SUCCESS_STATUSES = new Set([0, 'success', 'Success']);
const PENDING_STATUSES = new Set([1, 3, 'pending', 'sending']);

function statusBadge(status: number | string) {
  if (SUCCESS_STATUSES.has(status)) {
    return (
      <Badge className="bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
        Success
      </Badge>
    );
  }
  if (PENDING_STATUSES.has(status)) {
    return (
      <Badge className="bg-amber-500/15 text-amber-300 border border-amber-500/30">
        Pending
      </Badge>
    );
  }
  return (
    <Badge className="bg-red-500/15 text-red-300 border border-red-500/30">
      Failed
    </Badge>
  );
}

function statusCodeColor(code: number) {
  if (code >= 200 && code < 300) return 'text-emerald-300';
  if (code >= 300 && code < 400) return 'text-amber-300';
  return 'text-red-300';
}

export function WebhookAttemptsTable({
  attempts,
  isLoading,
}: WebhookAttemptsTableProps) {
  const [selected, setSelected] = useState<WebhookMessageAttempt | null>(null);

  if (isLoading) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6 animate-pulse space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-12 bg-zinc-800/50 rounded-md" />
        ))}
      </div>
    );
  }

  if (!attempts.length) {
    return (
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
        <p className="text-sm text-zinc-500">No deliveries yet.</p>
        <p className="text-xs text-zinc-600 mt-1">
          Send a test event or wait for real activity to see delivery attempts
          here.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-zinc-800 hover:bg-transparent">
              <TableHead className="text-zinc-400">Status</TableHead>
              <TableHead className="text-zinc-400">Code</TableHead>
              <TableHead className="text-zinc-400">Event</TableHead>
              <TableHead className="text-zinc-400">Duration</TableHead>
              <TableHead className="text-zinc-400">When</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {attempts.map((a) => (
              <TableRow
                key={a.id}
                className="border-zinc-800 cursor-pointer hover:bg-zinc-900"
                onClick={() => setSelected(a)}
              >
                <TableCell>{statusBadge(a.status)}</TableCell>
                <TableCell
                  className={`font-mono text-xs ${statusCodeColor(a.response_status_code)}`}
                >
                  {a.response_status_code || '-'}
                </TableCell>
                <TableCell className="text-xs text-zinc-300">
                  {a.msg?.event_type ?? a.msg_id}
                </TableCell>
                <TableCell className="text-xs text-zinc-400">
                  {a.response_duration_ms} ms
                </TableCell>
                <TableCell className="text-xs text-zinc-400">
                  {a.timestamp
                    ? formatDistanceToNow(new Date(a.timestamp), {
                        addSuffix: true,
                      })
                    : '-'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Sheet
        open={!!selected}
        onOpenChange={(open) => !open && setSelected(null)}
      >
        <SheetContent className="w-full sm:max-w-xl bg-zinc-950 border-zinc-800 overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="text-white">Delivery attempt</SheetTitle>
            <SheetDescription>
              {selected?.id && (
                <code className="font-mono text-[10px] text-zinc-500 break-all">
                  {selected.id}
                </code>
              )}
            </SheetDescription>
          </SheetHeader>
          {selected && (
            <div className="px-4 space-y-4 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Status">{statusBadge(selected.status)}</Field>
                <Field label="HTTP code">
                  <span
                    className={`font-mono ${statusCodeColor(selected.response_status_code)}`}
                  >
                    {selected.response_status_code}
                  </span>
                </Field>
                <Field label="Duration">
                  {selected.response_duration_ms} ms
                </Field>
                <Field label="When">
                  {selected.timestamp
                    ? new Date(selected.timestamp).toLocaleString()
                    : '-'}
                </Field>
              </div>
              <Field label="URL">
                <code className="font-mono text-xs text-zinc-300 break-all">
                  {selected.url}
                </code>
              </Field>
              <Field label="Event type">
                <code className="font-mono text-xs text-zinc-300">
                  {selected.msg?.event_type ?? '-'}
                </code>
              </Field>
              <Field label="Response body">
                <pre className="text-xs text-zinc-300 bg-zinc-900 border border-zinc-800 rounded-md p-3 overflow-x-auto whitespace-pre-wrap break-all">
                  {selected.response || '(empty)'}
                </pre>
              </Field>
              {selected.msg?.payload && (
                <Field label="Payload">
                  <pre className="text-xs text-zinc-300 bg-zinc-900 border border-zinc-800 rounded-md p-3 overflow-x-auto">
                    {JSON.stringify(selected.msg.payload, null, 2)}
                  </pre>
                </Field>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <p className="text-[10px] uppercase tracking-wide text-zinc-500">
        {label}
      </p>
      <div>{children}</div>
    </div>
  );
}
