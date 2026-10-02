import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { mcpClientsService } from '@/lib/api/services/mcp-clients.service';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/errors/handler';

export function useMcpClients() {
  return useQuery({
    queryKey: queryKeys.mcpClients.list(),
    queryFn: () => mcpClientsService.list(),
  });
}

export function useForgetMcpClient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => mcpClientsService.forget(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.mcpClients.list() });
      toast.success('MCP client removed');
    },
    onError: (error) => {
      toast.error(`Failed to remove MCP client: ${getErrorMessage(error)}`);
    },
  });
}
