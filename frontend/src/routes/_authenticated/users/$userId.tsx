import { createFileRoute, Link, useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import {
  ArrowLeft,
  RefreshCw,
  Link as LinkIcon,
  Trash2,
  Copy,
  Check,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  useUserConnections,
  useGenerateConnectionLink,
  useSyncUserData,
  useDisconnectProvider,
  useUserHeartRate,
  useUserWorkouts,
  useUserRecords,
} from '@/hooks/api/use-health';
import { useUser, useDeleteUser } from '@/hooks/api/use-users';
import { LoadingState } from '@/components/common/loading-spinner';
import { ErrorState } from '@/components/common/error-state';
import { HeartRateChart, WorkoutsTable, RecordsTable } from '@/components/health';
import { toast } from 'sonner';
import type {
  HeartRateListResponse,
  WorkoutListResponse,
  RecordListResponse,
} from '@/lib/api/types';

const emptyHeartRateData: HeartRateListResponse = {
  data: [],
  recovery_data: [],
  summary: {
    total_records: 0,
    avg_heart_rate: 0,
    max_heart_rate: 0,
    min_heart_rate: 0,
    avg_recovery_rate: 0,
    max_recovery_rate: 0,
    min_recovery_rate: 0,
  },
  meta: { requested_at: '', filters: {}, result_count: 0, date_range: {} },
};

const emptyWorkoutsData: WorkoutListResponse = {
  data: [],
  meta: {
    requested_at: '',
    filters: {},
    result_count: 0,
    total_count: 0,
    date_range: { start: '', end: '', duration_days: 0 },
  },
};

const emptyRecordsData: RecordListResponse = {
  data: [],
  meta: {
    requested_at: '',
    filters: {},
    result_count: 0,
    total_count: 0,
    date_range: { start: '', end: '', duration_days: 0 },
  },
};

export const Route = createFileRoute('/_authenticated/users/$userId')({
  component: UserDetailPage,
});

function UserDetailPage() {
  const { userId } = Route.useParams();
  const navigate = useNavigate();
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [copiedId, setCopiedId] = useState(false);

  const {
    data: user,
    isLoading: userLoading,
    error: userError,
  } = useUser(userId);
  const { data: connections, isLoading: connectionsLoading } =
    useUserConnections(userId);
  const { data: heartRateData, isLoading: heartRateLoading } =
    useUserHeartRate(userId, { limit: 100 });
  const { data: workoutsData, isLoading: workoutsLoading } =
    useUserWorkouts(userId, { limit: 20 });
  const { data: recordsData, isLoading: recordsLoading } =
    useUserRecords(userId, { limit: 20 });
  const generateLinkMutation = useGenerateConnectionLink();
  const syncMutation = useSyncUserData();
  const disconnectMutation = useDisconnectProvider();
  const deleteUserMutation = useDeleteUser();

  const handleCopyId = async () => {
    await navigator.clipboard.writeText(userId);
    setCopiedId(true);
    toast.success('User ID copied to clipboard');
    setTimeout(() => setCopiedId(false), 2000);
  };

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

  const handleDelete = () => {
    deleteUserMutation.mutate(userId, {
      onSuccess: () => {
        setIsDeleteDialogOpen(false);
        navigate({ to: '/users' });
      },
    });
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };


  if (userLoading) {
    return <LoadingState message="Loading user..." />;
  }

  if (userError || !user) {
    return (
      <ErrorState
        title="User not found"
        message="The requested user could not be found."
      />
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/users">
            <Button variant="outline" size="sm">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Users
            </Button>
          </Link>
          <div>
            <h1 className="text-3xl font-bold">User Details</h1>
            <div className="flex items-center gap-2 mt-1">
              <code className="font-mono text-sm text-muted-foreground bg-muted px-2 py-1 rounded">
                {userId}
              </code>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={handleCopyId}
              >
                {copiedId ? (
                  <Check className="h-3 w-3 text-green-500" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
              </Button>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleSync} disabled={syncMutation.isPending}>
            <RefreshCw
              className={`mr-2 h-4 w-4 ${syncMutation.isPending ? 'animate-spin' : ''}`}
            />
            Sync Data
          </Button>
          <Button
            variant="destructive"
            onClick={() => setIsDeleteDialogOpen(true)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete User
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>User Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-sm text-muted-foreground">User ID</p>
              <p className="font-mono text-sm">{user.id}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Created</p>
              <p className="text-sm">{formatDate(user.created_at)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Connected Devices</CardTitle>
          <CardDescription>
            Wearable devices and health platforms connected to this user
          </CardDescription>
        </CardHeader>
        <CardContent>
          {connectionsLoading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="space-y-4">
              {connections && connections.length > 0 ? (
                connections.map((connection) => (
                  <div
                    key={connection.id}
                    className="flex items-center justify-between p-4 border rounded-lg"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <h3 className="font-semibold">
                          {connection.providerName}
                        </h3>
                        <Badge
                          variant={
                            connection.status === 'active'
                              ? 'default'
                              : connection.status === 'error'
                                ? 'destructive'
                                : 'secondary'
                          }
                        >
                          {connection.status}
                        </Badge>
                        <Badge
                          variant={
                            connection.syncStatus === 'success'
                              ? 'default'
                              : connection.syncStatus === 'failed'
                                ? 'destructive'
                                : 'secondary'
                          }
                        >
                          {connection.syncStatus}
                        </Badge>
                      </div>
                      <div className="mt-2 text-sm text-muted-foreground space-y-1">
                        <p>Connected: {formatDate(connection.connectedAt)}</p>
                        <p>Last Sync: {formatDate(connection.lastSyncAt)}</p>
                        <p>
                          Data Points: {connection.dataPoints.toLocaleString()}
                        </p>
                        {connection.syncError && (
                          <p className="text-destructive">
                            Error: {connection.syncError}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          handleDisconnect(connection.id, connection.providerName)
                        }
                        disabled={disconnectMutation.isPending}
                      >
                        Disconnect
                      </Button>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <p>No devices connected yet</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-4"
                    onClick={() => handleGenerateLink('garmin')}
                    disabled={generateLinkMutation.isPending}
                  >
                    <LinkIcon className="mr-2 h-4 w-4" />
                    Generate Connection Link
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {!connectionsLoading && (
        <>
          <HeartRateChart
            data={heartRateData ?? emptyHeartRateData}
            isLoading={heartRateLoading}
          />
          <WorkoutsTable
            data={workoutsData ?? emptyWorkoutsData}
            isLoading={workoutsLoading}
          />
          <RecordsTable
            data={recordsData ?? emptyRecordsData}
            isLoading={recordsLoading}
          />
        </>
      )}

      <Card>
        <CardHeader>
          <CardTitle>AI Health Assistant</CardTitle>
          <CardDescription>
            Chat interface will be implemented in Phase 3
          </CardDescription>
        </CardHeader>
        <CardContent className="h-64 flex items-center justify-center text-muted-foreground">
          <p>AI-powered health insights coming soon...</p>
        </CardContent>
      </Card>

      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete User?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. This will permanently delete the
              user and all associated data including:
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
              <li>All wearable device connections</li>
              <li>All health data (heart rate, sleep, activity)</li>
              <li>All automation triggers for this user</li>
            </ul>
            <div className="mt-4 p-3 bg-muted rounded-md">
              <p className="text-sm text-muted-foreground">User ID:</p>
              <code className="font-mono text-sm">{userId}</code>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsDeleteDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteUserMutation.isPending}
            >
              {deleteUserMutation.isPending ? 'Deleting...' : 'Delete User'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
