import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { usersService } from '../../lib/api';
import { queryKeys } from '../../lib/query/keys';
import type { UserRead, UserCreate, UserUpdate } from '../../lib/api/types';

export function useUsers(filters?: { search?: string }) {
  return useQuery({
    queryKey: queryKeys.users.list(filters),
    queryFn: () => usersService.getAll(filters),
  });
}

export function useUser(id: string) {
  return useQuery({
    queryKey: queryKeys.users.detail(id),
    queryFn: () => usersService.getById(id),
    enabled: !!id,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UserCreate) => usersService.create(data),
    onSuccess: () => {
      // Invalidate users list
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
      toast.success('User created successfully');
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Failed to create user';
      toast.error(message);
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: UserUpdate }) =>
      usersService.update(id, data),
    onMutate: async ({ id, data }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.users.detail(id) });

      // Snapshot previous value
      const previousUser = queryClient.getQueryData<UserRead>(
        queryKeys.users.detail(id)
      );

      // Optimistically update
      if (previousUser) {
        queryClient.setQueryData<UserRead>(queryKeys.users.detail(id), {
          ...previousUser,
          ...data,
        });
      }

      return { previousUser };
    },
    onSuccess: (updatedUser, { id }) => {
      // Update cache with server response
      queryClient.setQueryData(queryKeys.users.detail(id), updatedUser);
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
      toast.success('User updated successfully');
    },
    onError: (error: unknown, { id }, context) => {
      // Rollback on error
      if (context?.previousUser) {
        queryClient.setQueryData(
          queryKeys.users.detail(id),
          context.previousUser
        );
      }
      const message =
        error instanceof Error ? error.message : 'Failed to update user';
      toast.error(message);
    },
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => usersService.delete(id),
    onMutate: async (id) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: queryKeys.users.lists() });

      // Snapshot previous value
      const previousUsers = queryClient.getQueryData<UserRead[]>(
        queryKeys.users.lists()
      );

      // Optimistically remove from cache
      if (previousUsers) {
        queryClient.setQueryData<UserRead[]>(
          queryKeys.users.lists(),
          previousUsers.filter((u) => u.id !== id)
        );
      }

      return { previousUsers };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
      toast.success('User deleted successfully');
    },
    onError: (error: unknown, _id, context) => {
      // Rollback on error
      if (context?.previousUsers) {
        queryClient.setQueryData(
          queryKeys.users.lists(),
          context.previousUsers
        );
      }
      const message =
        error instanceof Error ? error.message : 'Failed to delete user';
      toast.error(message);
    },
  });
}
