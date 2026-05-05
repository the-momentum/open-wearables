import { useNavigate } from '@tanstack/react-router';
import { Trash2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { WebhookEndpoint } from '@/lib/api/types';

interface WebhooksTableProps {
  data: WebhookEndpoint[];
  onDelete: (id: string) => void;
}

export function WebhooksTable({ data, onDelete }: WebhooksTableProps) {
  const navigate = useNavigate();

  return (
    <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="border-border/60 hover:bg-transparent">
            <TableHead className="text-muted-foreground">URL</TableHead>
            <TableHead className="text-muted-foreground">Description</TableHead>
            <TableHead className="text-muted-foreground">Events</TableHead>
            <TableHead className="text-muted-foreground">User filter</TableHead>
            <TableHead className="text-muted-foreground text-right">
              Actions
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.map((endpoint) => {
            const goToDetail = () =>
              navigate({
                to: '/webhooks/$endpointId',
                params: { endpointId: endpoint.id },
              });
            return (
              <TableRow
                key={endpoint.id}
                className="border-border/60 cursor-pointer hover:bg-card"
                onClick={goToDetail}
              >
                <TableCell className="font-mono text-xs text-foreground max-w-[280px] truncate">
                  {endpoint.url}
                </TableCell>
                <TableCell className="text-sm text-foreground/90 max-w-[220px] truncate">
                  {endpoint.description ?? (
                    <span className="text-muted-foreground/70">-</span>
                  )}
                </TableCell>
                <TableCell>
                  {endpoint.filter_types?.length ? (
                    <div className="flex flex-wrap gap-1 max-w-[280px]">
                      {endpoint.filter_types.slice(0, 3).map((t) => (
                        <Badge
                          key={t}
                          variant="outline"
                          className="border-border text-foreground/90 text-[10px]"
                        >
                          {t}
                        </Badge>
                      ))}
                      {endpoint.filter_types.length > 3 && (
                        <Badge
                          variant="outline"
                          className="border-border text-muted-foreground text-[10px]"
                        >
                          +{endpoint.filter_types.length - 3}
                        </Badge>
                      )}
                    </div>
                  ) : (
                    <Badge
                      variant="outline"
                      className="border-border text-muted-foreground text-[10px]"
                    >
                      All events
                    </Badge>
                  )}
                </TableCell>
                <TableCell>
                  {endpoint.user_id ? (
                    <code className="font-mono text-xs text-foreground/90">
                      {endpoint.user_id.slice(0, 8)}...
                    </code>
                  ) : (
                    <span className="text-xs text-muted-foreground/70">
                      All users
                    </span>
                  )}
                </TableCell>
                <TableCell
                  className="text-right"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => onDelete(endpoint.id)}
                    title="Delete"
                    className="text-muted-foreground hover:text-[hsl(var(--destructive-muted))]"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {data.length === 0 && (
        <div className="p-12 text-center">
          <p className="text-sm text-muted-foreground">
            No webhooks configured.
          </p>
        </div>
      )}
    </div>
  );
}
