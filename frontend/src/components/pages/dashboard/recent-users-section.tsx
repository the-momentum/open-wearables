import { format } from 'date-fns';
import { cn } from '@/lib/utils';
import type { UserRead } from '@/lib/api/types';

export interface RecentUsersSectionProps {
  users: UserRead[];
  totalUsersCount: number;
  isLoading?: boolean;
  className?: string;
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
        'bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden',
        className
      )}
    >
      <div className="px-6 py-4 border-b border-zinc-800">
        <h2 className="text-sm font-medium text-white">Recent Users</h2>
        <p className="text-xs text-zinc-500 mt-1">
          Total users: {totalUsersCount}
        </p>
      </div>
      <div className="p-6 space-y-4">
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="animate-pulse">
                <div className="h-4 w-32 bg-zinc-800 rounded mb-1" />
                <div className="h-3 w-48 bg-zinc-800/50 rounded" />
              </div>
            ))}
          </div>
        ) : users.length > 0 ? (
          users.map((user) => {
            const userName =
              user.first_name || user.last_name
                ? `${user.first_name || ''} ${user.last_name || ''}`.trim()
                : user.email || 'Unknown User';
            const date = new Date(user.created_at);
            const formattedDate = isNaN(date.getTime())
              ? 'Invalid date'
              : format(date, 'MMM d, yyyy');
            return (
              <div key={user.id} className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-zinc-300">
                    {userName}
                  </p>
                  <p className="text-xs text-zinc-500">
                    {user.email || user.external_user_id || 'No email'}
                  </p>
                  <p className="text-xs text-zinc-600 mt-0.5">
                    Created on {formattedDate}
                  </p>
                </div>
                <span className="text-xs text-emerald-400">Active</span>
              </div>
            );
          })
        ) : (
          <div className="flex items-center justify-center h-[200px] text-zinc-600">
            <p className="text-sm">No users found</p>
          </div>
        )}
      </div>
    </div>
  );
}
