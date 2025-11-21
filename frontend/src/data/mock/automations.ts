import type { Automation, AutomationTrigger } from '@/lib/api/types';

export const mockAutomations: Automation[] = [
  {
    id: 'auto-1',
    name: 'High Heart Rate Alert',
    description:
      'Trigger webhook when user heart rate exceeds 120 bpm during rest',
    webhookUrl: 'https://api.example.com/webhooks/high-heart-rate',
    isEnabled: true,
    triggerCount: 45,
    lastTriggered: '2025-11-17T14:32:00Z',
    createdAt: '2025-11-01T10:00:00Z',
    updatedAt: '2025-11-17T14:32:00Z',
  },
  {
    id: 'auto-2',
    name: 'Poor Sleep Quality',
    description:
      'Notify when sleep efficiency drops below 70% for 3 consecutive nights',
    webhookUrl: 'https://api.example.com/webhooks/poor-sleep',
    isEnabled: true,
    triggerCount: 12,
    lastTriggered: '2025-11-16T08:15:00Z',
    createdAt: '2025-11-02T11:30:00Z',
    updatedAt: '2025-11-16T08:15:00Z',
  },
  {
    id: 'auto-3',
    name: 'Low Activity Warning',
    description:
      'Alert when daily steps fall below 5000 for 2 consecutive days',
    webhookUrl: 'https://api.example.com/webhooks/low-activity',
    isEnabled: false,
    triggerCount: 8,
    lastTriggered: '2025-11-10T19:45:00Z',
    createdAt: '2025-11-03T09:15:00Z',
    updatedAt: '2025-11-15T16:20:00Z',
  },
  {
    id: 'auto-4',
    name: 'Unusual Activity Spike',
    description: 'Detect when active minutes exceed 200% of user average',
    webhookUrl: 'https://api.example.com/webhooks/activity-spike',
    isEnabled: true,
    triggerCount: 3,
    lastTriggered: '2025-11-15T11:22:00Z',
    createdAt: '2025-11-05T14:00:00Z',
    updatedAt: '2025-11-15T11:22:00Z',
  },
  {
    id: 'auto-5',
    name: 'Stress Level Monitor',
    description: 'Trigger when stress score exceeds 75 for more than 2 hours',
    webhookUrl: 'https://api.example.com/webhooks/stress-alert',
    isEnabled: true,
    triggerCount: 27,
    lastTriggered: '2025-11-17T16:05:00Z',
    createdAt: '2025-11-07T13:45:00Z',
    updatedAt: '2025-11-17T16:05:00Z',
  },
];

export const mockAutomationTriggers: Record<string, AutomationTrigger[]> = {
  'auto-1': [
    {
      id: 'trigger-1',
      automationId: 'auto-1',
      userId: 'user-1',
      userName: 'John Doe',
      userEmail: 'john.doe@example.com',
      triggeredAt: '2025-11-17T14:32:00Z',
      data: {
        heartRate: 125,
        timestamp: '2025-11-17T14:30:00Z',
        context: 'resting',
      },
      webhookStatus: 'success',
      webhookResponse: { statusCode: 200 },
    },
    {
      id: 'trigger-2',
      automationId: 'auto-1',
      userId: 'user-2',
      userName: 'Jane Smith',
      userEmail: 'jane.smith@example.com',
      triggeredAt: '2025-11-17T10:15:00Z',
      data: {
        heartRate: 132,
        timestamp: '2025-11-17T10:13:00Z',
        context: 'resting',
      },
      webhookStatus: 'success',
      webhookResponse: { statusCode: 200 },
    },
    {
      id: 'trigger-3',
      automationId: 'auto-1',
      userId: 'user-3',
      userName: 'Bob Johnson',
      userEmail: 'bob.johnson@example.com',
      triggeredAt: '2025-11-16T22:45:00Z',
      data: {
        heartRate: 128,
        timestamp: '2025-11-16T22:43:00Z',
        context: 'resting',
      },
      webhookStatus: 'failed',
      webhookResponse: { statusCode: 500, error: 'Internal server error' },
    },
  ],
  'auto-2': [
    {
      id: 'trigger-4',
      automationId: 'auto-2',
      userId: 'user-4',
      userName: 'Alice Williams',
      userEmail: 'alice.williams@example.com',
      triggeredAt: '2025-11-16T08:15:00Z',
      data: {
        sleepEfficiency: 62,
        consecutiveNights: 3,
        dates: ['2025-11-14', '2025-11-15', '2025-11-16'],
      },
      webhookStatus: 'success',
      webhookResponse: { statusCode: 200 },
    },
  ],
};
