import type { ApiErrorResponse } from '@/lib/api/types';
import { ApiError } from './api-error';

export function getErrorMessage(error: unknown): string {
  // Handle ApiError instances
  if (error instanceof ApiError) {
    return error.getUserFriendlyMessage();
  }

  // Handle standard Error instances
  if (error instanceof Error) {
    return error.message;
  }

  // Handle API error responses
  if (typeof error === 'object' && error !== null && 'message' in error) {
    return (error as ApiErrorResponse).message;
  }

  // Fallback for unknown errors
  return 'An unexpected error occurred';
}

export function getErrorCode(error: unknown): string | undefined {
  if (error instanceof ApiError) {
    return error.code;
  }

  if (typeof error === 'object' && error !== null && 'code' in error) {
    return (error as ApiErrorResponse).code;
  }

  return undefined;
}

export function getErrorDetails(
  error: unknown
): Record<string, unknown> | undefined {
  if (error instanceof ApiError) {
    return error.details;
  }

  if (typeof error === 'object' && error !== null && 'details' in error) {
    return (error as ApiErrorResponse).details;
  }

  return undefined;
}
