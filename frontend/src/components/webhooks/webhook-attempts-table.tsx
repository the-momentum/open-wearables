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
      <Badge className="bg-[hsl(var(--success-muted)/0.15)] text-[hsl(var(--success-muted))] border border-[hsl(var(--success-muted)/0.3)]">
        Success
      </Badge>
    );
  }
  if (PENDING_STATUSES.has(status)) {
    return (
      <Badge className="bg-[hsl(var(--warning-muted)/0.15)] text-[hsl(var(--warning-muted))] border border-[hsl(var(--warning-muted)/0.3)]">
        Pending
      </Badge>
    );
  }
  return (
    <Badge className="bg-[hsl(var(--destructive-muted)/0.15)] text-[hsl(var(--destructive-muted))] border border-[hsl(var(--destructive-muted)/0.3)]">
      Failed
    </Badge>
  );
}

function statusCodeColor(code: number) {
  if (code >= 200 && code < 300) return 'text-[hsl(var(--success-muted))]';
  if (code >= 300 && code < 400) return 'text-[hsl(var(--warning-muted))]';
  return 'text-[hsl(var(--destructive-muted))]';
}

export function WebhookAttemptsTable({
  attempts,
  isLoading,
}: WebhookAttemptsTableProps) {
  const [selected, setSelected] = useState<WebhookMessageAttempt | null>(null);

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-6 animate-pulse space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-12 bg-muted/50 rounded-md" />
        ))}
      </div>
    );
  }

  if (!attempts.length) {
    return (
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-12 text-center">
        <p className="text-sm text-muted-foreground">No deliveries yet.</p>
        <p className="text-xs text-muted-foreground/70 mt-1">
          Send a test event or wait for real activity to see delivery attempts
          here.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-border/60 hover:bg-transparent">
              <TableHead className="text-muted-foreground">Status</TableHead>
              <TableHead className="text-muted-foreground">Code</TableHead>
              <TableHead className="text-muted-foreground">Event</TableHead>
              <TableHead className="text-muted-foreground">Duration</TableHead>
              <TableHead className="text-muted-foreground">When</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {attempts.map((a) => (
              <TableRow
                key={a.id}
                className="border-border/60 cursor-pointer hover:bg-card"
                onClick={() => setSelected(a)}
              >
                <TableCell>{statusBadge(a.status)}</TableCell>
                <TableCell
                  className={`font-mono text-xs ${statusCodeColor(a.responseStatusCode)}`}
                >
                  {a.responseStatusCode || '-'}
                </TableCell>
                <TableCell className="text-xs text-foreground/90">
                  {a.msg?.eventType ?? a.msgId}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {a.responseDurationMs} ms
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
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
        <SheetContent className="w-full sm:max-w-xl bg-popover border-border/60 overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="text-foreground">
              Delivery attempt
            </SheetTitle>
            <SheetDescription>
              {selected?.id && (
                <code className="font-mono text-[10px] text-muted-foreground break-all">
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
                    className={`font-mono ${statusCodeColor(selected.responseStatusCode)}`}
                  >
                    {selected.responseStatusCode}
                  </span>
                </Field>
                <Field label="Duration">{selected.responseDurationMs} ms</Field>
                <Field label="When">
                  {selected.timestamp
                    ? new Date(selected.timestamp).toLocaleString()
                    : '-'}
                </Field>
              </div>
              <Field label="URL">
                <code className="font-mono text-xs text-foreground/90 break-all">
                  {selected.url}
                </code>
              </Field>
              <Field label="Event type">
                <code className="font-mono text-xs text-foreground/90">
                  {selected.msg?.eventType ?? '-'}
                </code>
              </Field>
              <Field label="Response body">
                <pre className="text-xs text-foreground/90 bg-card border border-border/60 rounded-md p-3 overflow-x-auto whitespace-pre-wrap break-all">
                  {selected.response || '(empty)'}
                </pre>
              </Field>
              {selected.msg?.payload && (
                <Field label="Payload">
                  <pre className="text-xs text-foreground/90 bg-card border border-border/60 rounded-md p-3 overflow-x-auto">
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
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div>{children}</div>
    </div>
  );
}
