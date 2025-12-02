export interface ApiErrorResponse {
  message: string;
  code: string;
  statusCode: number;
  details?: Record<string, unknown>;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface UserRead {
  id: string;
  created_at: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  external_user_id: string | null;
}

export interface UserCreate {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  external_user_id?: string | null;
}

export interface UserUpdate {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  external_user_id?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  developer_id: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name?: string;
}

export interface RegisterResponse {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ResetPasswordRequest {
  token: string;
  password: string;
}

export interface DashboardStats {
  totalUsers: number;
  activeConnections: number;
  dataPoints: number;
  apiCalls: number;
}

export interface Provider {
  id: string;
  name: string;
  description: string;
  logoUrl: string;
  isAvailable: boolean;
  features: string[];
  authType: 'oauth2' | 'api_key';
}

export type WearableProvider =
  | 'fitbit'
  | 'garmin'
  | 'oura'
  | 'whoop'
  | 'strava'
  | 'google-fit'
  | 'withings';

export interface UserConnection {
  id: string;
  userId: string;
  providerId: string;
  providerName: string;
  status: 'active' | 'error' | 'pending' | 'disconnected';
  connectedAt: string;
  lastSyncAt: string | null;
  syncStatus: 'success' | 'failed' | 'pending' | 'syncing';
  syncError?: string;
  dataPoints: number;
}

export interface HeartRateData {
  id: string;
  userId: string;
  timestamp: string;
  value: number;
  source: string;
}

export interface SleepData {
  id: string;
  userId: string;
  date: string;
  startTime: string;
  endTime: string;
  totalMinutes: number;
  deepMinutes: number;
  lightMinutes: number;
  remMinutes: number;
  awakeMinutes: number;
  efficiency: number;
  quality: 'excellent' | 'good' | 'fair' | 'poor';
  source: string;
}

export interface ActivityData {
  id: string;
  userId: string;
  date: string;
  steps: number;
  activeMinutes: number;
  calories: number;
  distance: number; // km
  floors: number;
  source: string;
}

export interface HealthDataSummary {
  userId: string;
  period: string;
  heartRate: {
    average: number;
    min: number;
    max: number;
    data: HeartRateData[];
  };
  sleep: {
    averageMinutes: number;
    averageEfficiency: number;
    data: SleepData[];
  };
  activity: {
    averageSteps: number;
    totalActiveMinutes: number;
    data: ActivityData[];
  };
  lastUpdated: string;
}

export interface HeartRatePoint {
  timestamp: string;
  bpm: number;
}

export interface SleepSession {
  date: string;
  duration: number; // minutes
  efficiency: number; // percentage
  stages: {
    deep: number;
    light: number;
    rem: number;
    awake: number;
  };
}

export interface ActivitySummary {
  date: string;
  steps: number;
  calories: number;
  distance: number; // meters
  activeMinutes: number;
}

export interface ApiKey {
  id: string; // This is the actual API key value (sk-...)
  name: string;
  created_by: string;
  created_at: string;
}

export interface ApiKeyCreate {
  name: string;
}

export interface Automation {
  id: string;
  name: string;
  description: string;
  webhookUrl: string;
  isEnabled: boolean;
  createdAt: string;
  updatedAt: string;
  lastTriggered: string | null;
  triggerCount: number;
}

export interface AutomationCreate {
  name: string;
  description: string;
  webhookUrl: string;
  isEnabled?: boolean;
}

export interface AutomationUpdate {
  name?: string;
  description?: string;
  webhookUrl?: string;
  isEnabled?: boolean;
}

export interface AutomationTrigger {
  id: string;
  automationId: string;
  userId: string;
  userName: string;
  userEmail: string;
  triggeredAt: string;
  data: Record<string, unknown>;
  webhookStatus: 'success' | 'failed' | 'pending';
  webhookResponse?: Record<string, unknown>;
  markedIncorrect?: boolean;
}

export interface TestAutomationResult {
  automationId: string;
  totalTriggers: number;
  dateRange: { start: string; end: string };
  executionTime: number;
  instances: AutomationTrigger[];
}

export interface RequestLog {
  id: string;
  timestamp: string;
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE' | 'PUT';
  endpoint: string;
  statusCode: number;
  responseTime: number;
  request: {
    headers: Record<string, string>;
    body?: unknown;
    query?: Record<string, string>;
  };
  response: {
    headers: Record<string, string>;
    body?: unknown;
  };
  error?: {
    message: string;
    stack?: string;
  };
}

export interface ApiCallsDataPoint {
  date: string;
  calls: number;
}

export interface DataPointsDataPoint {
  date: string;
  points: number;
}

export interface AutomationTriggersDataPoint {
  date: string;
  triggers: number;
  users: number;
}

export interface TriggersByTypeDataPoint {
  type: string;
  count: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export interface ChatRequest {
  message: string;
  userId?: string;
}

export interface HeartRateValue {
  value: number;
  unit: string;
}

export interface HeartRateDataResponse {
  id: number;
  workout_id: string;
  date: string;
  source: string | null;
  units: string | null;
  avg: HeartRateValue | null;
  min: HeartRateValue | null;
  max: HeartRateValue | null;
}

export interface HeartRateRecoveryResponse {
  id: number;
  workout_id: string;
  date: string;
  source: string | null;
  units: string | null;
  avg: HeartRateValue | null;
  min: HeartRateValue | null;
  max: HeartRateValue | null;
}

export interface HeartRateSummary {
  total_records: number;
  avg_heart_rate: number;
  max_heart_rate: number;
  min_heart_rate: number;
  avg_recovery_rate: number;
  max_recovery_rate: number;
  min_recovery_rate: number;
}

export interface HeartRateMeta {
  requested_at: string;
  filters: Record<string, unknown>;
  result_count: number;
  date_range: Record<string, unknown>;
}

export interface HeartRateListResponse {
  data: HeartRateDataResponse[];
  recovery_data: HeartRateRecoveryResponse[];
  summary: HeartRateSummary;
  meta: HeartRateMeta;
}

export interface DateRange {
  start: string;
  end: string;
  duration_days: number;
}

export interface WorkoutSummary {
  total_statistics: number;
  avg_statistic_value: number;
  max_statistic_value: number;
  min_statistic_value: number;
  avg_heart_rate: number;
  max_heart_rate: number;
  min_heart_rate: number;
  total_calories: number;
}

/**
 * Workout response from backend
 * GET /api/v1/users/{user_id}/workouts
 */
export interface WorkoutResponse {
  id: string;
  type: string | null;
  duration_seconds: string;
  source_name: string;
  start_datetime: string;
  end_datetime: string;
  statistics: WorkoutStatisticResponse[];
}

/**
 * Workout statistic response from backend
 * GET /api/v1/users/{user_id}/heart-rate
 */
export interface WorkoutStatisticResponse {
  id: string;
  user_id: string;
  workout_id: string;
  type: string;
  start_datetime: string;
  end_datetime: string;
  min: number | null;
  max: number | null;
  avg: number | null;
  unit: string;
}

export interface WorkoutMeta {
  requested_at: string;
  filters: Record<string, unknown>;
  result_count: number;
  total_count: number;
  date_range: DateRange;
}

export interface WorkoutListResponse {
  data: WorkoutResponse[];
  meta: WorkoutMeta;
}

export interface MetadataEntryResponse {
  id: string;
  key: string;
  value: string;
}

export interface RecordResponse {
  id: string;
  type: string;
  sourceName: string;
  startDate: string;
  endDate: string;
  unit: string;
  value: string;
  user_id: string;
  recordMetadata: MetadataEntryResponse[];
}

export interface RecordMeta {
  requested_at: string;
  filters: Record<string, unknown>;
  result_count: number;
  total_count: number;
  date_range: DateRange;
}

export interface RecordListResponse {
  data: RecordResponse[];
  meta: RecordMeta;
}

export interface HealthDataParams {
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
  [key: string]: string | number | undefined;
}
