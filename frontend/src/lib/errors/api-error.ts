export type ApiErrorCode =
  | 'UNAUTHORIZED'
  | 'FORBIDDEN'
  | 'NOT_FOUND'
  | 'VALIDATION_ERROR'
  | 'RATE_LIMITED'
  | 'SERVER_ERROR'
  | 'NETWORK_ERROR'
  | 'TIMEOUT'
  | 'UNKNOWN';

export interface ApiValidationError {
  field: string;
  message: string;
  type: string;
}

export class ApiError extends Error {
  code: ApiErrorCode;
  statusCode: number;
  /** Machine-readable code from the backend, e.g. USER_NOT_FOUND. */
  serverCode?: string;
  validationErrors?: ApiValidationError[];
  details?: Record<string, unknown>;

  constructor(
    message: string,
    statusCode: number = 500,
    code?: ApiErrorCode,
    details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'ApiError';
    this.statusCode = statusCode;
    this.code = code || this.mapStatusCodeToErrorCode(statusCode);
    this.details = details;
  }

  private mapStatusCodeToErrorCode(statusCode: number): ApiErrorCode {
    if (statusCode === 401) return 'UNAUTHORIZED';
    if (statusCode === 403) return 'FORBIDDEN';
    if (statusCode === 404) return 'NOT_FOUND';
    if (statusCode === 422) return 'VALIDATION_ERROR';
    if (statusCode === 429) return 'RATE_LIMITED';
    if (statusCode >= 500) return 'SERVER_ERROR';
    return 'UNKNOWN';
  }

  static fromResponse(response: Response, data?: unknown): ApiError {
    // Backend errors are RFC 9457 problem json: {title, status, detail, code}
    // plus an `errors` list on 422 validation failures.
    const problem = (
      typeof data === 'object' && data !== null ? data : {}
    ) as Record<string, unknown>;
    const message =
      (problem.detail as string) ||
      (problem.title as string) ||
      response.statusText ||
      'An error occurred';

    const error = new ApiError(message, response.status);
    if (typeof problem.code === 'string') {
      error.serverCode = problem.code;
    }
    if (Array.isArray(problem.errors)) {
      error.validationErrors = problem.errors as ApiValidationError[];
    }
    return error;
  }

  static networkError(message: string = 'Network error occurred'): ApiError {
    return new ApiError(message, 0, 'NETWORK_ERROR');
  }

  static timeout(message: string = 'Request timeout'): ApiError {
    return new ApiError(message, 0, 'TIMEOUT');
  }

  getUserFriendlyMessage(): string {
    switch (this.code) {
      case 'UNAUTHORIZED':
        return 'You are not authorized. Please log in again.';
      case 'FORBIDDEN':
        return 'You do not have permission to perform this action.';
      case 'NOT_FOUND':
        return 'The requested resource was not found.';
      case 'VALIDATION_ERROR': {
        const fieldErrors = this.validationErrors
          ?.map((item) => `${item.field}: ${item.message}`)
          .join('; ');
        return (
          fieldErrors ||
          this.message ||
          'Please check your input and try again.'
        );
      }
      case 'RATE_LIMITED':
        return 'Too many requests. Please wait a moment and try again.';
      case 'SERVER_ERROR':
        return 'A server error occurred. Please try again later.';
      case 'NETWORK_ERROR':
        return 'Network connection error. Please check your internet connection.';
      case 'TIMEOUT':
        return 'Request timeout. Please try again.';
      default:
        return this.message || 'An unexpected error occurred.';
    }
  }
}
