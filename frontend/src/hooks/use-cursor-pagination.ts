import { useState, useCallback } from 'react';

/**
 * Hook for managing cursor-based pagination state.
 *
 * Usage:
 * ```tsx
 * const pagination = useCursorPagination();
 *
 * const { data } = useQuery({
 *   queryFn: () => fetchData({ cursor: pagination.currentCursor }),
 * });
 *
 * const hasNextPage = data?.pagination?.has_more ?? false;
 * const nextCursor = data?.pagination?.next_cursor ?? null;
 *
 * <button onClick={() => pagination.goToNextPage(nextCursor)} disabled={!hasNextPage}>
 *   Next
 * </button>
 * ```
 */
export function useCursorPagination() {
  const [currentPage, setCurrentPage] = useState(1);
  const [cursorHistory, setCursorHistory] = useState<(string | null)[]>([null]);

  const currentCursor = cursorHistory[currentPage - 1] ?? null;
  const hasPrevPage = currentPage > 1;

  const goToNextPage = useCallback(
    (nextCursor: string | null) => {
      if (nextCursor) {
        // Store the next cursor if we haven't visited this page yet
        setCursorHistory((prev) => {
          if (prev.length === currentPage) {
            return [...prev, nextCursor];
          }
          return prev;
        });
        setCurrentPage((p) => p + 1);
      }
    },
    [currentPage]
  );

  const goToPrevPage = useCallback(() => {
    if (currentPage > 1) {
      setCurrentPage((p) => p - 1);
    }
  }, [currentPage]);

  const reset = useCallback(() => {
    setCurrentPage(1);
    setCursorHistory([null]);
  }, []);

  return {
    currentPage,
    currentCursor,
    hasPrevPage,
    goToNextPage,
    goToPrevPage,
    reset,
  };
}
