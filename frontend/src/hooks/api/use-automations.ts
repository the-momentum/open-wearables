import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { automationsService } from '@/lib/api/services/automations.service';
import type { AutomationCreate, AutomationUpdate } from '@/lib/api/types';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/errors/handler';

// Get all automations
export function useAutomations() {
  return useQuery({
    queryKey: queryKeys.automations.list(),
    queryFn: () => automationsService.getAutomations(),
  });
}

// Get single automation
export function useAutomation(id: string) {
  return useQuery({
    queryKey: queryKeys.automations.detail(id),
    queryFn: () => automationsService.getAutomation(id),
    enabled: !!id,
  });
}

// Get automation triggers
export function useAutomationTriggers(automationId: string) {
  return useQuery({
    queryKey: queryKeys.automations.triggers(automationId),
    queryFn: () => automationsService.getAutomationTriggers(automationId),
    enabled: !!automationId,
  });
}

// Create automation
export function useCreateAutomation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AutomationCreate) =>
      automationsService.createAutomation(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.automations.list() });
      toast.success('Automation created successfully');
    },
    onError: (error) => {
      toast.error(`Failed to create automation: ${getErrorMessage(error)}`);
    },
  });
}

// Update automation
export function useUpdateAutomation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AutomationUpdate }) =>
      automationsService.updateAutomation(id, data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.automations.list() });
      queryClient.invalidateQueries({
        queryKey: queryKeys.automations.detail(variables.id),
      });
      toast.success('Automation updated successfully');
    },
    onError: (error) => {
      toast.error(`Failed to update automation: ${getErrorMessage(error)}`);
    },
  });
}

// Delete automation
export function useDeleteAutomation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => automationsService.deleteAutomation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.automations.list() });
      toast.success('Automation deleted successfully');
    },
    onError: (error) => {
      toast.error(`Failed to delete automation: ${getErrorMessage(error)}`);
    },
  });
}

// Toggle automation
export function useToggleAutomation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, isEnabled }: { id: string; isEnabled: boolean }) =>
      automationsService.toggleAutomation(id, isEnabled),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.automations.list() });
      queryClient.invalidateQueries({
        queryKey: queryKeys.automations.detail(variables.id),
      });
      toast.success(
        variables.isEnabled ? 'Automation enabled' : 'Automation disabled'
      );
    },
    onError: (error) => {
      toast.error(`Failed to toggle automation: ${getErrorMessage(error)}`);
    },
  });
}

// Test automation
export function useTestAutomation() {
  return useMutation({
    mutationFn: (automationId: string) =>
      automationsService.testAutomation(automationId),
    onSuccess: () => {
      toast.success('Automation test completed');
    },
    onError: (error) => {
      toast.error(`Failed to test automation: ${getErrorMessage(error)}`);
    },
  });
}

// Improve description with AI
export function useImproveDescription() {
  return useMutation({
    mutationFn: (description: string) =>
      automationsService.improveDescription(description),
    onError: (error) => {
      toast.error(`Failed to improve description: ${getErrorMessage(error)}`);
    },
  });
}
