import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useState, useEffect } from 'react';
import {
  ArrowLeft,
  Link as LinkIcon,
  Activity,
  Heart,
  Dumbbell,
  Trash2,
  Check,
  Pencil,
  X,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  useHeartRate,
  useUserConnections,
  useWorkouts,
} from '@/hooks/api/use-health';
import { useUsers, useDeleteUser, useUpdateUser } from '@/hooks/api/use-users';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { formatDate, formatDuration, truncateId } from '@/lib/utils/format';
import { calculateHeartRateStats } from '@/lib/utils/health';
import { ConnectionCard } from '@/components/user/connection-card';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';

export const Route = createFileRoute('/_authenticated/users/$userId')({
  component: UserDetailPage,
});

function UserDetailPage() {
  const { userId } = Route.useParams();
  const navigate = useNavigate();
  const { data: users, isLoading: usersLoading } = useUsers();
  const { data: heartRateData, isLoading: heartRateLoading } =
    useHeartRate(userId);
  const { data: workouts, isLoading: workoutsLoading } = useWorkouts(userId, {
    limit: 10,
    sort_order: 'desc',
  });
  const { data: connections, isLoading: connectionsLoading } =
    useUserConnections(userId);
  const { mutate: deleteUser, isPending: isDeleting } = useDeleteUser();
  const { mutate: updateUser, isPending: isUpdating } = useUpdateUser();

  const user = users?.find((u) => u.id === userId);
  const heartRateStats = calculateHeartRateStats(heartRateData);
  const [copied, setCopied] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [editForm, setEditForm] = useState({
    first_name: '',
    last_name: '',
    email: '',
    external_user_id: '',
  });

  useEffect(() => {
    if (user) {
      setEditForm({
        first_name: user.first_name || '',
        last_name: user.last_name || '',
        email: user.email || '',
        external_user_id: user.external_user_id || '',
      });
    }
  }, [user]);

  const handleCopyPairLink = async () => {
    const pairLink = `${window.location.origin}/users/${userId}/pair`;
    await navigator.clipboard.writeText(pairLink);
    setCopied(true);
    toast.success('Pairing link copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDelete = () => {
    deleteUser(userId, {
      onSuccess: () => {
        navigate({ to: '/users' });
      },
    });
  };

  const handleEditSubmit = () => {
    updateUser(
      {
        id: userId,
        data: {
          first_name: editForm.first_name || null,
          last_name: editForm.last_name || null,
          email: editForm.email || null,
          external_user_id: editForm.external_user_id || null,
        },
      },
      {
        onSuccess: () => {
          setIsEditDialogOpen(false);
        },
      }
    );
  };

  if (!usersLoading && !user) {
    return (
      <div className="p-8">
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-12 text-center">
          <p className="text-zinc-400">User not found</p>
          <Link
            to="/users"
            className="mt-4 inline-flex items-center gap-2 px-4 py-2 bg-zinc-800 text-white rounded-md text-sm font-medium hover:bg-zinc-700 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Users
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/users"
            className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-md transition-colors"
          >
            <ArrowLeft className="h-5 w-5" />
          </Link>
          {usersLoading ? (
            <div className="space-y-2">
              <div className="h-7 w-48 bg-zinc-800 rounded animate-pulse" />
              <div className="h-4 w-32 bg-zinc-800/50 rounded animate-pulse" />
            </div>
          ) : (
            <div>
              <h1 className="text-2xl font-medium text-white">
                {user?.first_name || user?.last_name
                  ? `${user?.first_name || ''} ${user?.last_name || ''}`.trim()
                  : 'Unnamed User'}
              </h1>
              <p className="text-sm text-zinc-500">
                {user?.email || 'No email'}
              </p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopyPairLink}
            className="flex items-center gap-2 px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 text-emerald-600" />
                Copied!
              </>
            ) : (
              <>
                <LinkIcon className="h-4 w-4" />
                Copy Pairing Link
              </>
            )}
          </button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <button
                disabled={isDeleting}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Trash2 className="h-4 w-4" />
                {isDeleting ? 'Deleting...' : 'Delete User'}
              </button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete User</AlertDialogTitle>
                <AlertDialogDescription>
                  Are you sure you want to delete this user? This action cannot
                  be undone and will permanently remove all associated data.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDelete}
                  className="bg-red-600 text-white hover:bg-red-700"
                >
                  Delete
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </div>

      {/* User Information */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <h2 className="text-sm font-medium text-white">User Information</h2>
          <button
            onClick={() => setIsEditDialogOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-md transition-colors"
          >
            <Pencil className="h-3.5 w-3.5" />
            Edit
          </button>
        </div>
        <div className="p-6">
          {usersLoading ? (
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <div className="h-4 w-16 bg-zinc-800/50 rounded animate-pulse" />
                <div className="h-5 w-48 bg-zinc-800 rounded animate-pulse" />
              </div>
              <div className="space-y-2">
                <div className="h-4 w-16 bg-zinc-800/50 rounded animate-pulse" />
                <div className="h-5 w-32 bg-zinc-800 rounded animate-pulse" />
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div>
                <p className="text-xs text-zinc-500 mb-1">User ID</p>
                <code className="font-mono text-sm text-zinc-300 bg-zinc-800 px-2 py-1 rounded">
                  {truncateId(user?.id ?? '')}
                </code>
              </div>
              <div>
                <p className="text-xs text-zinc-500 mb-1">External User ID</p>
                <code className="font-mono text-sm text-zinc-300 bg-zinc-800 px-2 py-1 rounded">
                  {user?.external_user_id || '—'}
                </code>
              </div>
              <div>
                <p className="text-xs text-zinc-500 mb-1">Email</p>
                <p className="text-sm text-zinc-300">{user?.email || '—'}</p>
              </div>
              <div>
                <p className="text-xs text-zinc-500 mb-1">Created</p>
                <p className="text-sm text-zinc-300">
                  {formatDate(user?.created_at)}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Connected Providers */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <h2 className="text-sm font-medium text-white">
            Connected Providers
          </h2>
          <p className="text-xs text-zinc-500 mt-1">
            Wearable devices and health platforms connected to this user
          </p>
        </div>
        <div className="p-6">
          {connectionsLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {[1, 2].map((i) => (
                <div
                  key={i}
                  className="p-4 border border-zinc-800 rounded-lg space-y-3"
                >
                  <div className="flex items-center gap-3">
                    <div className="h-6 w-24 bg-zinc-800 rounded animate-pulse" />
                    <div className="h-5 w-16 bg-zinc-800/50 rounded animate-pulse" />
                  </div>
                  <div className="space-y-2">
                    <div className="h-4 w-40 bg-zinc-800/50 rounded animate-pulse" />
                    <div className="h-4 w-36 bg-zinc-800/50 rounded animate-pulse" />
                  </div>
                </div>
              ))}
            </div>
          ) : connections && connections.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {connections.map((connection) => (
                <ConnectionCard key={connection.id} connection={connection} />
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-zinc-500 mb-4">No providers connected yet</p>
              <button
                onClick={handleCopyPairLink}
                className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-800 text-white rounded-md text-sm font-medium hover:bg-zinc-700 transition-colors"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4 text-emerald-500" />
                    Link Copied!
                  </>
                ) : (
                  <>
                    <LinkIcon className="h-4 w-4" />
                    Copy Pairing Link
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Health Stats */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Heart Rate */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">Heart Rate</h3>
            <Heart className="h-4 w-4 text-zinc-500" />
          </div>
          <div className="p-6">
            {heartRateLoading ? (
              <div className="space-y-3">
                <div className="h-8 w-24 bg-zinc-800 rounded animate-pulse" />
                <div className="h-4 w-32 bg-zinc-800/50 rounded animate-pulse" />
              </div>
            ) : heartRateData && heartRateData.length > 0 ? (
              <>
                <div className="text-3xl font-medium text-white">
                  {heartRateStats.avg ?? '—'}{' '}
                  <span className="text-lg text-zinc-500">bpm</span>
                </div>
                <p className="text-xs text-zinc-500 mt-2">
                  Range: {heartRateStats.min ?? '—'} -{' '}
                  {heartRateStats.max ?? '—'} bpm
                </p>
                <div className="mt-4 pt-4 border-t border-zinc-800">
                  <p className="text-xs text-zinc-500">
                    {heartRateStats.count} readings
                  </p>
                </div>
              </>
            ) : (
              <p className="text-sm text-zinc-500">
                No heart rate data available
              </p>
            )}
          </div>
        </div>

        {/* Activity / Workouts */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">Workouts</h3>
            <Activity className="h-4 w-4 text-zinc-500" />
          </div>
          <div className="p-6">
            {workoutsLoading ? (
              <div className="space-y-3">
                <div className="h-8 w-20 bg-zinc-800 rounded animate-pulse" />
                <div className="h-4 w-28 bg-zinc-800/50 rounded animate-pulse" />
              </div>
            ) : workouts && workouts.length > 0 ? (
              <>
                <div className="text-3xl font-medium text-white">
                  {workouts.length}
                </div>
                <p className="text-xs text-zinc-500 mt-2">Total workouts</p>
                <div className="mt-4 pt-4 border-t border-zinc-800">
                  <p className="text-xs text-zinc-500">
                    Most recent:{' '}
                    {new Date(workouts[0].start_datetime).toLocaleDateString()}
                  </p>
                </div>
              </>
            ) : (
              <p className="text-sm text-zinc-500">No workout data available</p>
            )}
          </div>
        </div>
      </div>

      {/* Recent Workouts */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-medium text-white">Recent Workouts</h2>
            <p className="text-xs text-zinc-500 mt-1">
              Latest workout activities
            </p>
          </div>
          <Dumbbell className="h-4 w-4 text-zinc-500" />
        </div>
        <div className="p-6">
          {workoutsLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="p-4 border border-zinc-800 rounded-lg space-y-2"
                >
                  <div className="h-5 w-32 bg-zinc-800 rounded animate-pulse" />
                  <div className="h-4 w-48 bg-zinc-800/50 rounded animate-pulse" />
                </div>
              ))}
            </div>
          ) : workouts && workouts.length > 0 ? (
            <div className="space-y-3">
              {workouts.map((workout) => (
                <div
                  key={workout.id}
                  className="flex items-center justify-between p-4 border border-zinc-800 rounded-lg hover:border-zinc-700 transition-colors"
                >
                  <div>
                    <h4 className="font-medium text-white">
                      {workout.type || 'Workout'}
                    </h4>
                    <p className="text-xs text-zinc-500 mt-1">
                      {formatDate(workout.start_datetime)} •{' '}
                      {formatDuration(workout.duration_seconds)} •{' '}
                      {workout.source_name}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-zinc-400">
                      {workout.statistics.length} metrics
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-zinc-500 mb-4">No workouts recorded yet</p>
              <button
                onClick={handleCopyPairLink}
                className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-800 text-white rounded-md text-sm font-medium hover:bg-zinc-700 transition-colors"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4 text-emerald-500" />
                    Link Copied!
                  </>
                ) : (
                  <>
                    <LinkIcon className="h-4 w-4" />
                    Copy Pairing Link
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Edit User Dialog */}
      {isEditDialogOpen && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl w-full max-w-md shadow-2xl">
            <div className="p-6 border-b border-zinc-800 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-medium text-white">Edit User</h2>
                <p className="text-sm text-zinc-500 mt-1">
                  Update user information
                </p>
              </div>
              <button
                onClick={() => setIsEditDialogOpen(false)}
                className="p-2 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-md transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="first_name" className="text-zinc-300">
                    First Name
                  </Label>
                  <Input
                    id="first_name"
                    value={editForm.first_name}
                    onChange={(e) =>
                      setEditForm({ ...editForm, first_name: e.target.value })
                    }
                    placeholder="John"
                    className="bg-zinc-800 border-zinc-700"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="last_name" className="text-zinc-300">
                    Last Name
                  </Label>
                  <Input
                    id="last_name"
                    value={editForm.last_name}
                    onChange={(e) =>
                      setEditForm({ ...editForm, last_name: e.target.value })
                    }
                    placeholder="Doe"
                    className="bg-zinc-800 border-zinc-700"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="email" className="text-zinc-300">
                  Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={editForm.email}
                  onChange={(e) =>
                    setEditForm({ ...editForm, email: e.target.value })
                  }
                  placeholder="john@example.com"
                  className="bg-zinc-800 border-zinc-700"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="external_user_id" className="text-zinc-300">
                  External User ID
                </Label>
                <Input
                  id="external_user_id"
                  value={editForm.external_user_id}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      external_user_id: e.target.value,
                    })
                  }
                  placeholder="external-123"
                  className="bg-zinc-800 border-zinc-700"
                />
                <p className="text-xs text-zinc-500">
                  Optional identifier from your system
                </p>
              </div>
            </div>
            <div className="p-6 border-t border-zinc-800 flex justify-end gap-3">
              <button
                onClick={() => setIsEditDialogOpen(false)}
                className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleEditSubmit}
                disabled={isUpdating}
                className="px-4 py-2 text-sm font-medium bg-white text-black rounded-md hover:bg-zinc-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isUpdating ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
