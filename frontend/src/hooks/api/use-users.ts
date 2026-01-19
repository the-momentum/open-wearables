import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { toast } from 'sonner';
import { usersService } from '../../lib/api';
import { queryKeys } from '../../lib/query/keys';
import { S3_UPLOAD_THRESHOLD, MAX_FILE_SIZE } from '@/lib/constants/upload';
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

export function useGenerateUserToken() {
  return useMutation({
    mutationFn: (userId: string) => usersService.generateToken(userId),
    onSuccess: () => {
      toast.success('User token generated successfully');
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to generate user token';
      toast.error(message);
    },
  });
}

export function useUploadAppleXml() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ userId, file }: { userId: string; file: File }) =>
      usersService.uploadAppleXml(userId, file),
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
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ userId, file }: { userId: string; file: File }) => {
      // Step 1: Get presigned URL from backend
      const presignedData = await usersService.getAppleXmlPresignedUrl(userId, {
        filename: file.name,
        max_file_size: file.size,
      });

      // Step 2: Upload directly to S3
      await usersService.uploadToS3(
        presignedData.upload_url,
        presignedData.form_fields,
        file
      );

      return presignedData;
    },
    onSuccess: (_data, { userId }) => {
      // Invalidate user data (processing will happen asynchronously via SQS)
      queryClient.invalidateQueries({
        queryKey: queryKeys.users.detail(userId),
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.health.all,
        refetchType: 'active',
      });
      toast.success(
        'XML file uploaded to S3 successfully. Processing will begin shortly.'
      );
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to upload XML file to S3';
      toast.error(message);
    },
  });
}

interface UseAppleXmlUploadOptions {
  onSuccess?: (userId: string) => void;
  onError?: (error: Error) => void;
}

/**
 * Custom hook for handling Apple Health XML file uploads
 * Automatically selects between direct upload and S3 based on file size
 * Includes file type and size validation
 */
export function useAppleXmlUpload(options: UseAppleXmlUploadOptions = {}) {
  const [uploadingUserId, setUploadingUserId] = useState<string | null>(null);

  const { mutate: uploadDirect } = useUploadAppleXml();
  const { mutate: uploadViaS3 } = useUploadAppleXmlViaS3();

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
      const maxSizeGB = (MAX_FILE_SIZE / (1024 * 1024 * 1024)).toFixed(0);
      const fileSizeGB = (file.size / (1024 * 1024 * 1024)).toFixed(2);
      toast.error(
        `File is too large (${fileSizeGB}GB). Maximum size is ${maxSizeGB}GB`
      );
      if (options.onError) {
        options.onError(new Error('File size exceeds maximum limit'));
      }
      return;
    }

    setUploadingUserId(userId);

    // Choose upload method based on file size
    const uploadMutation =
      file.size > S3_UPLOAD_THRESHOLD ? uploadViaS3 : uploadDirect;

    uploadMutation(
      { userId, file },
      {
        onSuccess: () => {
          if (options.onSuccess) {
            options.onSuccess(userId);
          }
        },
        onError: (error) => {
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
  };
}
