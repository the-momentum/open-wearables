'use client';

import { useState, useEffect, useRef } from 'react';
import { Link } from '@tanstack/react-router';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type PaginationState,
} from '@tanstack/react-table';
import {
  Search,
  Eye,
  Trash2,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  ChevronsUpDown,
  Link as LinkIcon,
  Loader2,
  Upload,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import type { UserRead, UserQueryParams } from '@/lib/api/types';
import { copyToClipboard } from '@/lib/utils/clipboard';
import { truncateId } from '@/lib/utils/format';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAppleXmlUpload } from '@/hooks/api/use-users';
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
  PaginationEllipsis,
} from '@/components/ui/pagination';

interface UsersTableProps {
  data: UserRead[];
  total: number;
  page: number;
  pageSize: number;
  pageCount: number;
  isLoading?: boolean;
  onDelete: (userId: string) => void;
  isDeleting?: boolean;
  onQueryChange: (params: UserQueryParams) => void;
}

const columnToSortBy: Record<string, UserQueryParams['sort_by']> = {
  created_at: 'created_at',
  email: 'email',
  first_name: 'first_name',
  name: 'first_name',
};

export function UsersTable({
  data,
  total,
  page,
  pageSize,
  pageCount,
  isLoading,
  onDelete,
  isDeleting,
  onQueryChange,
}: UsersTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'created_at', desc: true },
  ]);
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: page - 1,
    pageSize,
  });
  const [globalFilter, setGlobalFilter] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copiedPairLink, setCopiedPairLink] = useState<string | null>(null);
  const fileInputRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const { handleUpload, uploadingUserId } = useAppleXmlUpload();

  const onQueryChangeRef = useRef(onQueryChange);
  useEffect(() => {
    onQueryChangeRef.current = onQueryChange;
  });

  const prevSearchRef = useRef(debouncedSearch);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(globalFilter);
    }, 300);
    return () => clearTimeout(timer);
  }, [globalFilter]);

  useEffect(() => {
    const searchChanged = prevSearchRef.current !== debouncedSearch;
    prevSearchRef.current = debouncedSearch;

    if (searchChanged && pagination.pageIndex !== 0) {
      setPagination((prev) => ({ ...prev, pageIndex: 0 }));
      return;
    }

    const effectivePage = searchChanged ? 1 : pagination.pageIndex + 1;
    const sortColumn = sorting[0];
    const sortBy = sortColumn ? columnToSortBy[sortColumn.id] : 'created_at';
    const sortOrder = sortColumn?.desc ? 'desc' : 'asc';

    onQueryChangeRef.current({
      page: effectivePage,
      limit: pagination.pageSize,
      sort_by: sortBy,
      sort_order: sortOrder,
      search: debouncedSearch || undefined,
    });
  }, [pagination, sorting, debouncedSearch]);

  const handleCopyId = async (id: string) => {
    const success = await copyToClipboard(id, 'User ID copied to clipboard');
    if (success) {
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  };

  const handleCopyPairLink = async (userId: string) => {
    const pairLink = `${window.location.origin}/users/${userId}/pair`;
    const success = await copyToClipboard(
      pairLink,
      'Pairing link copied to clipboard'
    );
    if (success) {
      setCopiedPairLink(userId);
      setTimeout(() => setCopiedPairLink(null), 2000);
    }
  };

  const handleUploadClick = (userId: string) => {
    fileInputRefs.current[userId]?.click();
  };

  const SortableHeader = ({
    column,
    children,
  }: {
    column: {
      id: string;
      getIsSorted: () => false | 'asc' | 'desc';
      toggleSorting: (desc?: boolean) => void;
    };
    children: React.ReactNode;
  }) => {
    const isSortable = column.id in columnToSortBy;

    if (!isSortable) {
      return (
        <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
          {children}
        </span>
      );
    }

    return (
      <button
        className="flex items-center gap-1 text-xs font-medium text-zinc-500 uppercase tracking-wider hover:text-zinc-300 transition-colors"
        onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
      >
        {children}
        {column.getIsSorted() === 'asc' ? (
          <ChevronUp className="h-3 w-3" />
        ) : column.getIsSorted() === 'desc' ? (
          <ChevronDown className="h-3 w-3" />
        ) : (
          <ChevronsUpDown className="h-3 w-3 opacity-50" />
        )}
      </button>
    );
  };

  const columns: ColumnDef<UserRead>[] = [
    {
      accessorKey: 'id',
      header: () => (
        <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
          User ID
        </span>
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <code className="font-mono text-xs bg-zinc-800 text-zinc-300 px-2 py-1 rounded">
            {truncateId(row.original.id)}
          </code>
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={() => handleCopyId(row.original.id)}
          >
            {copiedId === row.original.id ? (
              <Check className="h-3 w-3 text-emerald-500" />
            ) : (
              <Copy className="h-3 w-3" />
            )}
          </Button>
        </div>
      ),
      enableSorting: false,
    },
    {
      accessorKey: 'external_user_id',
      header: () => (
        <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
          External User ID
        </span>
      ),
      cell: ({ row }) => (
        <code className="font-mono text-xs bg-zinc-800 text-zinc-300 px-2 py-1 rounded">
          {row.original.external_user_id
            ? truncateId(row.original.external_user_id)
            : '—'}
        </code>
      ),
      enableSorting: false,
    },
    {
      id: 'name',
      accessorFn: (row) =>
        `${row.first_name || ''} ${row.last_name || ''}`.trim(),
      header: ({ column }) => (
        <SortableHeader column={column}>Name</SortableHeader>
      ),
      cell: ({ row }) => {
        const fullName =
          `${row.original.first_name || ''} ${row.original.last_name || ''}`.trim();
        return (
          <span
            className={fullName ? 'text-sm text-zinc-300' : 'text-zinc-600'}
          >
            {fullName || '—'}
          </span>
        );
      },
    },
    {
      accessorKey: 'email',
      header: ({ column }) => (
        <SortableHeader column={column}>Email</SortableHeader>
      ),
      cell: ({ row }) => (
        <span
          className={
            row.original.email ? 'text-sm text-zinc-400' : 'text-zinc-600'
          }
        >
          {row.original.email || '—'}
        </span>
      ),
    },
    {
      accessorKey: 'created_at',
      header: ({ column }) => (
        <SortableHeader column={column}>Created</SortableHeader>
      ),
      cell: ({ row }) => (
        <span className="text-xs text-zinc-500">
          {formatDistanceToNow(new Date(row.original.created_at), {
            addSuffix: true,
          })}
        </span>
      ),
    },
    {
      id: 'actions',
      header: () => (
        <span className="text-xs font-medium text-zinc-500 uppercase tracking-wider text-right block">
          Actions
        </span>
      ),
      cell: ({ row }) => (
        <div className="flex justify-end gap-1">
          <Button variant="outline" size="icon" asChild>
            <Link to="/users/$userId" params={{ userId: row.original.id }}>
              <Eye className="h-4 w-4" />
            </Link>
          </Button>
          <Button
            variant="outline"
            size="icon"
            onClick={() => handleUploadClick(row.original.id)}
            disabled={uploadingUserId === row.original.id}
            title="Upload Apple Health XML"
          >
            {uploadingUserId === row.original.id ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Upload className="h-4 w-4" />
            )}
          </Button>
          <input
            ref={(el) => {
              fileInputRefs.current[row.original.id] = el;
            }}
            type="file"
            accept=".xml"
            onChange={(e) => handleUpload(row.original.id, e)}
            className="hidden"
          />
          <Button
            variant="outline"
            size="icon"
            onClick={() => handleCopyPairLink(row.original.id)}
            title="Copy pairing link"
          >
            {copiedPairLink === row.original.id ? (
              <Check className="h-4 w-4 text-emerald-500" />
            ) : (
              <LinkIcon className="h-4 w-4" />
            )}
          </Button>
          <Button
            variant="destructive-outline"
            size="icon"
            onClick={() => onDelete(row.original.id)}
            disabled={isDeleting}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ),
      enableSorting: false,
    },
  ];

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      pagination,
    },
    onSortingChange: setSorting,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    manualSorting: true,
    manualFiltering: true,
    pageCount,
  });

  const currentPage = pagination.pageIndex;

  const getPageNumbers = () => {
    const pages: (number | 'ellipsis')[] = [];
    const maxVisible = 5;

    if (pageCount <= maxVisible) {
      for (let i = 0; i < pageCount; i++) {
        pages.push(i);
      }
    } else {
      pages.push(0);

      if (currentPage > 2) {
        pages.push('ellipsis');
      }

      const start = Math.max(1, currentPage - 1);
      const end = Math.min(pageCount - 2, currentPage + 1);

      for (let i = start; i <= end; i++) {
        if (!pages.includes(i)) {
          pages.push(i);
        }
      }

      if (currentPage < pageCount - 3) {
        pages.push('ellipsis');
      }

      if (!pages.includes(pageCount - 1)) {
        pages.push(pageCount - 1);
      }
    }

    return pages;
  };

  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
      <div className="p-4 border-b border-zinc-800">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <Input
            type="text"
            placeholder="Search by name or email..."
            value={globalFilter}
            onChange={(e) => setGlobalFilter(e.target.value)}
            className="bg-zinc-900 border-zinc-800 px-9"
          />
          {isLoading && (
            <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500 animate-spin" />
          )}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr
                key={headerGroup.id}
                className="border-b border-zinc-800 text-left"
              >
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="px-4 py-3">
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                          header.column.columnDef.header,
                          header.getContext()
                        )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center">
                  <p className="text-zinc-400">
                    {globalFilter
                      ? 'No users match your search criteria.'
                      : 'No users found'}
                  </p>
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="hover:bg-zinc-800/30 transition-colors"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3">
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pageCount > 0 && (
        <div className="p-4 border-t border-zinc-800 flex items-center justify-between">
          <div className="text-sm text-zinc-500">
            Showing{' '}
            <span className="font-medium text-zinc-300">
              {total === 0 ? 0 : pagination.pageIndex * pagination.pageSize + 1}
            </span>{' '}
            to{' '}
            <span className="font-medium text-zinc-300">
              {Math.min(
                (pagination.pageIndex + 1) * pagination.pageSize,
                total
              )}
            </span>{' '}
            of <span className="font-medium text-zinc-300">{total}</span> users
          </div>

          {pageCount > 1 && (
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    onClick={() => table.previousPage()}
                    className={
                      !table.getCanPreviousPage()
                        ? 'pointer-events-none opacity-50'
                        : 'cursor-pointer'
                    }
                  />
                </PaginationItem>

                {getPageNumbers().map((pageNum, idx) =>
                  pageNum === 'ellipsis' ? (
                    <PaginationItem key={`ellipsis-${idx}`}>
                      <PaginationEllipsis />
                    </PaginationItem>
                  ) : (
                    <PaginationItem key={pageNum}>
                      <PaginationLink
                        onClick={() => table.setPageIndex(pageNum)}
                        isActive={currentPage === pageNum}
                        className="cursor-pointer"
                      >
                        {pageNum + 1}
                      </PaginationLink>
                    </PaginationItem>
                  )
                )}

                <PaginationItem>
                  <PaginationNext
                    onClick={() => table.nextPage()}
                    className={
                      !table.getCanNextPage()
                        ? 'pointer-events-none opacity-50'
                        : 'cursor-pointer'
                    }
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          )}
        </div>
      )}
    </div>
  );
}
