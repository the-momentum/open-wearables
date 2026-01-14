/**
 * File upload configuration constants
 * These match the backend limits defined in backend/app/schemas/apple/apple_xml/aws.py
 */

/**
 * File size threshold for choosing upload method
 * Files larger than this will use S3 presigned URLs
 * Files smaller will use direct upload through backend
 */
export const S3_UPLOAD_THRESHOLD = 10 * 1024 * 1024; // 10MB

/**
 * Maximum file size allowed for uploads
 * Matches backend MAX_FILE_SIZE limit
 */
export const MAX_FILE_SIZE = 1024 * 1024 * 1024; // 1GB
