import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type {
  Automation,
  AutomationCreate,
  AutomationUpdate,
  AutomationTrigger,
  TestAutomationResult,
} from '../types';

export const automationsService = {
  async getAutomations(): Promise<Automation[]> {
    return apiClient.get<Automation[]>(API_ENDPOINTS.automations);
  },

  async getAutomation(id: string): Promise<Automation> {
    return apiClient.get<Automation>(API_ENDPOINTS.automationDetail(id));
  },

  async createAutomation(data: AutomationCreate): Promise<Automation> {
    return apiClient.post<Automation>(API_ENDPOINTS.automations, data);
  },

  async updateAutomation(
    id: string,
    data: AutomationUpdate
  ): Promise<Automation> {
    return apiClient.patch<Automation>(
      API_ENDPOINTS.automationDetail(id),
      data
    );
  },

  async deleteAutomation(id: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.automationDetail(id));
  },

  async toggleAutomation(id: string, isEnabled: boolean): Promise<Automation> {
    return this.updateAutomation(id, { isEnabled });
  },

  async getAutomationTriggers(
    automationId: string
  ): Promise<AutomationTrigger[]> {
    return apiClient.get<AutomationTrigger[]>(
      `${API_ENDPOINTS.automationDetail(automationId)}/triggers`
    );
  },

  async testAutomation(automationId: string): Promise<TestAutomationResult> {
    return apiClient.post<TestAutomationResult>(
      API_ENDPOINTS.testAutomation(automationId),
      {}
    );
  },

  async improveDescription(
    description: string
  ): Promise<{ improvedDescription: string }> {
    return apiClient.post<{ improvedDescription: string }>(
      `${API_ENDPOINTS.automations}/improve-description`,
      { description }
    );
  },
};
