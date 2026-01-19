import type { ChartConfig } from '@/components/ui/chart';

/**
 * Chart configuration for heart rate visualizations
 */
export const HR_CHART_CONFIG = {
  hr: {
    label: 'Heart Rate (bpm)',
    color: '#f43f5e',
  },
  avgHr: {
    label: 'Avg HR (bpm)',
    color: '#f43f5e',
  },
} satisfies ChartConfig;

/**
 * Chart configuration for weight visualizations
 */
export const WEIGHT_CHART_CONFIG = {
  weight: {
    label: 'Weight (kg)',
    color: '#3b82f6',
  },
} satisfies ChartConfig;
