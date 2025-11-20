export const queryKeys = {
  auth: {
    all: ['auth'] as const,
    session: () => [...queryKeys.auth.all, 'session'] as const,
  },

  users: {
    all: ['users'] as const,
    lists: () => [...queryKeys.users.all, 'list'] as const,
    list: (filters?: { search?: string; status?: string }) =>
      [...queryKeys.users.lists(), filters] as const,
    details: () => [...queryKeys.users.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.users.details(), id] as const,
  },

  dashboard: {
    all: ['dashboard'] as const,
    stats: () => [...queryKeys.dashboard.all, 'stats'] as const,
    charts: (timeRange?: string) =>
      [...queryKeys.dashboard.all, 'charts', timeRange] as const,
  },

  apiKeys: {
    all: ['apiKeys'] as const,
    lists: () => [...queryKeys.apiKeys.all, 'list'] as const,
    list: (filters?: { type?: string }) =>
      [...queryKeys.apiKeys.lists(), filters] as const,
    details: () => [...queryKeys.apiKeys.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.apiKeys.details(), id] as const,
  },

  credentials: {
    all: ['credentials'] as const,
    lists: () => [...queryKeys.credentials.all, 'list'] as const,
    list: () => [...queryKeys.credentials.lists()] as const,
    details: () => [...queryKeys.credentials.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.credentials.details(), id] as const,
  },

  automations: {
    all: ['automations'] as const,
    lists: () => [...queryKeys.automations.all, 'list'] as const,
    list: (filters?: { status?: string; search?: string }) =>
      filters
        ? ([...queryKeys.automations.lists(), filters] as const)
        : queryKeys.automations.lists(),
    details: () => [...queryKeys.automations.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.automations.details(), id] as const,
    triggers: (id: string) =>
      [...queryKeys.automations.detail(id), 'triggers'] as const,
    test: (id: string) =>
      [...queryKeys.automations.detail(id), 'test'] as const,
  },

  healthData: {
    all: (userId: string) => ['healthData', userId] as const,
    heartRate: (userId: string, dateRange?: { start: string; end: string }) =>
      [...queryKeys.healthData.all(userId), 'heartRate', dateRange] as const,
    sleep: (userId: string, dateRange?: { start: string; end: string }) =>
      [...queryKeys.healthData.all(userId), 'sleep', dateRange] as const,
    activity: (userId: string, dateRange?: { start: string; end: string }) =>
      [...queryKeys.healthData.all(userId), 'activity', dateRange] as const,
  },

  health: {
    all: ['health'] as const,
    providers: () => [...queryKeys.health.all, 'providers'] as const,
    connections: (userId: string) =>
      [...queryKeys.health.all, 'connections', userId] as const,
    heartRate: (userId: string, days: number) =>
      [...queryKeys.health.all, 'heartRate', userId, days] as const,
    sleep: (userId: string, days: number) =>
      [...queryKeys.health.all, 'sleep', userId, days] as const,
    activity: (userId: string, days: number) =>
      [...queryKeys.health.all, 'activity', userId, days] as const,
    summary: (userId: string, period?: string) =>
      [...queryKeys.health.all, 'summary', userId, period] as const,
  },

  connections: {
    all: (userId: string) => ['connections', userId] as const,
    status: (userId: string) =>
      [...queryKeys.connections.all(userId), 'status'] as const,
  },

  requestLogs: {
    all: ['requestLogs'] as const,
    lists: () => [...queryKeys.requestLogs.all, 'list'] as const,
    list: (filters?: {
      status?: number;
      method?: string;
      search?: string;
      dateRange?: { start: string; end: string };
    }) => [...queryKeys.requestLogs.lists(), filters] as const,
  },

  chat: {
    all: (userId?: string) => ['chat', userId] as const,
    history: (userId?: string) =>
      [...queryKeys.chat.all(userId), 'history'] as const,
  },
} as const;
