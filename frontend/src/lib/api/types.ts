export interface ApiErrorResponse {
  message: string;
  code: string;
  statusCode: number;
  details?: Record<string, unknown>;
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

export interface UserQueryParams {
  page?: number;
  limit?: number;
  sort_by?: 'created_at' | 'email' | 'first_name' | 'last_name';
  sort_order?: 'asc' | 'desc';
  search?: string;
  email?: string;
  external_user_id?: string;
}

export interface PaginatedUsersResponse {
  items: UserRead[];
  total: number;
  page: number;
  limit: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    next_cursor: string | null;
    previous_cursor: string | null;
    has_more: boolean;
  };
  metadata: {
    resolution: string | null;
    sample_count: number | null;
    start_time: string | null;
    end_time: string | null;
  };
}

export interface UserUpdate {
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  external_user_id?: string | null;
}

export interface PresignedURLRequest {
  filename: string;
  expiration_seconds?: number;
  max_file_size?: number;
}

export interface PresignedURLResponse {
  upload_url: string;
  form_fields: Record<string, string>;
  file_key: string;
  expires_in: number;
  max_file_size: number;
  bucket: string;
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

export interface TimeSeriesSample {
  timestamp: string;
  type: string;
  value: number;
  unit: string;
}

export interface TimeSeriesParams {
  start_time: string;
  end_time: string;
  types?: string[];
  resolution?: 'raw' | '1min' | '5min' | '15min' | '1hour';
  cursor?: string;
  limit?: number;
  [key: string]: string | string[] | number | undefined;
}

export interface ResetPasswordRequest {
  token: string;
  password: string;
}

export interface CountWithGrowth {
  count: number;
  weekly_growth: number;
}

export interface SeriesTypeMetric {
  series_type: string;
  count: number;
}

export interface WorkoutTypeMetric {
  workout_type: string | null;
  count: number;
}

export interface DataPointsInfo {
  count: number;
  weekly_growth: number;
  top_series_types: SeriesTypeMetric[];
  top_workout_types: WorkoutTypeMetric[];
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

// ============================================================================
// Summary Types - Match backend schemas for /users/{userId}/summaries/* endpoints
// ============================================================================

export interface SleepStagesSummary {
  awake_minutes: number | null;
  light_minutes: number | null;
  deep_minutes: number | null;
  rem_minutes: number | null;
}

export interface SleepSummary {
  date: string;
  source: DataSource;
  start_time: string | null;
  end_time: string | null;
  duration_minutes: number | null;
  time_in_bed_minutes: number | null;
  efficiency_percent: number | null;
  stages: SleepStagesSummary | null;
  interruptions_count: number | null;
  nap_count: number | null;
  nap_duration_minutes: number | null;
  avg_heart_rate_bpm: number | null;
  avg_hrv_sdnn_ms: number | null;
  avg_respiratory_rate: number | null;
  avg_spo2_percent: number | null;
}

export interface BloodPressure {
  avg_systolic_mmhg: number | null;
  avg_diastolic_mmhg: number | null;
  max_systolic_mmhg: number | null;
  max_diastolic_mmhg: number | null;
  min_systolic_mmhg: number | null;
  min_diastolic_mmhg: number | null;
  reading_count: number | null;
}

export interface BodySummary {
  date: string;
  source: DataSource;
  // Static/demographic
  age: number | null;
  // Body composition (latest values)
  height_cm: number | null;
  weight_kg: number | null;
  body_fat_percent: number | null;
  muscle_mass_kg: number | null;
  bmi: number | null;
  // Vitals (7-day rolling averages)
  resting_heart_rate_bpm: number | null;
  avg_hrv_sdnn_ms: number | null;
  blood_pressure: BloodPressure | null;
  basal_body_temperature_celsius: number | null;
}

export interface RecoverySummary {
  date: string;
  source: DataSource;
  sleep_duration_seconds: number | null;
  sleep_efficiency_percent: number | null;
  resting_heart_rate_bpm: number | null;
  avg_hrv_sdnn_ms: number | null;
  avg_spo2_percent: number | null;
  recovery_score: number | null;
}

export interface DataSource {
  provider: string;
  device: string | null;
}

export interface HeartRateStats {
  avg_bpm: number | null;
  max_bpm: number | null;
  min_bpm: number | null;
}

export interface IntensityMinutes {
  light: number | null;
  moderate: number | null;
  vigorous: number | null;
}

export interface ActivitySummary {
  date: string;
  source: DataSource;
  // Step and movement metrics
  steps: number | null;
  distance_meters: number | null;
  // Elevation metrics
  floors_climbed: number | null;
  elevation_meters: number | null;
  // Energy metrics
  active_calories_kcal: number | null;
  total_calories_kcal: number | null;
  // Duration metrics
  active_minutes: number | null;
  sedentary_minutes: number | null;
  // Intensity metrics (based on HR zones)
  intensity_minutes: IntensityMinutes | null;
  // Heart rate aggregates
  heart_rate: HeartRateStats | null;
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

export interface EventRecordResponse {
  id: string;
  type: string;
  name?: string | null;
  start_time: string;
  end_time: string;
  duration_seconds?: number | null;
  source?: {
    provider: string;
    device?: string | null;
  };
  calories_kcal?: number | null;
  distance_meters?: number | null;

  // Legacy fields (keeping for compatibility if needed, but marked optional)
  user_id?: string;
  provider_id?: string | null;
  category?: string;
  source_name?: string;
  device_id?: string | null;
  start_datetime?: string;
  end_datetime?: string;
  heart_rate_min?: number | string | null;
  heart_rate_max?: number | string | null;
  heart_rate_avg?: number | string | null;
  steps_min?: number | string | null;
  steps_max?: number | string | null;
  steps_avg?: number | string | null;
  max_speed?: number | string | null;
  max_watts?: number | string | null;
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

export interface HealthDataParams {
  start_datetime?: string;
  end_datetime?: string;
  device_id?: string;
  limit?: number;
  offset?: number;
  [key: string]: string | number | undefined;
}

export interface Developer {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  created_at: string;
}

export interface Invitation {
  id: string;
  email: string;
  invited_by: string;
  created_at: string;
  expires_at: string;
  status: 'pending' | 'sent' | 'failed' | 'accepted' | 'expired' | 'revoked';
}

export interface InvitationCreate {
  email: string;
}

export interface InvitationAccept {
  token: string;
  first_name: string;
  last_name: string;
  password: string;
}

// Garmin Backfill Status (sequential: 5 data types × 30 days)
export interface GarminBackfillStatus {
  in_progress: boolean;
  days_completed: number;
  current_data_type_index: number;
  current_data_type: string; // "sleeps" | "dailies" | "epochs" | "bodyComps" | "hrv"
  current_end_date: string | null;
  target_days: number;
}

// Sync Response (returned by provider sync endpoint)
export interface SyncResponse {
  success: boolean;
  async: boolean;
  task_id: string;
  message: string;
  backfill_status?: GarminBackfillStatus;
}
