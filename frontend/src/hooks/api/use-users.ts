import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import { usersService } from '../../lib/api';
import { queryKeys } from '../../lib/query/keys';
import {
  BYTES_PER_GIBIBYTE,
  S3_UPLOAD_THRESHOLD,
  MAX_FILE_SIZE,
} from '@/lib/constants/upload';
import type {
  UserRead,
  UserCreate,
  UserUpdate,
  UserQueryParams,
} from '../../lib/api/types';

export function useUsers(params?: UserQueryParams) {
  return useQuery({
    queryKey: queryKeys.users.list(params),
    queryFn: () => usersService.getAll(params),
    placeholderData: (previousData) => previousData,
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
      // Invalidate dashboard stats - only refetches if dashboard is currently open
      queryClient.invalidateQueries({
        queryKey: queryKeys.dashboard.stats(),
        refetchType: 'active',
      });
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

      // Optimistically update (only apply non-null values to preserve required fields)
      if (previousUser) {
        const optimisticUpdate: UserRead = {
          ...previousUser,
          first_name:
            data.first_name !== undefined
              ? data.first_name
              : previousUser.first_name,
          last_name:
            data.last_name !== undefined
              ? data.last_name
              : previousUser.last_name,
          email: data.email !== undefined ? data.email : previousUser.email,
          external_user_id:
            data.external_user_id ?? previousUser.external_user_id,
        };
        queryClient.setQueryData<UserRead>(
          queryKeys.users.detail(id),
          optimisticUpdate
        );
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.lists() });
      // Invalidate dashboard stats - only refetches if dashboard is currently open
      queryClient.invalidateQueries({
        queryKey: queryKeys.dashboard.stats(),
        refetchType: 'active',
      });
      toast.success('User deleted successfully');
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Failed to delete user';
      toast.error(message);
    },
  });
}

export function useGenerateInvitationCode() {
  return useMutation({
    mutationFn: (userId: string) => usersService.generateInvitationCode(userId),
    onSuccess: () => {
      toast.success('Invitation code generated successfully');
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to generate invitation code';
      toast.error(message);
    },
  });
}

export function useUploadAppleXml() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      userId,
      file,
      onProgress,
    }: {
      userId: string;
      file: File;
      onProgress?: (percent: number) => void;
    }) => usersService.uploadAppleXml(userId, file, onProgress),
    onSuccess: (_data, { userId }) => {
      // Invalidate user data to show new imported data
      queryClient.invalidateQueries({
        queryKey: queryKeys.users.detail(userId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.all,
        refetchType: 'active',
      });
      toast.success('XML file uploaded successfully');
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error ? error.message : 'Failed to upload XML file';
      toast.error(message);
    },
  });
}

export function useUploadAppleXmlViaS3() {
  return useMutation({
    mutationFn: ({
      userId,
      file,
      onProgress,
    }: {
      userId: string;
      file: File;
      onProgress?: (percent: number) => void;
    }) =>
      // Multipart upload straight to object storage (S3 or MinIO). Parts are PUT
      // via presigned URLs; the backend finalizes the object and starts processing.
      usersService.uploadAppleXmlViaMultipart(userId, file, onProgress),
    onSuccess: (data) => {
      const taskSuffix = data.task_id
        ? ` Task ${data.task_id.slice(0, 8)}… is processing it.`
        : ' Processing will begin from the configured storage notification.';
      toast.success(`XML file uploaded to object storage.${taskSuffix}`);
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to upload XML file to object storage';
      toast.error(message);
    },
  });
}

interface UseAppleXmlUploadOptions {
  onSuccess?: (userId: string) => void;
  onError?: (error: Error) => void;
}

export type UploadPhase = 'idle' | 'uploading' | 'success' | 'error';

export interface UploadProgressState {
  phase: UploadPhase;
  /** 0-100 during upload; 100 on success. */
  percent: number;
  fileName: string | null;
  fileSize: number | null;
  errorMessage: string | null;
}

const IDLE_PROGRESS: UploadProgressState = {
  phase: 'idle',
  percent: 0,
  fileName: null,
  fileSize: null,
  errorMessage: null,
};

/**
 * Custom hook for handling Apple Health XML file uploads
 * Automatically selects between direct upload and S3 based on file size
 * Includes file type and size validation, and exposes live upload progress
 * for a progress dialog.
 */
export function useAppleXmlUpload(options: UseAppleXmlUploadOptions = {}) {
  const [uploadingUserId, setUploadingUserId] = useState<string | null>(null);
  const [progress, setProgress] = useState<UploadProgressState>(IDLE_PROGRESS);

  const { mutate: uploadDirect } = useUploadAppleXml();
  const { mutate: uploadViaS3 } = useUploadAppleXmlViaS3();

  const resetProgress = () => setProgress(IDLE_PROGRESS);

  const handleUpload = (
    userId: string,
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Reset the input so the same file can be uploaded again
    event.target.value = '';

    // Validate file type
    const isValidExtension = file.name.toLowerCase().endsWith('.xml');
    const isValidMimeType =
      file.type === 'text/xml' || file.type === 'application/xml';

    if (!isValidExtension && !isValidMimeType) {
      toast.error('Invalid file type. Please upload an XML file (.xml)');
      if (options.onError) {
        options.onError(new Error('Invalid file type'));
      }
      return;
    }

    // Validate file size
    if (file.size > MAX_FILE_SIZE) {
      const maxSizeGB = (MAX_FILE_SIZE / BYTES_PER_GIBIBYTE).toFixed(0);
      const fileSizeGB = (file.size / BYTES_PER_GIBIBYTE).toFixed(2);
      toast.error(
        `File is too large (${fileSizeGB}GB). Maximum size is ${maxSizeGB}GB`
      );
      if (options.onError) {
        options.onError(new Error('File size exceeds maximum limit'));
      }
      return;
    }

    setUploadingUserId(userId);
    setProgress({
      phase: 'uploading',
      percent: 0,
      fileName: file.name,
      fileSize: file.size,
      errorMessage: null,
    });

    const onProgress = (percent: number) =>
      setProgress((prev) => ({ ...prev, percent }));

    // Choose upload method based on file size
    const uploadMutation =
      file.size > S3_UPLOAD_THRESHOLD ? uploadViaS3 : uploadDirect;

    uploadMutation(
      { userId, file, onProgress },
      {
        onSuccess: () => {
          setProgress((prev) => ({ ...prev, phase: 'success', percent: 100 }));
          if (options.onSuccess) {
            options.onSuccess(userId);
          }
        },
        onError: (error) => {
          setProgress((prev) => ({
            ...prev,
            phase: 'error',
            errorMessage: (error as Error).message,
          }));
          if (options.onError) {
            options.onError(error as Error);
          }
        },
        onSettled: () => {
          setUploadingUserId(null);
        },
      }
    );
  };

  return {
    handleUpload,
    uploadingUserId,
    isUploading: (userId: string) => uploadingUserId === userId,
    progress,
    resetProgress,
  };
}
