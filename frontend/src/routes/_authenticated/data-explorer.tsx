import { useState } from 'react';
import { createFileRoute } from '@tanstack/react-router';
import { Database, Dumbbell, Gauge, Moon, UserSearch } from 'lucide-react';
import { PageHeader } from '@/components/ui/page-header';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { UserPicker } from '@/components/data-explorer/user-picker';
import { TimeseriesExplorer } from '@/components/data-explorer/timeseries-explorer';
import { WorkoutsExplorer } from '@/components/data-explorer/workouts-explorer';
import { SleepExplorer } from '@/components/data-explorer/sleep-explorer';
import { ScoresExplorer } from '@/components/data-explorer/scores-explorer';
import { useUserDataSummary } from '@/hooks/api/use-health';
import { formatNumber } from '@/lib/utils/format';

interface DataExplorerSearch {
  userId?: string;
}

export const Route = createFileRoute('/_authenticated/data-explorer')({
  component: DataExplorerPage,
  validateSearch: (search: Record<string, unknown>): DataExplorerSearch => ({
    userId:
      typeof search.userId === 'string' && search.userId
        ? search.userId
        : undefined,
  }),
});

function DataExplorerPage() {
  const { userId } = Route.useSearch();
  const navigate = Route.useNavigate();

  const setUserId = (id: string | undefined) => {
    navigate({ search: { userId: id }, replace: true });
  };

  return (
    <div className="space-y-6 p-6 md:p-8">
      <PageHeader
        title="Data Explorer"
        description="Browse every data point collected for a user — raw samples, workouts, sleep sessions, and health scores."
      />

      <UserPicker selectedUserId={userId} onSelect={setUserId} />

      {userId ? (
        <ExplorerContent userId={userId} />
      ) : (
        <div className="rounded-xl border border-dashed border-border/60 bg-muted/10 p-16 text-center">
          <UserSearch className="mx-auto h-10 w-10 text-muted-foreground/40" />
          <p className="mt-3 text-sm text-muted-foreground">
            Select a user above to explore their data.
          </p>
        </div>
      )}
    </div>
  );
}

function ExplorerContent({ userId }: { userId: string }) {
  const [tab, setTab] = useState('timeseries');
  const { data: summary } = useUserDataSummary(userId);

  return (
    <Tabs value={tab} onValueChange={setTab}>
      <TabsList>
        <TabsTrigger value="timeseries" className="gap-2">
          <Database className="h-3.5 w-3.5" />
          Data Points
          <TabCount value={summary?.total_data_points} />
        </TabsTrigger>
        <TabsTrigger value="workouts" className="gap-2">
          <Dumbbell className="h-3.5 w-3.5" />
          Workouts
          <TabCount value={summary?.total_workouts} />
        </TabsTrigger>
        <TabsTrigger value="sleep" className="gap-2">
          <Moon className="h-3.5 w-3.5" />
          Sleep
          <TabCount value={summary?.total_sleep_events} />
        </TabsTrigger>
        <TabsTrigger value="scores" className="gap-2">
          <Gauge className="h-3.5 w-3.5" />
          Health Scores
        </TabsTrigger>
      </TabsList>

      <TabsContent value="timeseries">
        <TimeseriesExplorer userId={userId} />
      </TabsContent>
      <TabsContent value="workouts">
        <WorkoutsExplorer userId={userId} />
      </TabsContent>
      <TabsContent value="sleep">
        <SleepExplorer userId={userId} />
      </TabsContent>
      <TabsContent value="scores">
        <ScoresExplorer userId={userId} />
      </TabsContent>
    </Tabs>
  );
}

function TabCount({ value }: { value: number | undefined }) {
  if (value === undefined) return null;
  return (
    <span className="rounded-full border border-border/60 bg-muted/40 px-1.5 py-0.5 text-[10px] tabular-nums text-muted-foreground">
      {formatNumber(value)}
    </span>
  );
}
