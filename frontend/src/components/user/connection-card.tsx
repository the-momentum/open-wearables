import { useState } from 'react';
import {
  CheckCircle2,
  ChevronDown,
  EllipsisVertical,
  History,
  Info,
  Loader2,
  RefreshCw,
  RotateCcw,
  Timer,
  TriangleAlert,
  Unlink,
  Watch,
  XCircle,
  Zap,
} from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { UserConnection } from '@/lib/api/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { cn } from '@/lib/utils';
import {
  useDisconnectProvider,
  useSynchronizeDataFromProvider,
  useSyncHistoricalData,
  useGarminBackfillStatus,
  useGarminCancelBackfill,
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

// Parse scope string into individual scope items
// Handles both comma-separated (Strava) and space-separated (Whoop, Polar) formats
function parseScopeString(scope: string): string[] {
  return scope.split(/[,\s]+/).filter(Boolean);
}

export function ConnectionCard({ connection, className }: ConnectionCardProps) {
  const [showDisconnectDialog, setShowDisconnectDialog] = useState(false);

  const { mutate: disconnectProvider, isPending: isDisconnecting } =
    useDisconnectProvider(connection.provider, connection.user_id);

  const { mutate: synchronizeDataFromProvider, isPending: isSynchronizing } =
    useSynchronizeDataFromProvider(connection.provider, connection.user_id);

  // For Garmin, check backfill status (30-day webhook sync)
  const { data: backfillStatus } = useGarminBackfillStatus(
    connection.user_id,
    connection.provider === 'garmin'
  );

  const { mutate: cancelBackfill, isPending: isCancelling } =
    useGarminCancelBackfill(connection.user_id);

  const { mutate: retryBackfill, isPending: isRetrying } =
    useRetryGarminBackfill(connection.user_id);

  const { mutate: syncHistorical, isPending: isSyncingHistorical } =
    useSyncHistoricalData(connection.provider, connection.user_id);

  // Check if backfill is in progress (includes retry phase)
  const isBackfillInProgress =
    connection.provider === 'garmin' &&
    (backfillStatus?.overall_status === 'in_progress' ||
      backfillStatus?.overall_status === 'retry_in_progress');

  // Check if currently in retry phase
  const isRetryPhase =
    connection.provider === 'garmin' &&
    backfillStatus?.overall_status === 'retry_in_progress';

  // Check if backfill was cancelled
  const isBackfillCancelled =
    connection.provider === 'garmin' &&
    backfillStatus?.overall_status === 'cancelled';

  // Check if permanently failed
  const isPermanentlyFailed =
    connection.provider === 'garmin' &&
    backfillStatus?.permanently_failed === true;

  // Get timed-out types from summary
  const timedOutTypes = backfillStatus?.summary
    ? Object.entries(backfillStatus.summary)
        .filter(([, v]) => v.timed_out > 0)
        .map(([type, v]) => ({ type, timedOutCount: v.timed_out }))
    : [];

  // Parse scope items once for display
  const scopeItems = connection.scope ? parseScopeString(connection.scope) : [];

  // Get failed types from summary
  const failedTypes = backfillStatus?.summary
    ? Object.entries(backfillStatus.summary)
        .filter(([, v]) => v.failed > 0)
        .map(([type, v]) => ({ type, failedCount: v.failed }))
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
            <XCircle className="h-3 w-3 text-[hsl(var(--destructive-muted))]" />
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
              <Watch className="h-6 w-6 text-muted-foreground" />
            </div>
            <div>
              <h3 className="font-semibold text-card-foreground text-lg">
                {connection.provider}
              </h3>
              <p className="text-sm text-muted-foreground mt-0.5">
                Last live sync:{' '}
                {connection.last_synced_at
                  ? formatDistanceToNow(new Date(connection.last_synced_at), {
                      addSuffix: true,
                    })
                  : 'Never'}
              </p>
              {connection.live_sync_mode && (
                <div className="mt-1.5">
                  {connection.live_sync_mode === 'webhook' ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      <Zap className="h-3 w-3" />
                      Webhook
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground border border-border">
                      <Timer className="h-3 w-3" />
                      Periodic pull
                    </span>
                  )}
                </div>
              )}
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
                {connection.status !== 'revoked' && (
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive cursor-pointer"
                    disabled={isDisconnecting}
                    onClick={() => setShowDisconnectDialog(true)}
                  >
                    <Unlink className="mr-2 h-4 w-4" />
                    Disconnect
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
            <AlertDialog
              open={showDisconnectDialog}
              onOpenChange={setShowDisconnectDialog}
            >
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>
                    Disconnect {connection.provider}?
                  </AlertDialogTitle>
                  <AlertDialogDescription>
                    This will revoke the connection. The user will need to
                    reconnect to {connection.provider} to resume data syncing.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={() => disconnectProvider()}>
                    Disconnect
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Show data scope */}
        {scopeItems.length > 0 && (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-default"
              >
                <Info className="h-3.5 w-3.5 shrink-0" />
                <span>Data scope</span>
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" align="start" className="max-w-sm">
              <div className="flex flex-wrap gap-1 py-0.5">
                {scopeItems.map((scopeItem) => (
                  <Badge
                    key={scopeItem}
                    variant="secondary"
                    className="text-[11px] font-normal px-1.5 py-0"
                  >
                    {scopeItem}
                  </Badge>
                ))}
              </div>
            </TooltipContent>
          </Tooltip>
        )}

        {/* Show backfill progress for Garmin */}
        {isBackfillInProgress && backfillStatus && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                {isRetryPhase && backfillStatus.retry_type ? (
                  <span className="text-sm text-muted-foreground">
                    Retrying {formatTypeName(backfillStatus.retry_type)}{' '}
                    {backfillStatus.retry_window !== null && (
                      <span>(window {backfillStatus.retry_window + 1})...</span>
                    )}
                  </span>
                ) : (
                  <span className="text-sm text-muted-foreground">
                    Fetching historical data...{' '}
                    <span className="font-medium">
                      {backfillStatus.current_window} of{' '}
                      {backfillStatus.total_windows} windows complete
                    </span>
                  </span>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => cancelBackfill()}
                disabled={isCancelling}
              >
                <XCircle className="h-3 w-3 mr-1" />
                Cancel
              </Button>
            </div>
            {/* Progress bar */}
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all duration-300"
                style={{
                  width: `${backfillStatus.total_windows > 0 ? (backfillStatus.current_window / backfillStatus.total_windows) * 100 : 0}%`,
                }}
              />
            </div>
            {/* Attempt counter */}
            {backfillStatus.attempt_count > 0 && (
              <span className="text-xs text-muted-foreground">
                Attempt {backfillStatus.attempt_count} of{' '}
                {backfillStatus.max_attempts}
              </span>
            )}
          </div>
        )}

        {/* Show cancelled backfill status */}
        {isBackfillCancelled && (
          <div className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg border">
            <XCircle className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">
              Backfill cancelled
            </span>
          </div>
        )}

        {/* Show permanently failed state */}
        {isPermanentlyFailed && (
          <div className="flex items-center gap-2 p-3 bg-destructive/10 rounded-lg border border-destructive/20">
            <XCircle className="h-4 w-4 text-destructive" />
            <span className="text-sm text-destructive">
              Backfill failed after {backfillStatus?.max_attempts} attempts.
              Please disconnect and reconnect your Garmin.
            </span>
          </div>
        )}

        {/* Show timed-out backfill types with retry buttons (warning/amber styling) */}
        {timedOutTypes.length > 0 &&
          !isBackfillInProgress &&
          !isPermanentlyFailed && (
            <div className="space-y-2 p-3 bg-[hsl(var(--warning-muted)/0.1)] rounded-lg border border-[hsl(var(--warning-muted)/0.2)]">
              <p className="text-sm font-medium text-[hsl(var(--warning-muted))] dark:text-[hsl(var(--warning-muted))]">
                Some data types timed out:
              </p>
              <div className="space-y-1.5">
                {timedOutTypes.map(({ type, timedOutCount }) => (
                  <div
                    key={type}
                    className="flex items-center justify-between text-sm"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="font-medium">
                        {formatTypeName(type)}
                      </span>
                      <p className="text-xs text-muted-foreground">
                        Timed out in {timedOutCount} window
                        {timedOutCount > 1 ? 's' : ''}
                      </p>
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

        {/* Show failed types (error/destructive styling, no retry) */}
        {failedTypes.length > 0 &&
          !isBackfillInProgress &&
          !isPermanentlyFailed && (
            <div className="space-y-2 p-3 bg-destructive/10 rounded-lg border border-destructive/20">
              <p className="text-sm font-medium text-destructive">
                Some data types failed:
              </p>
              <div className="space-y-1.5">
                {failedTypes.map(({ type, failedCount }) => (
                  <div key={type} className="flex items-center text-sm">
                    <XCircle className="h-3 w-3 text-destructive mr-2" />
                    <span className="font-medium">{formatTypeName(type)}</span>
                    <span className="text-xs text-muted-foreground ml-2">
                      Failed in {failedCount} window
                      {failedCount > 1 ? 's' : ''}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

        {/* Action buttons */}
        {connection.status === 'active' && (
          <div className="flex gap-2">
            {/* Provider with a hard history cap: single constrained button */}
            {connection.max_historical_days !== null &&
              connection.max_historical_days !== undefined &&
              !isBackfillInProgress &&
              !isPermanentlyFailed && (
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={() =>
                    syncHistorical(connection.max_historical_days as number)
                  }
                  disabled={isSyncingHistorical}
                >
                  {isSyncingHistorical ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Starting...
                    </>
                  ) : (
                    <>
                      <History className="h-4 w-4" />
                      Sync {connection.max_historical_days}-day History
                    </>
                  )}
                </Button>
              )}

            {/* Unconstrained providers: Sync History dropdown + Force Live Sync */}
            {(connection.max_historical_days === null ||
              connection.max_historical_days === undefined) &&
              connection.rest_pull &&
              !isPermanentlyFailed && (
                <>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        disabled={isSyncingHistorical}
                      >
                        {isSyncingHistorical ? (
                          <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Starting...
                          </>
                        ) : (
                          <>
                            <History className="h-4 w-4" />
                            Sync History
                            <ChevronDown className="h-3 w-3 ml-auto opacity-60" />
                          </>
                        )}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => syncHistorical(7)}>
                        Last 7 days
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => syncHistorical(30)}>
                        Last 30 days
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => syncHistorical(90)}>
                        Last 3 months
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => syncHistorical(180)}>
                        Last 6 months
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => syncHistorical(365)}>
                        Last year
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>

                  {connection.live_sync_mode !== 'webhook' && (
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
                          Force Live Sync
                        </>
                      )}
                    </Button>
                  )}
                </>
              )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
