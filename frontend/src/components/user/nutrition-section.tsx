import { format } from 'date-fns';
import { Apple, Droplet, Flame, Trash2, Wheat } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useMeals, useDeleteMeal } from '@/hooks/api/use-health';
import { useCursorPagination } from '@/hooks/use-cursor-pagination';
import { useDateRange } from '@/hooks/use-date-range';
import type { DateRangeValue } from '@/components/ui/date-range-selector';
import { CursorPagination } from '@/components/common/cursor-pagination';
import { MetricCard } from '@/components/common/metric-card';
import { DataSourceInfo } from '@/components/common/data-source-info';
import { SectionHeader } from '@/components/common/section-header';
import { EventDeleteDialog } from '@/components/common/event-delete-dialog';
import { formatCalories } from '@/lib/utils/format';
import type { Meal } from '@/lib/api/types';

const EMPTY_MEALS: Meal[] = [];

interface NutritionSectionProps {
  userId: string;
  dateRange: DateRangeValue;
  onDateRangeChange: (value: DateRangeValue) => void;
}

const MEAL_TYPE_STYLES: Record<
  string,
  { bg: string; text: string; label: string }
> = {
  breakfast: {
    bg: 'bg-amber-500/20',
    text: 'text-amber-400',
    label: 'Breakfast',
  },
  lunch: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', label: 'Lunch' },
  dinner: { bg: 'bg-indigo-500/20', text: 'text-indigo-400', label: 'Dinner' },
  snack: { bg: 'bg-violet-500/20', text: 'text-violet-400', label: 'Snack' },
};

function mealTypeStyle(mealType: string | null) {
  if (!mealType)
    return { bg: 'bg-zinc-500/20', text: 'text-zinc-400', label: 'Unknown' };
  return (
    MEAL_TYPE_STYLES[mealType.toLowerCase()] ?? {
      bg: 'bg-zinc-500/20',
      text: 'text-zinc-400',
      label: mealType,
    }
  );
}

function MealTypeBadge({ mealType }: { mealType: string | null }) {
  const style = mealTypeStyle(mealType);
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text}`}
    >
      {style.label}
    </span>
  );
}

function formatMacro(grams: number | null | undefined): string {
  if (grams === null || grams === undefined) return '-';
  return `${Math.round(grams)}g`;
}

function MealRow({ meal, userId }: { meal: Meal; userId: string }) {
  const [showDelete, setShowDelete] = useState(false);
  const deleteMeal = useDeleteMeal(userId);

  return (
    <>
      <div className="px-6 py-4 flex items-center gap-4 hover:bg-muted/30 transition-colors group">
        {/* Type + date */}
        <div className="w-40 shrink-0">
          <MealTypeBadge mealType={meal.meal_type} />
          <p className="text-xs text-muted-foreground mt-1">
            {format(new Date(meal.timestamp), 'MMM d, yyyy HH:mm')}
          </p>
        </div>

        {/* Name */}
        <div className="w-40 shrink-0">
          <p className="text-sm text-foreground truncate">{meal.name || '-'}</p>
        </div>

        {/* Metrics */}
        <div className="flex gap-8 flex-1 text-sm">
          <div>
            <p className="text-xs text-muted-foreground">Calories</p>
            <p className="font-medium text-foreground">
              {formatCalories(meal.calories_kcal)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Protein</p>
            <p className="font-medium text-foreground">
              {formatMacro(meal.macros?.protein_g)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Carbs</p>
            <p className="font-medium text-foreground">
              {formatMacro(meal.macros?.carbohydrates_g)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Fat</p>
            <p className="font-medium text-foreground">
              {formatMacro(meal.macros?.fat_g)}
            </p>
          </div>
          {meal.water_ml !== null && (
            <div>
              <p className="text-xs text-muted-foreground">Water</p>
              <p className="font-medium text-foreground">
                {Math.round(meal.water_ml)} ml
              </p>
            </div>
          )}
        </div>

        {/* Source + delete */}
        <div className="flex items-center gap-3 shrink-0">
          <DataSourceInfo source={meal.source} />
          <button
            onClick={() => setShowDelete(true)}
            className="p-1.5 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors opacity-0 group-hover:opacity-100"
            aria-label="Delete meal"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <EventDeleteDialog
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={() =>
          deleteMeal.mutate(meal.id, { onSuccess: () => setShowDelete(false) })
        }
        isPending={deleteMeal.isPending}
        title="Delete Meal"
        description="This will permanently remove this meal entry. Its correlated nutrient samples are kept, unlinked from the meal."
      />
    </>
  );
}

export function NutritionSection({
  userId,
  dateRange,
  onDateRangeChange,
}: NutritionSectionProps) {
  const { startDate, endDate } = useDateRange(dateRange);
  const pagination = useCursorPagination();

  const { data, isLoading } = useMeals(userId, {
    start_date: startDate,
    end_date: endDate,
    cursor: pagination.currentCursor ?? undefined,
    limit: 20,
  });

  const meals = data?.data ?? EMPTY_MEALS;

  const stats = useMemo(() => {
    if (meals.length === 0) return null;
    const withCalories = meals.filter((m) => m.calories_kcal !== null);
    const totalCalories = withCalories.reduce(
      (sum, m) => sum + (m.calories_kcal ?? 0),
      0
    );
    const totalProtein = meals.reduce(
      (sum, m) => sum + (m.macros?.protein_g ?? 0),
      0
    );
    const totalWater = meals.reduce((sum, m) => sum + (m.water_ml ?? 0), 0);
    return {
      count: meals.length,
      avgCalories: withCalories.length
        ? totalCalories / withCalories.length
        : null,
      totalProtein,
      totalWater,
    };
  }, [meals]);

  return (
    <div className="space-y-6">
      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MetricCard
          icon={Apple}
          iconColor="text-emerald-400"
          iconBgColor="bg-emerald-500/10"
          value={String(stats?.count ?? '—')}
          label="Meals in range"
        />
        <MetricCard
          icon={Flame}
          iconColor="text-orange-400"
          iconBgColor="bg-orange-500/10"
          value={
            stats?.avgCalories !== null && stats?.avgCalories !== undefined
              ? formatCalories(stats.avgCalories)
              : '—'
          }
          label="Avg calories / meal"
        />
        <MetricCard
          icon={Wheat}
          iconColor="text-amber-400"
          iconBgColor="bg-amber-500/10"
          value={stats ? formatMacro(stats.totalProtein) : '—'}
          label="Total protein"
        />
        <MetricCard
          icon={Droplet}
          iconColor="text-sky-400"
          iconBgColor="bg-sky-500/10"
          value={stats ? `${Math.round(stats.totalWater)} ml` : '—'}
          label="Total water"
        />
      </div>

      {/* Meals table */}
      <div className="rounded-xl border border-border/60 bg-card/30 overflow-hidden">
        <SectionHeader
          title="Meals"
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
        ) : meals.length === 0 ? (
          <div className="px-6 py-12 text-center text-muted-foreground text-sm">
            No meals found for this period.
          </div>
        ) : (
          <div className="divide-y divide-border/40">
            {meals.map((meal) => (
              <MealRow key={meal.id} meal={meal} userId={userId} />
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
