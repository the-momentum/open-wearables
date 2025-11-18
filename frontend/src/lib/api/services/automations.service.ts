import { apiClient } from '../client';
import type {
  Automation,
  AutomationCreate,
  AutomationUpdate,
  AutomationTrigger,
  TestAutomationResult,
} from '../types';
import {
  mockAutomations,
  mockAutomationTriggers,
} from '@/data/mock/automations';

const USE_MOCK = import.meta.env.VITE_USE_MOCK_API === 'true';

// Helper to simulate API delay
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export const automationsService = {
  // List all automations
  async getAutomations(): Promise<Automation[]> {
    if (USE_MOCK) {
      await delay(300);
      return mockAutomations;
    }
    return await apiClient.get<Automation[]>('/v1/automations');
  },

  // Get single automation
  async getAutomation(id: string): Promise<Automation> {
    if (USE_MOCK) {
      await delay(200);
      const automation = mockAutomations.find((a) => a.id === id);
      if (!automation) {
        throw new Error(`Automation ${id} not found`);
      }
      return automation;
    }
    return await apiClient.get<Automation>(`/v1/automations/${id}`);
  },

  // Create automation
  async createAutomation(data: AutomationCreate): Promise<Automation> {
    if (USE_MOCK) {
      await delay(500);
      const newAutomation: Automation = {
        id: `auto-${Date.now()}`,
        name: data.name,
        description: data.description,
        webhookUrl: data.webhookUrl,
        isEnabled: data.isEnabled ?? true,
        triggerCount: 0,
        lastTriggered: null,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      mockAutomations.push(newAutomation);
      return newAutomation;
    }
    return await apiClient.post<Automation>('/v1/automations', data);
  },

  // Update automation
  async updateAutomation(
    id: string,
    data: AutomationUpdate
  ): Promise<Automation> {
    if (USE_MOCK) {
      await delay(400);
      const automation = mockAutomations.find((a) => a.id === id);
      if (!automation) {
        throw new Error(`Automation ${id} not found`);
      }
      Object.assign(automation, {
        ...data,
        updatedAt: new Date().toISOString(),
      });
      return automation;
    }
    return await apiClient.patch<Automation>(`/v1/automations/${id}`, data);
  },

  // Delete automation
  async deleteAutomation(id: string): Promise<void> {
    if (USE_MOCK) {
      await delay(300);
      const index = mockAutomations.findIndex((a) => a.id === id);
      if (index === -1) {
        throw new Error(`Automation ${id} not found`);
      }
      mockAutomations.splice(index, 1);
      return;
    }
    await apiClient.delete(`/v1/automations/${id}`);
  },

  // Toggle automation enabled state
  async toggleAutomation(id: string, isEnabled: boolean): Promise<Automation> {
    return this.updateAutomation(id, { isEnabled });
  },

  // Get automation triggers/history
  async getAutomationTriggers(
    automationId: string
  ): Promise<AutomationTrigger[]> {
    if (USE_MOCK) {
      await delay(300);
      return mockAutomationTriggers[automationId] || [];
    }
    return await apiClient.get<AutomationTrigger[]>(
      `/v1/automations/${automationId}/triggers`
    );
  },

  // Test automation against historical data
  async testAutomation(automationId: string): Promise<TestAutomationResult> {
    if (USE_MOCK) {
      await delay(1500); // Simulate processing time
      const triggers = mockAutomationTriggers[automationId] || [];
      return {
        automationId,
        totalTriggers: triggers.length,
        dateRange: {
          start: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
          end: new Date().toISOString(),
        },
        executionTime: 1.23,
        instances: triggers,
      };
    }
    return await apiClient.post<TestAutomationResult>(
      `/v1/automations/${automationId}/test`,
      {}
    );
  },

  // Improve automation description with AI
  async improveDescription(
    description: string
  ): Promise<{ improvedDescription: string }> {
    if (USE_MOCK) {
      await delay(800);
      // Simple mock improvement
      return {
        improvedDescription: `Enhanced: ${description} - This automation uses advanced health metrics analysis to identify patterns and trigger webhooks when specific thresholds are met, ensuring timely notifications for critical health events.`,
      };
    }
    return await apiClient.post<{ improvedDescription: string }>(
      '/v1/automations/improve-description',
      { description }
    );
  },
};
