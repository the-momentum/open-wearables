import { useState } from 'react';
import { toast } from 'sonner';
import { useUploadAppleXml, useUploadAppleXmlViaS3 } from './use-users';
import { S3_UPLOAD_THRESHOLD, MAX_FILE_SIZE } from '@/lib/constants/upload';

interface UseAppleXmlUploadOptions {
  onSuccess?: (userId: string) => void;
  onError?: (error: Error) => void;
}

/**
 * Custom hook for handling Apple Health XML file uploads
 * Automatically selects between direct upload and S3 based on file size
 * Includes file size validation
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
