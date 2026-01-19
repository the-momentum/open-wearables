import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';

interface CursorPaginationProps {
  currentPage: number;
  hasPrevPage: boolean;
  hasNextPage: boolean;
  isFetching?: boolean;
  onPrevPage: () => void;
  onNextPage: () => void;
}

export function CursorPagination({
  currentPage,
  hasPrevPage,
  hasNextPage,
  isFetching = false,
  onPrevPage,
  onNextPage,
}: CursorPaginationProps) {
  // Don't render if there's only one page
  if (!hasPrevPage && !hasNextPage) {
    return null;
  }

  return (
    <div className="pt-4 border-t border-zinc-800">
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              onClick={onPrevPage}
              className={
                !hasPrevPage || isFetching
                  ? 'pointer-events-none opacity-50'
                  : 'cursor-pointer'
              }
            />
          </PaginationItem>
          <PaginationItem>
            <PaginationLink isActive>{currentPage}</PaginationLink>
          </PaginationItem>
          <PaginationItem>
            <PaginationNext
              onClick={onNextPage}
              className={
                !hasNextPage || isFetching
                  ? 'pointer-events-none opacity-50'
                  : 'cursor-pointer'
              }
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  );
}
