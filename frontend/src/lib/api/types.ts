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

export interface CountWithGrowth {
  count: number;
  weekly_growth: number;
}

export interface DataPointsInfo {
  count: number;
  weekly_growth: number;
}

export interface DashboardStats {
  total_users: CountWithGrowth;
  active_conn: CountWithGrowth;
  data_points: DataPointsInfo;
}

export interface Provider {
  provider: string;
  name: string;
  has_cloud_api: boolean;
  is_enabled: boolean;
  icon_url: string;
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
  user_id: string;
  provider: string;
  provider_user_id?: string;
  provider_username?: string;
  scope?: string;
  id: string;
  status: 'active' | 'revoked' | 'expired';
  last_synced_at?: string;
  created_at: string;
  updated_at: string;
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

export interface EventRecordResponse {
  id: string;
  user_id: string;
  provider_id: string | null;
  category: string;
  type: string | null;
  source_name: string;
  device_id: string | null;
  duration_seconds: string | null;
  start_datetime: string;
  end_datetime: string;
  heart_rate_min: number | string | null;
  heart_rate_max: number | string | null;
  heart_rate_avg: number | string | null;
  steps_min: number | string | null;
  steps_max: number | string | null;
  steps_avg: number | string | null;
  max_speed: number | string | null;
  max_watts: number | string | null;
  moving_time_seconds: number | string | null;
  total_elevation_gain: number | string | null;
  average_speed: number | string | null;
  average_watts: number | string | null;
  elev_high: number | string | null;
  elev_low: number | string | null;
  sleep_total_duration_minutes: number | string | null;
  sleep_time_in_bed_minutes: number | string | null;
  sleep_efficiency_score: number | string | null;
  sleep_deep_minutes: number | string | null;
  sleep_rem_minutes: number | string | null;
  sleep_light_minutes: number | string | null;
  sleep_awake_minutes: number | string | null;
}

export interface HeartRateSampleResponse {
  id: string;
  device_id: string | null;
  recorded_at: string;
  value: number | string;
  series_type: 'heart_rate';
}

export interface HealthDataParams {
  start_datetime?: string;
  end_datetime?: string;
  device_id?: string;
  limit?: number;
  offset?: number;
  [key: string]: string | number | undefined;
}
