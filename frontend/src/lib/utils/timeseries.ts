import { format } from 'date-fns';
import type { TimeSeriesSample } from '@/lib/api/types';

/**
 * Prepared heart rate chart data point
 */
export interface HrChartDataPoint {
  time: string;
  hr: number;
}

/**
 * Prepare heart rate time series data for chart display.
 * Filters to heart_rate type, sorts by timestamp, and formats time.
 */
export function prepareHrChartData(
  data: TimeSeriesSample[] | undefined
): HrChartDataPoint[] {
  if (!data?.length) return [];

  return data
    .filter((d) => d.type === 'heart_rate')
    .sort(
      (a, b) =>
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    )
    .map((d) => ({
      time: format(new Date(d.timestamp), 'HH:mm'),
      hr: d.value,
    }));
}
