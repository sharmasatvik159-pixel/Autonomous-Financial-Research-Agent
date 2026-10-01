"""Error Recovery & Exponential Backoff with Jitter for ARA-1.

Implements resilient retry policies, exponential backoff with full jitter,
and error classification for external API calls, timeouts, and rate limits.
"""

from __future__ import annotations
import logging
import random
import time
from enum import Enum
from typing import Callable, Any, Dict, Optional, Type, Tuple
from functools import wraps

logger = logging.getLogger("ARA1.Resilience.ErrorHandler")

class ErrorSeverity(str, Enum):
    TRANSIENT = "TRANSIENT"
    DEGRADED = "DEGRADED"
    FATAL = "FATAL"

class ErrorCategory(str, Enum):
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    SERVER_5XX = "SERVER_5XX"
    CLIENT_4XX = "CLIENT_4XX"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    UNKNOWN = "UNKNOWN"

def classify_error(exc: Exception) -> Tuple[ErrorCategory, ErrorSeverity]:
    """Classifies an exception into a domain category and severity level."""
    msg = str(exc).lower()
    exc_type = type(exc).__name__.lower()

    if "429" in msg or "rate limit" in msg or "too many requests" in msg:
        return ErrorCategory.RATE_LIMIT, ErrorSeverity.TRANSIENT
    elif any(code in msg for code in ("500", "502", "503", "504")) or "server error" in msg:
        return ErrorCategory.SERVER_5XX, ErrorSeverity.TRANSIENT
    elif "timeout" in msg or "timed out" in msg or "timeout" in exc_type:
        return ErrorCategory.TIMEOUT, ErrorSeverity.TRANSIENT
    elif "validation error" in msg or "schema" in msg:
        return ErrorCategory.SCHEMA_ERROR, ErrorSeverity.DEGRADED
    elif any(code in msg for code in ("400", "404", "not found")):
        return ErrorCategory.CLIENT_4XX, ErrorSeverity.DEGRADED
    else:
        return ErrorCategory.UNKNOWN, ErrorSeverity.DEGRADED

def calculate_backoff_with_jitter(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter_factor: float = 0.5,
) -> float:
    """
    Computes exponential backoff with full jitter to avoid thundering herd.
    Formula: delay = min(max_delay, base_delay * 2^(attempt - 1)) * (1 + random(-jitter, +jitter))
    """
    exp_delay = min(max_delay, base_delay * (2.0 ** max(0, attempt - 1)))
    jitter_range = exp_delay * jitter_factor
    jitter = random.uniform(-jitter_range, jitter_range)
    final_delay = max(0.05, exp_delay + jitter)
    return round(final_delay, 3)

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 10.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry_callback: Optional[Callable[[int, Exception, float], None]] = None,
):
    """
    Decorator executing wrapped function with exponential backoff and jitter upon transient errors.
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    cat, severity = classify_error(e)

                    if severity != ErrorSeverity.TRANSIENT or attempt == max_retries:
                        logger.warning(
                            f"Execution of '{func.__name__}' failed on attempt {attempt}/{max_retries} "
                            f"[{cat.value} / {severity.value}]: {e}"
                        )
                        raise e

                    delay = calculate_backoff_with_jitter(attempt, base_delay, max_delay)
                    logger.info(
                        f"Transient error [{cat.value}] in '{func.__name__}' on attempt {attempt}/{max_retries}. "
                        f"Backing off for {delay:.2f}s before retry. Error: {e}"
                    )
                    if on_retry_callback:
                        on_retry_callback(attempt, e, delay)

                    time.sleep(delay)

            if last_exception:
                raise last_exception
        return wrapper
    return decorator
