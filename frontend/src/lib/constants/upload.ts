/**
 * File upload configuration constants
 * These match the backend limits defined in backend/app/schemas/providers/apple/apple_xml/aws.py
 */

/**
 * File size threshold for choosing upload method
 * Files larger than this will use S3 presigned URLs
 * Files smaller will use direct upload through backend
 */
export const S3_UPLOAD_THRESHOLD = 10 * 1024 * 1024; // 10MB

export const BYTES_PER_GIBIBYTE = 1024 * 1024 * 1024;

/**
 * Upper bound for a direct upload or an individual multipart PUT.
 * The XHR helpers also accept an override for slower deployments.
 */
export const UPLOAD_REQUEST_TIMEOUT_MS = 30 * 60 * 1000;

/**
 * Maximum file size allowed for uploads
 * Matches backend MAX_FILE_SIZE limit
 */
export const MAX_FILE_SIZE = 5 * BYTES_PER_GIBIBYTE; // 5 GiB product limit
