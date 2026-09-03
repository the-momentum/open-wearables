import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import {
  zeppService,
  type ZeppConnectRequest,
  type ZeppVerifyRequest,
} from '@/lib/api/services/zepp.service';
import { queryKeys } from '@/lib/query/keys';

export function useVerifyZepp() {
  return useMutation({
    mutationFn: (data: ZeppVerifyRequest) => zeppService.verify(data),
    onError: (error: unknown) => {
      const message =
        error instanceof Error
          ? error.message
          : 'Falha ao verificar credenciais Zepp';
      toast.error(message);
    },
  });
}

export function useConnectZepp(userId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ZeppConnectRequest) => zeppService.connect(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.connections.all(userId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.all,
      });
      toast.success('Relógio Amazfit / Zepp conectado com sucesso!');
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Falha ao conectar conta Zepp';
      toast.error(message);
    },
  });
}
