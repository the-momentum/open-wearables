import {
  DateRangeSelector,
  type DateRangeValue,
} from '@/components/ui/date-range-selector';

interface SectionHeaderProps {
  title: string;
  dateRange?: DateRangeValue;
  onDateRangeChange?: (value: DateRangeValue) => void;
  rightContent?: React.ReactNode;
}

/**
 * A reusable section header with optional date range selector.
 */
export function SectionHeader({
  title,
  dateRange,
  onDateRangeChange,
  rightContent,
}: SectionHeaderProps) {
  return (
    <div className="px-6 py-4 border-b border-border/60 flex items-center justify-between">
      <h3 className="text-sm font-medium text-foreground">{title}</h3>
      {dateRange !== undefined && onDateRangeChange && (
        <DateRangeSelector value={dateRange} onChange={onDateRangeChange} />
      )}
      {rightContent}
    </div>
  );
}
