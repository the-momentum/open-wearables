import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Plug, Trash2 } from 'lucide-react';
import { useMcpClients, useForgetMcpClient } from '@/hooks/api/use-mcp-clients';
import type { McpClient } from '@/lib/api/types';
import { Button } from '@/components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';

export function McpClientsSection() {
  const [clientToForget, setClientToForget] = useState<McpClient | null>(null);

  const { data: clients, isLoading, error, refetch } = useMcpClients();
  const forgetMutation = useForgetMcpClient();

  const handleForgetConfirm = async () => {
    if (!clientToForget) return;
    await forgetMutation.mutateAsync(clientToForget.id);
    setClientToForget(null);
  };

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-10 bg-muted rounded-md w-full" />
          <div className="space-y-3">
            {[1, 2].map((i) => (
              <div key={i} className="h-16 bg-muted/50 rounded-md" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl p-12 text-center">
        <p className="text-muted-foreground mb-4">Failed to load MCP clients</p>
        <Button onClick={() => refetch()}>Retry</Button>
      </div>
    );
  }

  return (
    <>
      <div className="rounded-2xl border border-border/60 bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-border/60">
          <h3 className="text-sm font-medium text-foreground">
            Connected MCP Clients
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            Apps that authenticated against your self-hosted MCP server via
            OAuth (e.g. claude.ai). Bearer-token connections have no per-client
            identity and don&apos;t show up here.
          </p>
        </div>

        {clients && clients.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/60 text-left">
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Client
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    Last active
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                    First connected
                  </th>
                  <th className="px-6 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider text-right">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/40">
                {clients.map((mcpClient) => (
                  <tr
                    key={mcpClient.id}
                    className="hover:bg-muted/40 transition-colors"
                  >
                    <td className="px-6 py-4">
                      <div className="text-sm font-medium text-foreground/90">
                        {mcpClient.client_name || 'Unnamed client'}
                      </div>
                      <code className="text-[10px] text-muted-foreground">
                        {mcpClient.client_id}
                      </code>
                    </td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(mcpClient.last_seen_at), {
                        addSuffix: true,
                      })}
                    </td>
                    <td className="px-6 py-4 text-xs text-muted-foreground">
                      {formatDistanceToNow(new Date(mcpClient.created_at), {
                        addSuffix: true,
                      })}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-end">
                        <Button
                          variant="destructive-outline"
                          size="icon"
                          aria-label="Forget MCP client"
                          onClick={() => setClientToForget(mcpClient)}
                          disabled={forgetMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center">
            <Plug className="h-12 w-12 text-muted-foreground/60 mx-auto mb-4" />
            <p className="text-muted-foreground mb-2">
              No MCP clients connected yet
            </p>
            <p className="text-sm text-muted-foreground">
              Clients that sign in through your MCP server&apos;s OAuth flow
              will appear here.
            </p>
          </div>
        )}
      </div>

      <AlertDialog
        open={clientToForget !== null}
        onOpenChange={(open) => {
          if (!open) setClientToForget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Forget MCP Client</AlertDialogTitle>
            <AlertDialogDescription>
              {clientToForget
                ? `Remove "${clientToForget.client_name || clientToForget.client_id}" from this list? This only forgets the record here - it does not revoke the client's live session on the MCP server. It will reappear if it reconnects.`
                : "Remove this client from this list? This only forgets the record here - it does not revoke the client's live session on the MCP server."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={forgetMutation.isPending}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleForgetConfirm}
              disabled={forgetMutation.isPending}
              aria-label="Confirm forget MCP client"
            >
              {forgetMutation.isPending ? 'Removing...' : 'Remove'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
