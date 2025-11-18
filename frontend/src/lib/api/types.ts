// Common API types and interfaces

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

// User types
export interface UserRead {
  id: string;
  email?: string;
  name?: string;
  created_at: string;
  metadata?: Record<string, unknown>;
}

export interface UserCreate {
  email?: string;
  name?: string;
  metadata?: Record<string, unknown>;
}

export interface UserUpdate {
  email?: string;
  name?: string;
  metadata?: Record<string, unknown>;
}

// Auth types
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

// Dashboard types
export interface DashboardStats {
  totalUsers: number;
  activeConnections: number;
  dataPoints: number;
  apiCalls: number;
}

// Provider types
export interface Provider {
  id: string;
  name: string;
  description: string;
  logoUrl: string;
  isAvailable: boolean;
  features: string[];
  authType: 'oauth2' | 'api_key';
}

// Connection types
export type WearableProvider =
  | 'fitbit'
  | 'garmin'
  | 'oura'
  | 'whoop'
  | 'strava'
  | 'apple'
  | 'apple-health'
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

// Health data types
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

// Legacy types for backward compatibility
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

// API Key types
export interface ApiKey {
  id: string;
  name: string;
  key: string;
  type: 'live' | 'test' | 'widget';
  status: 'active' | 'revoked';
  lastUsed: string | null;
  createdAt: string;
  expiresAt: string | null;
}

export interface ApiKeyRead {
  id: string;
  name: string;
  key: string;
  type: 'developer' | 'widget';
  status: 'active' | 'revoked';
  lastUsed?: string;
  createdAt: string;
}

export interface ApiKeyCreate {
  name: string;
  type: 'live' | 'test' | 'widget';
}

// Automation types
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

// Request log types
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

// Chart data types
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

// Chat types
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
