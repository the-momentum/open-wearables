import {
  CheckCircle2,
  EllipsisVertical,
  Loader2,
  RefreshCw,
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
} from '@/hooks/api/use-health';

interface ConnectionCardProps {
  connection: UserConnection;
  className?: string;
}

export function ConnectionCard({ connection, className }: ConnectionCardProps) {
  const { mutate: synchronizeDataFromProvider, isPending: isSynchronizing } =
    useSynchronizeDataFromProvider(connection.provider, connection.user_id);

  // For Garmin, check backfill status
  const { data: backfillStatus } = useGarminBackfillStatus(
    connection.user_id,
    connection.provider === 'garmin'
  );

  const isGarminBackfilling =
    connection.provider === 'garmin' && backfillStatus?.in_progress;

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
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => synchronizeDataFromProvider()}
          disabled={isSynchronizing || isGarminBackfilling}
        >
          {isGarminBackfilling ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Day {(backfillStatus?.days_completed ?? 0) + 1}/
              {backfillStatus?.target_days ?? 30} (
              {backfillStatus?.current_data_type ?? 'syncing'})
            </>
          ) : isSynchronizing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Sync Now
            </>
          ) : (
            <>
              <RefreshCw className="h-4 w-4" />
              Sync Now
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
