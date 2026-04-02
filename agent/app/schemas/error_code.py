from enum import StrEnum


class ErrorCode(StrEnum):
    AUTHENTICATION_ERROR = "authentication_failed"
    VALIDATION_ERRROR = "validation_failed"
    OBJECT_NOT_FOUND = "object_not_found"
    WORKFLOW_TIMED_OUT = "workflow_timed_out"
    WORKFLOW_RUNTIME_ERROR = "workflow_runtime_error"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    MAX_REQUESTS_EXCEEDED = "max_requests_exceeded"
    ACTIVE_SESSION_DROPPED = "active_session_dropped"
    INACTIVE_SESSION_ACCESSED = "inactive_session_accessed"
    OPENAI_ERROR = "openai_error"
