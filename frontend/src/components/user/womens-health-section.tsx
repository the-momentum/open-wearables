import { format } from 'date-fns';
import { Heart, Trash2 } from 'lucide-react';
import { useState } from 'react';
import {
  useMenstrualCycles,
  useDeleteMenstrualCycle,
} from '@/hooks/api/use-health';
import { useCursorPagination } from '@/hooks/use-cursor-pagination';
import { useDateRange } from '@/hooks/use-date-range';
import type { DateRangeValue } from '@/components/ui/date-range-selector';
import { CursorPagination } from '@/components/common/cursor-pagination';
import { MetricCard } from '@/components/common/metric-card';
import { SourceBadge } from '@/components/common/source-badge';
import { SectionHeader } from '@/components/common/section-header';
import { EventDeleteDialog } from '@/components/common/event-delete-dialog';
import type { MenstrualCycleRecord } from '@/lib/api/types';

interface WomensHealthSectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

const PHASE_STYLES: Record<
  string,
  { bg: string; text: string; label: string }
> = {
  menstrual: {
    bg: 'bg-rose-500/20',
    text: 'text-rose-400',
    label: 'Menstrual',
  },
  menstruation: {
    bg: 'bg-rose-500/20',
    text: 'text-rose-400',
    label: 'Menstruation',
  },
  follicular: {
    bg: 'bg-violet-500/20',
    text: 'text-violet-400',
    label: 'Follicular',
  },
  ovulation: {
    bg: 'bg-amber-500/20',
    text: 'text-amber-400',
    label: 'Ovulation',
  },
  luteal: { bg: 'bg-blue-500/20', text: 'text-blue-400', label: 'Luteal' },
  pregnancy: {
    bg: 'bg-pink-500/20',
    text: 'text-pink-400',
    label: 'Pregnancy',
  },
};

function phaseStyle(phaseType: string | null) {
  if (!phaseType)
    return { bg: 'bg-zinc-500/20', text: 'text-zinc-400', label: 'Unknown' };
  return (
    PHASE_STYLES[phaseType.toLowerCase()] ?? {
      bg: 'bg-zinc-500/20',
      text: 'text-zinc-400',
      label: phaseType,
    }
  );
}

