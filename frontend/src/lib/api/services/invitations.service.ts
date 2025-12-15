import { apiClient } from '../client';
import { API_ENDPOINTS } from '../config';
import type { Invitation, InvitationCreate, InvitationAccept } from '../types';

export const invitationsService = {
  async getInvitations(): Promise<Invitation[]> {
    return apiClient.get<Invitation[]>(API_ENDPOINTS.invitations);
  },

  async createInvitation(data: InvitationCreate): Promise<Invitation> {
    return apiClient.post<Invitation>(API_ENDPOINTS.invitations, data);
  },

  async revokeInvitation(id: string): Promise<void> {
    return apiClient.delete<void>(API_ENDPOINTS.invitationDetail(id));
  },

  async resendInvitation(id: string): Promise<Invitation> {
    return apiClient.post<Invitation>(API_ENDPOINTS.invitationResend(id));
  },

  async acceptInvitation(data: InvitationAccept): Promise<{ message: string }> {
    return apiClient.post<{ message: string }>(
      API_ENDPOINTS.acceptInvitation,
      data
    );
  },
};
