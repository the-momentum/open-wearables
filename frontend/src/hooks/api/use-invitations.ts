import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { invitationsService } from '@/lib/api/services/invitations.service';
import type {
  Invitation,
  InvitationCreate,
  InvitationAccept,
} from '@/lib/api/types';
import { queryKeys } from '@/lib/query/keys';
import { toast } from 'sonner';
import { getErrorMessage } from '@/lib/errors/handler';

export function useInvitations() {
  return useQuery({
    queryKey: queryKeys.invitations.list(),
    queryFn: () => invitationsService.getInvitations(),
  });
}

export function useCreateInvitation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: InvitationCreate) =>
      invitationsService.createInvitation(data),
    onSuccess: (createdInvitation) => {
      // Optimistically set status to 'sent' since email sending usually succeeds
      // On page refresh, the real status will be fetched (sent or failed)
      queryClient.setQueryData(
        queryKeys.invitations.list(),
        (old: Invitation[] = []) => [
          ...old,
          { ...createdInvitation, status: 'sent' },
        ]
      );
      toast.success('Invitation sent successfully');
    },
    onError: (error) => {
      toast.error(`Failed to send invitation: ${getErrorMessage(error)}`);
    },
  });
}

export function useRevokeInvitation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => invitationsService.revokeInvitation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.invitations.list() });
      toast.success('Invitation revoked successfully');
    },
    onError: (error) => {
      toast.error(`Failed to revoke invitation: ${getErrorMessage(error)}`);
    },
  });
}

export function useResendInvitation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => invitationsService.resendInvitation(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.invitations.list() });
      toast.success('Invitation resent successfully');
    },
    onError: (error) => {
      toast.error(`Failed to resend invitation: ${getErrorMessage(error)}`);
    },
  });
}

export function useAcceptInvitation() {
  return useMutation({
    mutationFn: (data: InvitationAccept) =>
      invitationsService.acceptInvitation(data),
    onSuccess: () => {
      toast.success('Invitation accepted successfully');
    },
    onError: (error) => {
      toast.error(`Failed to accept invitation: ${getErrorMessage(error)}`);
    },
  });
}
