import { useEffect, useState } from 'react';
import { Search, X } from 'lucide-react';
import { useUser, useUsers } from '@/hooks/api/use-users';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { UserRead } from '@/lib/api/types';

interface UserPickerProps {
  selectedUserId: string | undefined;
  onSelect: (userId: string | undefined) => void;
}

function userDisplayName(user: UserRead): string {
  const name = [user.first_name, user.last_name].filter(Boolean).join(' ');
  return name || user.email || user.external_user_id || user.id;
}

export function UserPicker({ selectedUserId, onSelect }: UserPickerProps) {
  const [input, setInput] = useState('');
  const [search, setSearch] = useState('');
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setSearch(input.trim()), 250);
    return () => clearTimeout(timer);
  }, [input]);

  const { data: selectedUser } = useUser(selectedUserId ?? '');
  const { data: results, isFetching } = useUsers({
    search: search || undefined,
    limit: 8,
  });

  if (selectedUserId) {
    const name = selectedUser ? userDisplayName(selectedUser) : '…';
    return (
      <div className="flex items-center justify-between rounded-xl border border-border/60 bg-card/40 px-4 py-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/60 bg-muted/40 text-xs font-bold text-foreground/70">
            {name.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-foreground">
              {name}
            </p>
            <p className="truncate font-mono text-xs text-muted-foreground">
              {selectedUserId}
            </p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onSelect(undefined)}
          className="gap-1 text-xs text-muted-foreground"
        >
          <X className="h-3 w-3" />
          Change user
        </Button>
      </div>
    );
  }

  return (
    <div className="relative max-w-xl">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search users by name, email, or external ID..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          className="pl-9"
        />
      </div>
      {open && (
        <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-border/60 bg-popover shadow-lg">
          {isFetching && !results ? (
            <div className="space-y-2 p-3">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : results && results.items.length > 0 ? (
            <ul>
              {results.items.map((user) => (
                <li key={user.id}>
                  <button
                    type="button"
                    // onMouseDown fires before the input's onBlur closes the list
                    onMouseDown={() => {
                      onSelect(user.id);
                      setInput('');
                    }}
                    className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left transition-colors hover:bg-card/60"
                  >
                    <span className="truncate text-sm text-foreground">
                      {userDisplayName(user)}
                    </span>
                    <span className="shrink-0 font-mono text-xs text-muted-foreground">
                      {user.id.slice(0, 8)}…
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="p-3 text-sm text-muted-foreground">No users found.</p>
          )}
        </div>
      )}
    </div>
  );
}
