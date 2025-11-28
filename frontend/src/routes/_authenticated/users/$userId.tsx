import { createFileRoute, Link } from '@tanstack/react-router';
import {
  ArrowLeft,
  Link as LinkIcon,
  Activity,
  Heart,
  Moon,
  Trash2,
} from 'lucide-react';
import {
  useUserConnections,
  useHealthSummary,
  useGenerateConnectionLink,
  useSyncUserData,
  useDisconnectProvider,
} from '@/hooks/api/use-health';
import { useUsers } from '@/hooks/api/use-users';
import { toast } from 'sonner';

export const Route = createFileRoute('/_authenticated/users/$userId')({
  component: UserDetailPage,
});

function UserDetailPage() {
  const { userId } = Route.useParams();
  const { data: users, isLoading: usersLoading } = useUsers();
  const { data: connections, isLoading: connectionsLoading } =
    useUserConnections(userId);
  const { data: healthSummary, isLoading: healthLoading } =
    useHealthSummary(userId);
  const generateLinkMutation = useGenerateConnectionLink();
  const syncMutation = useSyncUserData();
  const disconnectMutation = useDisconnectProvider();

  const user = users?.find((u) => u.id === userId);

  const handleGenerateLink = async (providerId: string) => {
    const result = await generateLinkMutation.mutateAsync({
      userId,
      providerId,
    });
    await navigator.clipboard.writeText(result.url);
    toast.success('Connection link copied to clipboard');
  };

  const handleSync = async () => {
    await syncMutation.mutateAsync(userId);
  };

  const handleDisconnect = async (
    connectionId: string,
    providerName: string
  ) => {
    if (confirm(`Are you sure you want to disconnect ${providerName}?`)) {
      await disconnectMutation.mutateAsync({ userId, connectionId });
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  const formatMinutes = (minutes: number) => {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}h ${mins}m`;
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
              <p className="text-sm text-zinc-500">{user?.email || 'No email'}</p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleGenerateLink('garmin')}
            disabled={generateLinkMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 bg-white text-black rounded-md text-sm font-medium hover:bg-zinc-200 transition-colors disabled:opacity-50"
          >
            <LinkIcon className="h-4 w-4" />
            Connect Wearables
          </button>
          <button
            onClick={() => {
              if (confirm('Are you sure you want to delete this user?')) {
                // TODO: implement delete user
              }
            }}
            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md text-sm font-medium hover:bg-red-700 transition-colors"
          >
            <Trash2 className="h-4 w-4" />
            Delete User
          </button>
        </div>
      </div>

      {/* User Information */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <h2 className="text-sm font-medium text-white">User Information</h2>
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
                  {user?.id.slice(0, 8)}...
                </code>
              </div>
              <div>
                <p className="text-xs text-zinc-500 mb-1">Client User ID</p>
                <code className="font-mono text-sm text-zinc-300 bg-zinc-800 px-2 py-1 rounded">
                  {user?.client_user_id}
                </code>
              </div>
              <div>
                <p className="text-xs text-zinc-500 mb-1">Email</p>
                <p className="text-sm text-zinc-300">{user?.email || '—'}</p>
              </div>
              <div>
                <p className="text-xs text-zinc-500 mb-1">Created</p>
                <p className="text-sm text-zinc-300">
                  {formatDate(user?.created_at ?? null)}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Connected Devices */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <h2 className="text-sm font-medium text-white">Connected Devices</h2>
          <p className="text-xs text-zinc-500 mt-1">
            Wearable devices and health platforms connected to this user
          </p>
        </div>
        <div className="p-6">
          {connectionsLoading ? (
            <div className="space-y-4">
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
            <div className="space-y-4">
              {connections.map((connection) => (
                <div
                  key={connection.id}
                  className="flex items-center justify-between p-4 border border-zinc-800 rounded-lg hover:border-zinc-700 transition-colors"
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-medium text-white">
                        {connection.providerName}
                      </h3>
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full ${
                          connection.status === 'active'
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : connection.status === 'error'
                              ? 'bg-red-500/20 text-red-400'
                              : 'bg-zinc-700 text-zinc-400'
                        }`}
                      >
                        {connection.status}
                      </span>
                      <span
                        className={`px-2 py-0.5 text-xs rounded-full ${
                          connection.syncStatus === 'success'
                            ? 'bg-emerald-500/20 text-emerald-400'
                            : connection.syncStatus === 'failed'
                              ? 'bg-red-500/20 text-red-400'
                              : 'bg-zinc-700 text-zinc-400'
                        }`}
                      >
                        {connection.syncStatus}
                      </span>
                    </div>
                    <div className="mt-2 text-xs text-zinc-500 space-y-1">
                      <p>Connected: {formatDate(connection.connectedAt)}</p>
                      <p>Last Sync: {formatDate(connection.lastSyncAt)}</p>
                      <p>Data Points: {connection.dataPoints.toLocaleString()}</p>
                      {connection.syncError && (
                        <p className="text-red-400">
                          Error: {connection.syncError}
                        </p>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() =>
                      handleDisconnect(connection.id, connection.providerName)
                    }
                    disabled={disconnectMutation.isPending}
                    className="px-3 py-1.5 text-xs text-zinc-400 border border-zinc-700 rounded-md hover:text-white hover:border-zinc-600 transition-colors disabled:opacity-50"
                  >
                    Disconnect
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-zinc-500 mb-4">No devices connected yet</p>
              <button
                onClick={() => handleGenerateLink('garmin')}
                disabled={generateLinkMutation.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 bg-zinc-800 text-white rounded-md text-sm font-medium hover:bg-zinc-700 transition-colors disabled:opacity-50"
              >
                <LinkIcon className="h-4 w-4" />
                Generate Connection Link
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Health Stats */}
      <div className="grid md:grid-cols-3 gap-6">
        {/* Heart Rate */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">Heart Rate</h3>
            <Heart className="h-4 w-4 text-zinc-500" />
          </div>
          <div className="p-6">
            {healthLoading ? (
              <div className="space-y-3">
                <div className="h-8 w-24 bg-zinc-800 rounded animate-pulse" />
                <div className="h-4 w-32 bg-zinc-800/50 rounded animate-pulse" />
              </div>
            ) : healthSummary ? (
              <>
                <div className="text-3xl font-medium text-white">
                  {healthSummary.heartRate.average}{' '}
                  <span className="text-lg text-zinc-500">bpm</span>
                </div>
                <p className="text-xs text-zinc-500 mt-2">
                  Range: {healthSummary.heartRate.min} -{' '}
                  {healthSummary.heartRate.max} bpm
                </p>
                <div className="mt-4 pt-4 border-t border-zinc-800">
                  <p className="text-xs text-zinc-500">
                    {healthSummary.heartRate.data.length} readings (7 days)
                  </p>
                </div>
              </>
            ) : (
              <p className="text-sm text-zinc-500">No data available</p>
            )}
          </div>
        </div>

        {/* Sleep */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">Sleep</h3>
            <Moon className="h-4 w-4 text-zinc-500" />
          </div>
          <div className="p-6">
            {healthLoading ? (
              <div className="space-y-3">
                <div className="h-8 w-20 bg-zinc-800 rounded animate-pulse" />
                <div className="h-4 w-28 bg-zinc-800/50 rounded animate-pulse" />
              </div>
            ) : healthSummary ? (
              <>
                <div className="text-3xl font-medium text-white">
                  {formatMinutes(healthSummary.sleep.averageMinutes)}
                </div>
                <p className="text-xs text-zinc-500 mt-2">
                  Efficiency: {healthSummary.sleep.averageEfficiency}%
                </p>
                <div className="mt-4 pt-4 border-t border-zinc-800">
                  <p className="text-xs text-zinc-500">
                    {healthSummary.sleep.data.length} nights recorded
                  </p>
                </div>
              </>
            ) : (
              <p className="text-sm text-zinc-500">No data available</p>
            )}
          </div>
        </div>

        {/* Activity */}
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">Activity</h3>
            <Activity className="h-4 w-4 text-zinc-500" />
          </div>
          <div className="p-6">
            {healthLoading ? (
              <div className="space-y-3">
                <div className="h-8 w-20 bg-zinc-800 rounded animate-pulse" />
                <div className="h-4 w-28 bg-zinc-800/50 rounded animate-pulse" />
              </div>
            ) : healthSummary ? (
              <>
                <div className="text-3xl font-medium text-white">
                  {healthSummary.activity.averageSteps.toLocaleString()}
                </div>
                <p className="text-xs text-zinc-500 mt-2">Average daily steps</p>
                <div className="mt-4 pt-4 border-t border-zinc-800">
                  <p className="text-xs text-zinc-500">
                    {healthSummary.activity.totalActiveMinutes} active minutes (7
                    days)
                  </p>
                </div>
              </>
            ) : (
              <p className="text-sm text-zinc-500">No data available</p>
            )}
          </div>
        </div>
      </div>

      {/* Health Data Visualizations */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <h2 className="text-sm font-medium text-white">
            Health Data Visualizations
          </h2>
          <p className="text-xs text-zinc-500 mt-1">
            Charts will be implemented in Phase 3 with Recharts
          </p>
        </div>
        <div className="h-64 flex items-center justify-center text-zinc-500">
          <p className="text-sm">
            Heart Rate, Sleep, and Activity charts coming soon...
          </p>
        </div>
      </div>

      {/* AI Health Assistant */}
      <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-zinc-800">
          <h2 className="text-sm font-medium text-white">AI Health Assistant</h2>
          <p className="text-xs text-zinc-500 mt-1">
            Chat interface will be implemented in Phase 3
          </p>
        </div>
        <div className="h-64 flex items-center justify-center text-zinc-500">
          <p className="text-sm">AI-powered health insights coming soon...</p>
        </div>
      </div>
    </div>
  );
}
