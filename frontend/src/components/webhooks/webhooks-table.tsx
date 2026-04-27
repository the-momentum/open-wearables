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
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="border-zinc-800 hover:bg-transparent">
            <TableHead className="text-zinc-400">URL</TableHead>
            <TableHead className="text-zinc-400">Description</TableHead>
            <TableHead className="text-zinc-400">Events</TableHead>
            <TableHead className="text-zinc-400">User filter</TableHead>
            <TableHead className="text-zinc-400 text-right">Actions</TableHead>
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
                className="border-zinc-800 cursor-pointer hover:bg-zinc-900"
                onClick={goToDetail}
              >
                <TableCell className="font-mono text-xs text-zinc-200 max-w-[280px] truncate">
                  {endpoint.url}
                </TableCell>
                <TableCell className="text-sm text-zinc-300 max-w-[220px] truncate">
                  {endpoint.description ?? (
                    <span className="text-zinc-600">-</span>
                  )}
                </TableCell>
                <TableCell>
                  {endpoint.filter_types?.length ? (
                    <div className="flex flex-wrap gap-1 max-w-[280px]">
                      {endpoint.filter_types.slice(0, 3).map((t) => (
                        <Badge
                          key={t}
                          variant="outline"
                          className="border-zinc-700 text-zinc-300 text-[10px]"
                        >
                          {t}
                        </Badge>
                      ))}
                      {endpoint.filter_types.length > 3 && (
                        <Badge
                          variant="outline"
                          className="border-zinc-700 text-zinc-500 text-[10px]"
                        >
                          +{endpoint.filter_types.length - 3}
                        </Badge>
                      )}
                    </div>
                  ) : (
                    <Badge
                      variant="outline"
                      className="border-zinc-700 text-zinc-400 text-[10px]"
                    >
                      All events
                    </Badge>
                  )}
                </TableCell>
                <TableCell>
                  {endpoint.user_id ? (
                    <code className="font-mono text-xs text-zinc-300">
                      {endpoint.user_id.slice(0, 8)}...
                    </code>
                  ) : (
                    <span className="text-xs text-zinc-600">All users</span>
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
                    className="text-zinc-400 hover:text-red-400"
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
          <p className="text-sm text-zinc-500">No webhooks configured.</p>
        </div>
      )}
    </div>
  );
}
