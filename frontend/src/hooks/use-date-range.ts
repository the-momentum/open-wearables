import { useMemo } from 'react';
import type { DateRangeValue } from '@/components/ui/date-range-selector';

interface DateRange {
  startDate: string;
  endDate: string;
}

interface DateRangeParams {
  start_date: string;
  end_date: string;
}

interface DateRangeDates {
  startDate: Date;
  endDate: Date;
}

/**
 * Hook to calculate date range from a DateRangeValue (number of days).
 * Returns ISO date strings for API calls.
 */
export function useDateRange(dateRange: DateRangeValue): DateRange {
  return useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - dateRange);
    return {
      startDate: start.toISOString(),
      endDate: end.toISOString(),
    };
  }, [dateRange]);
}

/**
 * Hook to calculate date range from a DateRangeValue (number of days).
 * Returns Date objects for flexible formatting.
 */
export function useDateRangeDates(dateRange: DateRangeValue): DateRangeDates {
  return useMemo(() => {
    const end = new Date();
    const start = new Date();
    start.setDate(end.getDate() - dateRange);
    return { startDate: start, endDate: end };
  }, [dateRange]);
}

/**
 * Hook to get an "all time" date range for fetching complete data.
 * Returns a stable object with start_date and end_date for API params.
 */
export function useAllTimeRange(): DateRangeParams {
  return useMemo(() => {
    const start = new Date('2000-01-01');
    const end = new Date();
    return {
      start_date: start.toISOString(),
      end_date: end.toISOString(),
    };
  }, []);
}

/**
 * Hook to get an "all time" date range as unix timestamps (seconds).
 * Used for APIs that expect unix timestamp format.
 */
export function useAllTimeRangeTimestamp(): DateRangeParams {
  return useMemo(() => {
    const start = new Date('2000-01-01');
    const end = new Date();
    return {
      start_date: Math.floor(start.getTime() / 1000).toString(),
      end_date: Math.floor(end.getTime() / 1000).toString(),
    };
  }, []);
}
