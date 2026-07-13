import { useQuery } from '@tanstack/react-query';
import { metaService } from '@/lib/api';
import { queryKeys } from '@/lib/query/keys';

export function useCoverage() {
  return useQuery({
    queryKey: queryKeys.meta.coverage(),
    queryFn: () => metaService.getCoverage(),
    staleTime: 24 * 60 * 60 * 1000, // 24h — coverage changes only on deploy
  });
}