function PhaseBadge({ phaseType }: { phaseType: string | null }) {
  const style = phaseStyle(phaseType);
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text}`}
    >
      {style.label}
    </span>
  );
}

function CycleCard({
  record,
  userId,
}: {
  record: MenstrualCycleRecord;
  userId: string;
}) {
  const [showDelete, setShowDelete] = useState(false);
  const deleteRecord = useDeleteMenstrualCycle(userId);

  return (
    <>
      <div className="px-6 py-4 flex items-center gap-4 hover:bg-muted/30 transition-colors group">
        {/* Cycle index + date */}
        <div className="w-44 shrink-0">
          <p className="text-sm text-foreground">
            First day: {format(new Date(record.start_time), 'MMM d, yyyy')}
          </p>
          <p className="text-sm text-foreground">
            Last day: {format(new Date(record.end_time), 'MMM d, yyyy')}
          </p>
        </div>

        {/* Phase */}
        <div className="w-32 shrink-0">
          <p className="text-xs text-muted-foreground mb-0.5">Cycle phase</p>
          <div className="flex items-center gap-1.5">
            <PhaseBadge phaseType={record.current_phase_type} />
            {record.is_predicted_cycle && (
              <span className="text-xs text-muted-foreground">predicted</span>
            )}
          </div>
        </div>

        {/* Metrics */}
        <div className="flex gap-40 flex-1 text-sm">
          {record.day_in_cycle !== null && (
            <div>
              <p className="text-xs text-muted-foreground">Cycle day</p>
              <p className="font-medium text-foreground">
                {record.day_in_cycle}
              </p>
            </div>
          )}
          {record.cycle_length !== null && (
            <div>
              <p className="text-xs text-muted-foreground">Cycle length</p>
              <p className="font-medium text-foreground">
                {record.cycle_length}d
              </p>
            </div>
          )}
          {record.period_length !== null && (
            <div>
              <p className="text-xs text-muted-foreground">Period length</p>
              <p className="font-medium text-foreground">
                {record.period_length}d
              </p>
            </div>
          )}
          {record.days_until_next_phase !== null && (
            <div>
              <p className="text-xs text-muted-foreground">Next phase</p>
              <p className="font-medium text-foreground">
                in {record.days_until_next_phase}d
              </p>
            </div>
          )}
          {record.fertile_window_start !== null &&
            record.length_of_fertile_window !== null && (
              <div>
                <p className="text-xs text-muted-foreground">Fertile window</p>
                <p className="font-medium text-foreground">
                  day {record.fertile_window_start}–
                  {record.fertile_window_start +
                    record.length_of_fertile_window -
                    1}
                </p>
              </div>
            )}
        </div>

        {/* Source + delete */}
        <div className="flex items-center gap-3 shrink-0">
          <SourceBadge provider={record.source.provider} />
          <button
            onClick={() => setShowDelete(true)}
            className="p-1.5 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors opacity-0 group-hover:opacity-100"
            aria-label="Delete record"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <EventDeleteDialog
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={() => deleteRecord.mutate(record.id)}
        isPending={deleteRecord.isPending}
        title="Delete Cycle Record"
        description="This will permanently remove this menstrual cycle record."
      />
    </>
  );
}

export function WomensHealthSection({
  userId,
  dateRange,
  onDateRangeChange,
}: WomensHealthSectionProps) {
  const { startDate, endDate } = useDateRange(dateRange);
  const pagination = useCursorPagination();

  const { data, isLoading } = useMenstrualCycles(userId, {
    start_date: startDate,
    end_date: endDate,
    cursor: pagination.currentCursor ?? undefined,
    limit: 20,
  });

  const records = data?.data ?? [];
  const totalInRange = records.length;
  const mostRecent = records[0];

  return (
    <div className="space-y-6">
      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <MetricCard
          icon={Heart}
          iconColor="text-rose-400"
          iconBgColor="bg-rose-500/10"
          value={String(data?.pagination ? totalInRange : '—')}
          label="Records in range"
        />
        {mostRecent && (
          <MetricCard
            icon={Heart}
            iconColor={phaseStyle(mostRecent.current_phase_type).text}
            iconBgColor={phaseStyle(mostRecent.current_phase_type).bg}
            value={phaseStyle(mostRecent.current_phase_type).label}
            label="Latest phase"
          />
        )}
        {mostRecent && mostRecent.cycle_length !== null && (
          <MetricCard
            icon={Heart}
            iconColor="text-violet-400"
            iconBgColor="bg-violet-500/10"
            value={`${mostRecent.cycle_length}d`}
            label="Last cycle length"
          />
        )}
      </div>

      {/* Records table */}
      <div className="rounded-xl border border-border/60 bg-card/30 overflow-hidden">
        <SectionHeader
          title="Cycle Records"
          dateRange={dateRange}
          onDateRangeChange={(v) => {
            pagination.reset();
            onDateRangeChange(v);
          }}
        />

        {isLoading ? (
          <div className="divide-y divide-border/40">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="px-6 py-4 flex items-center gap-4">
                <div className="h-4 w-28 bg-muted rounded animate-pulse" />
                <div className="h-5 w-24 bg-muted rounded animate-pulse" />
                <div className="flex gap-6 flex-1">
                  <div className="h-4 w-16 bg-muted rounded animate-pulse" />
                  <div className="h-4 w-16 bg-muted rounded animate-pulse" />
                </div>
              </div>
            ))}
          </div>
        ) : records.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground text-sm">
            No cycle records found for this period.
          </div>
        ) : (
          <div className="divide-y divide-border/40">
            {records.map((record) => (
              <CycleCard key={record.id} record={record} userId={userId} />
            ))}
          </div>
        )}

        <CursorPagination
          currentPage={pagination.currentPage}
          hasPrevPage={pagination.hasPrevPage}
          hasNextPage={!!data?.pagination?.has_more}
          onPrevPage={pagination.goToPrevPage}
          onNextPage={() =>
            data?.pagination?.next_cursor &&
            pagination.goToNextPage(data.pagination.next_cursor)
          }
        />
      </div>
    </div>
  );
}
