import { createFileRoute, Link } from '@tanstack/react-router';
import {
  ArrowLeft,
  RefreshCw,
  Link as LinkIcon,
  Activity,
  Heart,
  Moon,
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
import { Separator } from '@/components/ui/separator';
import {
  useUserConnections,
  useHealthSummary,
  useGenerateConnectionLink,
  useSyncUserData,
  useDisconnectProvider,
} from '@/hooks/api/use-health';
import { useUsers } from '@/hooks/api/use-users';
import { LoadingState } from '@/components/common/loading-spinner';
import { ErrorState } from '@/components/common/error-state';
import { toast } from 'sonner';

export const Route = createFileRoute('/_authenticated/users/$userId')({
  component: UserDetailPage,
});

function UserDetailPage() {
  const { userId } = Route.useParams();
  const { data: users } = useUsers();
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
    // Copy link to clipboard
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

  if (!user) {
    return <ErrorState message="User not found" />;
  }

  if (connectionsLoading || healthLoading) {
    return <LoadingState message="Loading user data..." />;
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
            <h1 className="text-3xl font-bold">
              {user.name || 'Unnamed User'}
            </h1>
            <p className="text-muted-foreground">{user.email}</p>
          </div>
        </div>
        <Button onClick={handleSync} disabled={syncMutation.isPending}>
          <RefreshCw
            className={`mr-2 h-4 w-4 ${syncMutation.isPending ? 'animate-spin' : ''}`}
          />
          Sync Data
        </Button>
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
        </CardContent>
      </Card>

      {healthSummary && (
        <div className="grid md:grid-cols-3 gap-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Heart Rate</CardTitle>
              <Heart className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {healthSummary.heartRate.average} bpm
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Range: {healthSummary.heartRate.min} -{' '}
                {healthSummary.heartRate.max} bpm
              </p>
              <Separator className="my-3" />
              <p className="text-xs text-muted-foreground">
                {healthSummary.heartRate.data.length} readings (7 days)
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Sleep</CardTitle>
              <Moon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatMinutes(healthSummary.sleep.averageMinutes)}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Efficiency: {healthSummary.sleep.averageEfficiency}%
              </p>
              <Separator className="my-3" />
              <p className="text-xs text-muted-foreground">
                {healthSummary.sleep.data.length} nights recorded
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Activity</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {healthSummary.activity.averageSteps.toLocaleString()}
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Average daily steps
              </p>
              <Separator className="my-3" />
              <p className="text-xs text-muted-foreground">
                {healthSummary.activity.totalActiveMinutes} active minutes (7
                days)
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Health Data Visualizations</CardTitle>
          <CardDescription>
            Charts will be implemented in Phase 3 with Recharts
          </CardDescription>
        </CardHeader>
        <CardContent className="h-64 flex items-center justify-center text-muted-foreground">
          <p>Heart Rate, Sleep, and Activity charts coming soon...</p>
        </CardContent>
      </Card>

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
    </div>
  );
}
