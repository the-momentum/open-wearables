// API services barrel export

export * from './client';
export * from './config';
export * from './types';

export { authService } from './services/auth.service';
export { metaService } from './services/meta.service';
export type {
  CoverageResponse,
  TimeseriesCategory,
  TimeseriesMetric,
  WorkoutField,
  SleepField,
  MenstrualCycleField,
  HealthScore,
} from './services/meta.service';
export { configService } from './services/config.service';
export type { AppConfig } from './services/config.service';
export { usersService } from './services/users.service';
export { dashboardService } from './services/dashboard.service';
export { webhooksService } from './services/webhooks.service';
export { syncStatusService } from './services/sync-status.service';
export type {
  SyncSource,
  SyncStage,
  SyncStatus,
  SyncStatusEvent,
  SyncRunSummary,
} from './services/sync-status.service';
