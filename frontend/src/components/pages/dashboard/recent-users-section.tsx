import { format } from 'date-fns';
import { Users as UsersIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { UserRead } from '@/lib/api/types';

export interface RecentUsersSectionProps {
  users: UserRead[];
  totalUsersCount: number;
  isLoading?: boolean;
  className?: string;
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return (parts[0]?.[0] ?? '?').toUpperCase();
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
}

export function RecentUsersSection({
  users,
  totalUsersCount,
  isLoading,
  className,
}: RecentUsersSectionProps) {
  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-2xl border border-border/60',
        'bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl',
        className
      )}
    >
      <div className="flex items-center justify-between border-b border-border/60 px-6 py-4">
        <div>
          <h2 className="text-base font-semibold text-foreground">
            Recent Users
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Total users:{' '}
            <span className="font-mono font-medium text-foreground">
              {totalUsersCount.toLocaleString()}
            </span>
          </p>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-border/60 bg-muted/40">
          <UsersIcon className="h-4 w-4 text-muted-foreground" />
        </div>
      </div>
      <div className="p-3">
        {isLoading ? (
          <div className="space-y-2 p-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex animate-pulse items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-muted" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 w-32 rounded bg-muted" />
                  <div className="h-2.5 w-48 rounded bg-muted/60" />
                </div>
              </div>
            ))}
          </div>
        ) : users.length > 0 ? (
          <div className="space-y-1">
            {users.map((user) => {
              const userName =
                user.first_name || user.last_name
                  ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
                  : user.email || 'Unknown User';
              const date = new Date(user.created_at);
              const formattedDate = isNaN(date.getTime())
                ? 'Invalid date'
                : format(date, 'MMM d, yyyy');
              return (
                <div
                  key={user.id}
                  className={cn(
                    'flex items-center gap-3 rounded-xl px-3 py-2.5',
                    'transition-colors duration-200 hover:bg-card-elevated/60'
                  )}
                >
                  <div
                    className={cn(
                      'flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold',
                      'bg-muted/60 text-foreground/80 border border-border/60'
                    )}
                  >
                    {getInitials(userName)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      {userName}
                    </p>
                    <p className="truncate text-xs text-muted-foreground">
                      {user.email || user.external_user_id || 'No email'}
                    </p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground/70">
                      Joined {formattedDate}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-[hsl(var(--success-muted))]" />
                    <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                      Active
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
            <UsersIcon className="h-8 w-8 opacity-40" />
            <p className="text-sm">No users found</p>
          </div>
        )}
      </div>
    </div>
  );
}
