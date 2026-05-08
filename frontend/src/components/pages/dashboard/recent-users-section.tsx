import { useState, type ElementType } from 'react';
import { format, formatDistanceToNow } from 'date-fns';
import { RefreshCw, Users as UsersIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { SourceBadge } from '@/components/common/source-badge';
import type { UserRead } from '@/lib/api/types';

export interface RecentUsersSectionProps {
  users: UserRead[];
  lastSyncedUsers: UserRead[];
  isLoading?: boolean;
  isLoadingLastSynced?: boolean;
  className?: string;
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return (parts[0]?.[0] ?? '?').toUpperCase();
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
}

function syncRecencyColor(syncedAt: string): string {
  const diffMs = Date.now() - new Date(syncedAt).getTime();
  const hours = diffMs / (1000 * 60 * 60);
  if (hours < 1) return 'text-[hsl(var(--success-muted))]';
  if (hours < 24) return 'text-[hsl(var(--warning-muted))]';
  return 'text-muted-foreground/70';
}

function syncRecencyDot(syncedAt: string): string {
  const diffMs = Date.now() - new Date(syncedAt).getTime();
  const hours = diffMs / (1000 * 60 * 60);
  if (hours < 1) return 'bg-[hsl(var(--success-muted))]';
  if (hours < 24) return 'bg-[hsl(var(--warning-muted))]';
  return 'bg-muted-foreground/40';
}

function SkeletonRows() {
  return (
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
  );
}

function EmptyState({
  icon: Icon,
  message,
}: {
  icon: ElementType;
  message: string;
}) {
  return (
    <div className="flex h-[200px] flex-col items-center justify-center gap-2 text-muted-foreground">
      <Icon className="h-8 w-8 opacity-40" />
      <p className="text-sm">{message}</p>
    </div>
  );
}

export function RecentUsersSection({
  users,
  lastSyncedUsers,
  isLoading,
  isLoadingLastSynced,
  className,
}: RecentUsersSectionProps) {
  const [tab, setTab] = useState<'recent' | 'last-synced'>('recent');

  return (
    <div
      className={cn(
        'relative overflow-hidden rounded-2xl border border-border/60',
        'bg-gradient-to-br from-card/80 to-card/40 backdrop-blur-xl',
        className
      )}
    >
      <div className="flex items-center gap-3 border-b border-border/60 px-4 py-2">
        <div
          role="tablist"
          aria-label="Recent users"
          className="relative flex flex-1 rounded-lg bg-foreground/5 p-1"
        >
          {/* sliding pill */}
          <span
            aria-hidden
            className={cn(
              'absolute inset-y-1 w-1/2 rounded-md bg-white shadow-sm transition-transform duration-200 ease-out',
              tab === 'recent' ? 'translate-x-0' : 'translate-x-full'
            )}
          />
          {(
            [
              { value: 'recent', label: 'Recent users', icon: UsersIcon },
              { value: 'last-synced', label: 'Last synced', icon: RefreshCw },
            ] as const
          ).map(({ value, label, icon: Icon }) => {
            const active = tab === value;
            return (
              <button
                key={value}
                type="button"
                role="tab"
                id={`users-tab-${value}`}
                aria-selected={active}
                aria-controls={`users-panel-${value}`}
                tabIndex={active ? 0 : -1}
                onClick={() => setTab(value)}
                className={cn(
                  'relative z-10 flex flex-1 items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-2 py-1.5 text-sm font-medium transition-colors duration-200',
                  active
                    ? 'text-zinc-900'
                    : 'text-muted-foreground hover:text-foreground/70'
                )}
              >
                <Icon className="h-3.5 w-3.5 shrink-0" />
                {label}
              </button>
            );
          })}
        </div>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border/60 bg-muted/40">
          <UsersIcon className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
      </div>

      <div className="p-3">
        {tab === 'recent' && (
          <div
            role="tabpanel"
            id="users-panel-recent"
            aria-labelledby="users-tab-recent"
          >
            {isLoading ? (
              <SkeletonRows />
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
                        <span
                          className={cn(
                            'h-1.5 w-1.5 rounded-full',
                            user.has_active_connection
                              ? 'bg-[hsl(var(--success-muted))]'
                              : 'bg-[hsl(var(--destructive-muted))]'
                          )}
                        />
                        <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                          {user.has_active_connection ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState icon={UsersIcon} message="No users found" />
            )}
          </div>
        )}

        {tab === 'last-synced' && (
          <div
            role="tabpanel"
            id="users-panel-last-synced"
            aria-labelledby="users-tab-last-synced"
          >
            {isLoadingLastSynced ? (
              <SkeletonRows />
            ) : lastSyncedUsers.length > 0 ? (
              <div className="space-y-1">
                {lastSyncedUsers.map((user) => {
                  const userName =
                    user.first_name || user.last_name
                      ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
                      : user.email || 'Unknown User';
                  const syncedAt = user.last_synced_at;
                  const provider = user.last_synced_provider;
                  const relativeTime = syncedAt
                    ? formatDistanceToNow(new Date(syncedAt), {
                        addSuffix: true,
                      })
                    : 'Never';
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
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {provider && <SourceBadge provider={provider} />}
                        <div className="flex items-center gap-1">
                          {syncedAt && (
                            <span
                              className={cn(
                                'h-1.5 w-1.5 rounded-full',
                                syncRecencyDot(syncedAt)
                              )}
                            />
                          )}
                          <span
                            className={cn(
                              'text-[11px]',
                              syncedAt
                                ? syncRecencyColor(syncedAt)
                                : 'text-muted-foreground/50'
                            )}
                          >
                            {relativeTime}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState icon={RefreshCw} message="No synced users yet" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
