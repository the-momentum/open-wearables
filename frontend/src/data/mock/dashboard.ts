// Mock dashboard data

import type {
  DashboardStats,
  ApiCallsDataPoint,
  DataPointsDataPoint,
  AutomationTriggersDataPoint,
  TriggersByTypeDataPoint,
} from '../../lib/api/types';
import { format, subDays } from 'date-fns';

export const mockDashboardStats: DashboardStats = {
  totalUsers: 1234,
  activeConnections: 573,
  dataPoints: 45200,
  apiCalls: 12300,
};

// Generate 30 days of API calls data
export const mockApiCallsData: ApiCallsDataPoint[] = Array.from(
  { length: 30 },
  (_, i) => ({
    date: format(subDays(new Date(), 30 - i), 'yyyy-MM-dd'),
    calls: Math.floor(300 + Math.random() * 200),
  })
);

// Generate 30 days of data points data
export const mockDataPointsData: DataPointsDataPoint[] = Array.from(
  { length: 30 },
  (_, i) => ({
    date: format(subDays(new Date(), 30 - i), 'yyyy-MM-dd'),
    points: Math.floor(1000 + Math.random() * 500),
  })
);

// Generate 30 days of automation triggers data
export const mockAutomationTriggersData: AutomationTriggersDataPoint[] =
  Array.from({ length: 30 }, (_, i) => ({
    date: format(subDays(new Date(), 30 - i), 'yyyy-MM-dd'),
    triggers: Math.floor(10 + Math.random() * 30),
    users: Math.floor(5 + Math.random() * 15),
  }));

// Triggers by type
export const mockTriggersByTypeData: TriggersByTypeDataPoint[] = [
  { type: 'Sleep Alert', count: 145 },
  { type: 'Heart Rate', count: 89 },
  { type: 'Activity Goal', count: 67 },
  { type: 'Recovery', count: 43 },
  { type: 'Custom', count: 28 },
];
