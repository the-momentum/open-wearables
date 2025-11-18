// Users API service

import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { UserRead, UserCreate, UserUpdate } from '../types';
import { mockUsers } from '../../../data/mock/users';

const USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true';

// In-memory mock store
let mockUsersStore = [...mockUsers];

// Mock users service
const mockUsersService = {
  async getAll(filters?: { search?: string }): Promise<UserRead[]> {
    await delay(500);

    let users = [...mockUsersStore];

    // Apply search filter
    if (filters?.search) {
      const searchLower = filters.search.toLowerCase();
      users = users.filter(
        (u) =>
          u.name?.toLowerCase().includes(searchLower) ||
          u.email?.toLowerCase().includes(searchLower)
      );
    }

    return users;
  },

  async getById(id: string): Promise<UserRead> {
    await delay(300);

    const user = mockUsersStore.find((u) => u.id === id);
    if (!user) {
      throw new Error('User not found');
    }

    return user;
  },

  async create(data: UserCreate): Promise<UserRead> {
    await delay(800);

    const newUser: UserRead = {
      ...data,
      id: 'user_' + Math.random().toString(36).substring(7),
      created_at: new Date().toISOString(),
      metadata: {
        ...data.metadata,
        connections: [],
        status: 'pending',
        dataPoints: 0,
      },
    };

    mockUsersStore.push(newUser);
    return newUser;
  },

  async update(id: string, data: UserUpdate): Promise<UserRead> {
    await delay(600);

    const index = mockUsersStore.findIndex((u) => u.id === id);
    if (index === -1) {
      throw new Error('User not found');
    }

    const updatedUser = {
      ...mockUsersStore[index],
      ...data,
      metadata: {
        ...mockUsersStore[index].metadata,
        ...data.metadata,
      },
    };

    mockUsersStore[index] = updatedUser;
    return updatedUser;
  },

  async delete(id: string): Promise<void> {
    await delay(400);

    const index = mockUsersStore.findIndex((u) => u.id === id);
    if (index === -1) {
      throw new Error('User not found');
    }

    mockUsersStore.splice(index, 1);
  },
};

// Real users service
const realUsersService = {
  async getAll(filters?: { search?: string }): Promise<UserRead[]> {
    const params = new URLSearchParams();
    if (filters?.search) params.append('search', filters.search);

    const endpoint = params.toString()
      ? `${API_ENDPOINTS.users}?${params}`
      : API_ENDPOINTS.users;

    return apiClient.get<UserRead[]>(endpoint);
  },

  async getById(id: string): Promise<UserRead> {
    return apiClient.get<UserRead>(API_ENDPOINTS.userDetail(id));
  },

  async create(data: UserCreate): Promise<UserRead> {
    return apiClient.post<UserRead>(API_ENDPOINTS.users, data);
  },

  async update(id: string, data: UserUpdate): Promise<UserRead> {
    return apiClient.patch<UserRead>(API_ENDPOINTS.userDetail(id), data);
  },

  async delete(id: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.userDetail(id));
  },
};

export const usersService = USE_MOCK ? mockUsersService : realUsersService;

// Utility function
function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
