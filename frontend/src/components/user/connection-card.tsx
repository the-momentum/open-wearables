import {
  CheckCircle2,
  EllipsisVertical,
  Loader2,
  RefreshCw,
  RotateCcw,
  TriangleAlert,
  Unlink,
  Watch,
  XCircle,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { UserConnection } from '@/lib/api/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import {
  useSynchronizeDataFromProvider,
  useGarminBackfillStatus,
  useRetryGarminBackfill,
} from '@/hooks/api/use-health';

interface ConnectionCardProps {
  connection: UserConnection;
  className?: string;
}

// Format data type name for display (e.g., "bodyComps" -> "Body Comps")
function formatTypeName(typeName: string): string {
  return typeName
    .replace(/([A-Z])/g, ' $1')
    .replace(/^./, (str) => str.toUpperCase())
    .trim();
}

export function ConnectionCard({ connection, className }: ConnectionCardProps) {
  const { mutate: synchronizeDataFromProvider, isPending: isSynchronizing } =
    useSynchronizeDataFromProvider(connection.provider, connection.user_id);

  // For Garmin, check backfill status (30-day webhook sync)
  const { data: backfillStatus } = useGarminBackfillStatus(
    connection.user_id,
    connection.provider === 'garmin'
  );

  const { mutate: retryBackfill, isPending: isRetrying } =
    useRetryGarminBackfill(connection.user_id);

  // Check if backfill is in progress
  const isBackfillInProgress =
    connection.provider === 'garmin' &&
    backfillStatus?.overall_status === 'in_progress';

  // Get failed types from backfill status
  const failedTypes = backfillStatus?.types
    ? Object.entries(backfillStatus.types)
        .filter(([, v]) => v.status === 'failed')
        .map(([type, v]) => ({ type, error: v.error }))
    : [];

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'active':
        return (
          <Badge variant="success" className="flex items-center gap-1">
            <CheckCircle2 className="h-3 w-3 text-green-400" />
            Active
          </Badge>
        );
      case 'revoked':
        return (
          <Badge variant="destructive" className="flex items-center gap-1">
            <XCircle className="h-3 w-3 text-red-400" />
            Revoked
          </Badge>
        );
      case 'expired':
        return (
          <Badge variant="warning" className="flex items-center gap-1">
            <TriangleAlert className="h-3 w-3 text-orange-400" />
            Expired
          </Badge>
        );
      default:
        return null;
    }
  };

  return (
    <Card className={cn('relative', className)}>
      <CardHeader className="pb-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            {/* Provider Icon - placeholder for now TODO: Implement provider icon */}
            <div className="h-14 w-14 rounded-full bg-white flex items-center justify-center">
              <Watch className="h-6 w-6 text-zinc-400" />
            </div>
            <div>
              <h3 className="font-semibold text-card-foreground text-lg">
                {connection.provider}
              </h3>
              <p className="text-sm text-muted-foreground mt-0.5">
                Last sync:{' '}
                {connection.last_synced_at
                  ? formatDistanceToNow(new Date(connection.last_synced_at), {
                      addSuffix: true,
                    })
                  : 'Never'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {renderStatusBadge(connection.status)}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="p-0 h-8 w-8">
                  <EllipsisVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  className="text-destructive focus:text-destructive cursor-pointer"
                  onClick={() => {
                    toast.error('Disconnecting not implemented yet'); // TODO: Implement disconnect
                  }}
                >
                  <Unlink className="mr-2 h-4 w-4" />
                  Disconnect
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Show backfill progress for Garmin */}
        {isBackfillInProgress && backfillStatus && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              <span className="text-sm text-muted-foreground">
                Fetching historical data...{' '}
                <span className="font-medium">
                  {backfillStatus.success_count}/{backfillStatus.total_types}{' '}
                  complete
                </span>
              </span>
            </div>
            {/* Progress bar */}
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{
                  width: `${(backfillStatus.success_count / backfillStatus.total_types) * 100}%`,
                }}
              />
            </div>
          </div>
        )}

        {/* Show failed backfill types with retry buttons */}
        {failedTypes.length > 0 && (
          <div className="space-y-2 p-3 bg-destructive/10 rounded-lg border border-destructive/20">
            <p className="text-sm font-medium text-destructive">
              Some data failed to sync:
            </p>
            <div className="space-y-1.5">
              {failedTypes.map(({ type, error }) => (
                <div
                  key={type}
                  className="flex items-center justify-between text-sm"
                >
                  <div className="flex-1 min-w-0">
                    <span className="font-medium">{formatTypeName(type)}</span>
                    {error && (
                      <p className="text-xs text-muted-foreground truncate">
                        {error}
                      </p>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs ml-2"
                    onClick={() => retryBackfill(type)}
                    disabled={isRetrying}
                  >
                    <RotateCcw className="h-3 w-3 mr-1" />
                    Retry
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sync button - only for non-Garmin providers */}
        {connection.provider !== 'garmin' && (
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="flex-1"
              onClick={() => synchronizeDataFromProvider()}
              disabled={isSynchronizing}
            >
              {isSynchronizing ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Syncing...
                </>
              ) : (
                <>
                  <RefreshCw className="h-4 w-4" />
                  Sync Now
                </>
              )}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
