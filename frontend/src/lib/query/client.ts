// TanStack Query client configuration

import { QueryClient } from '@tanstack/react-query';
import { ApiError } from '../errors/api-error';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
      retry: (failureCount, error) => {
        // Don't retry on client errors (4xx)
        if (
          error instanceof ApiError &&
          error.statusCode >= 400 &&
          error.statusCode < 500
        ) {
          return false;
        }
        // Retry up to 3 times on server errors (5xx) or network errors
        return failureCount < 3;
      },
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: false,
      onError: (error) => {
        // Global error handling for mutations
        if (error instanceof ApiError) {
        }
      },
    },
  },
});
