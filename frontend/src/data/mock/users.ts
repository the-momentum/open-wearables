// Mock user data

import type { UserRead } from '../../lib/api/types';

export const mockUsers: UserRead[] = [
  {
    id: '550e8400-e29b-41d4-a716-446655440000',
    email: 'john.doe@example.com',
    name: 'John Doe',
    created_at: '2024-10-15T10:30:00Z',
    metadata: {
      connections: ['fitbit', 'strava'],
      status: 'active',
      lastSync: '2024-11-17T08:00:00Z',
      dataPoints: 12400,
    },
  },
  {
    id: '550e8400-e29b-41d4-a716-446655440001',
    email: 'jane.smith@example.com',
    name: 'Jane Smith',
    created_at: '2024-10-20T14:15:00Z',
    metadata: {
      connections: ['garmin', 'oura'],
      status: 'active',
      lastSync: '2024-11-17T09:30:00Z',
      dataPoints: 8920,
    },
  },
  {
    id: '550e8400-e29b-41d4-a716-446655440002',
    email: 'mike.wilson@example.com',
    name: 'Mike Wilson',
    created_at: '2024-11-01T09:00:00Z',
    metadata: {
      connections: ['whoop'],
      status: 'error',
      lastSync: '2024-11-15T12:00:00Z',
      dataPoints: 3200,
    },
  },
  {
    id: '550e8400-e29b-41d4-a716-446655440003',
    email: 'sarah.johnson@example.com',
    name: 'Sarah Johnson',
    created_at: '2024-11-05T11:45:00Z',
    metadata: {
      connections: ['apple', 'strava'],
      status: 'active',
      lastSync: '2024-11-17T07:15:00Z',
      dataPoints: 15600,
    },
  },
  {
    id: '550e8400-e29b-41d4-a716-446655440004',
    email: 'alex.brown@example.com',
    name: 'Alex Brown',
    created_at: '2024-11-12T16:20:00Z',
    metadata: {
      connections: [],
      status: 'pending',
      lastSync: null,
      dataPoints: 0,
    },
  },
];
