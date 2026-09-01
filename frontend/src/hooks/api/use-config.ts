import { useQuery } from '@tanstack/react-query';
import { configService } from '@/lib/api';
import { queryKeys } from '@/lib/query/keys';

export function useConfig() {
  return useQuery({
    queryKey: queryKeys.config.all,
    queryFn: () => configService.get(),
    staleTime: 24 * 60 * 60 * 1000, // 24h — instance config changes only on redeploy
  });
}
