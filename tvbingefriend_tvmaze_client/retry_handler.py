"""Enhanced retry handling for TVMaze API calls."""

import time
from datetime import datetime, timedelta, UTC
from typing import Optional, Callable, Any, Type, TypedDict, cast
from functools import wraps
from collections import defaultdict
from logging import Logger, getLogger
import requests


class BackoffState(TypedDict):
    """State of a backoff attempt."""
    consecutive_failures: int
    last_failure_time: Optional[datetime]
    backoff_until: Optional[datetime]


# noinspection PyMethodMayBeStatic
class TVMazeRetryHandler:
    """Enhanced retry handler specifically for TVMaze API with exponential backoff.
    
    Complements the existing urllib3 retry strategy with application-level
    retry logic and TVMaze-specific error handling.
    """
    
    def __init__(self,

                 max_attempts: int = 3,
                 base_delay_seconds: float = 1.0,
                 max_delay_seconds: float = 60.0,
                 logger: Optional[Logger] = None):
        """Initialize the TVMaze retry handler.
        
        Args:
            max_attempts: Maximum retry attempts for application-level retries
            base_delay_seconds: Base delay for exponential backoff
            max_delay_seconds: Maximum delay between retries
            logger: Optional logger instance
        """
        self.max_attempts = max_attempts
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.logger = logger or getLogger(__name__)
        
        # Track backoff state for different operation types
        self.backoff_state: defaultdict[str, BackoffState] = defaultdict(lambda: cast(BackoffState, {
            'consecutive_failures': 0,
            'last_failure_time': None,
            'backoff_until': None
        }))
    
    def is_rate_limit_error(self, exception: Exception) -> bool:
        """Check if an exception indicates TVMaze API rate limiting.
        
        Args:
            exception: The exception to check
            
        Returns:
            True if this is a rate limit error
        """
        if isinstance(exception, requests.exceptions.HTTPError):
            if hasattr(exception, 'response') and exception.response is not None:
                return exception.response.status_code == 429
        
        error_message = str(exception).lower()
        rate_limit_indicators = [
            'rate limit',
            'too many requests',
            '429',
            'quota exceeded',
            'throttled'
        ]
        
        return any(indicator in error_message for indicator in rate_limit_indicators)
    
    def is_retriable_error(self, exception: Exception) -> bool:
        """Check if an exception should be retried.
        
        Args:
            exception: The exception to check
            
        Returns:
            True if the error should be retried
        """
        # Rate limit errors should be retried
        if self.is_rate_limit_error(exception):
            return True
        
        # Network/connection errors
        if isinstance(exception, (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError
        )):
            return True
        
        # HTTP errors that are typically temporary
        if isinstance(exception, requests.exceptions.HTTPError):
            if hasattr(exception, 'response') and exception.response is not None:
                status_code = exception.response.status_code
                # Retry on server errors and rate limits
                return status_code >= 500 or status_code == 429
        
        return False
    
    def calculate_backoff_delay(self, attempt: int, is_rate_limit: bool = False) -> float:
        """Calculate backoff delay for retry attempt.
        
        Args:
            attempt: Current attempt number (1-based)
            is_rate_limit: Whether this is due to rate limiting
            
        Returns:
            Delay in seconds
        """
        if is_rate_limit:
            # Longer delay for rate limit errors
            return min(60.0, self.base_delay_seconds * 30)
        
        # Exponential backoff for other errors
        delay = self.base_delay_seconds * (2 ** (attempt - 1))
        return min(delay, self.max_delay_seconds)
    
    def handle_failure(self, operation_id: str, exception: Exception) -> None:
        """Handle a failed operation for backoff tracking.
        
        Args:
            operation_id: Identifier for the operation type
            exception: The exception that occurred
        """
        backoff_state = self.backoff_state[operation_id]
        backoff_state['consecutive_failures'] += 1
        backoff_state['last_failure_time'] = datetime.now(UTC)
        
        is_rate_limit = self.is_rate_limit_error(exception)
        backoff_seconds = self.calculate_backoff_delay(
            backoff_state['consecutive_failures'], 
            is_rate_limit
        )
        
        backoff_state['backoff_until'] = datetime.now(UTC) + timedelta(seconds=backoff_seconds)
        
        self.logger.warning(
            f"TVMaze API failure #{backoff_state['consecutive_failures']} for {operation_id}. "
            f"Backing off for {backoff_seconds:.1f} seconds. Error: {exception}"
        )
    
    def handle_success(self, operation_id: str) -> None:
        """Handle a successful operation.
        
        Args:
            operation_id: Identifier for the operation type
        """
        if operation_id in self.backoff_state:
            self.backoff_state[operation_id] = {
                'consecutive_failures': 0,
                'last_failure_time': None,
                'backoff_until': None
            }
    
    def check_backoff(self, operation_id: str) -> None:
        """Check if operation should wait due to backoff.
        
        Args:
            operation_id: Identifier for the operation type
        """
        backoff_state = self.backoff_state[operation_id]
        backoff_until = backoff_state['backoff_until']
        if backoff_until and isinstance(backoff_until, datetime) and datetime.now(UTC) < backoff_until:
            wait_time = (backoff_until - datetime.now(UTC)).total_seconds()
            if wait_time > 0:
                self.logger.info(f"In backoff period for {operation_id}. Waiting {wait_time:.1f} seconds.")
                time.sleep(wait_time)
    
    def with_retry(self, 
                   operation_id: str = "tvmaze_api", 
                   max_attempts: Optional[int] = None,
                   exception_types: tuple[Type[Exception], ...] = (Exception,)) -> Callable:
        """Decorator for adding retry logic to TVMaze API calls.
        
        Args:
            operation_id: Identifier for the operation (for backoff tracking)
            max_attempts: Override default max attempts
            exception_types: Tuple of exception types to catch and retry
            
        Returns:
            Decorated function with retry logic
        """
        def decorator(func: Callable) -> Callable:
            """Decorator for adding retry logic to TVMaze API calls."""
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                """Wrapper function."""
                attempts = max_attempts or self.max_attempts
                last_exception = None
                
                # Check if we're in a backoff period
                self.check_backoff(operation_id)
                
                for attempt in range(1, attempts + 1):
                    try:
                        result = func(*args, **kwargs)
                        # Success - reset backoff state
                        self.handle_success(operation_id)
                        return result
                        
                    except exception_types as e:
                        last_exception = e
                        
                        # Only retry if it's a retriable error
                        if not self.is_retriable_error(e):
                            self.logger.error(f"Non-retriable error for {operation_id}: {e}")
                            raise
                        
                        if attempt < attempts:
                            is_rate_limit = self.is_rate_limit_error(e)
                            delay = self.calculate_backoff_delay(attempt, is_rate_limit)
                            
                            self.logger.warning(
                                f"TVMaze API attempt {attempt}/{attempts} failed for {operation_id}. "
                                f"Retrying in {delay:.1f}s. Error: {e}"
                            )
                            
                            time.sleep(delay)
                        else:
                            # All attempts failed - update backoff state
                            self.handle_failure(operation_id, e)
                            self.logger.error(
                                f"All {attempts} attempts failed for TVMaze API {operation_id}. Error: {e}"
                            )
                
                # All attempts failed
                raise last_exception
                
            return wrapper
        return decorator
    
    def get_status(self, operation_id: str = "tvmaze_api") -> dict[str, Any]:
        """Get retry status for an operation.
        
        Args:
            operation_id: Operation identifier
            
        Returns:
            Dictionary with retry status information
        """
        backoff_state = self.backoff_state[operation_id]
        now = datetime.now(UTC)
        
        backoff_until = backoff_state['backoff_until']
        last_failure_time = backoff_state['last_failure_time']
        
        return {
            'operation_id': operation_id,
            'consecutive_failures': backoff_state['consecutive_failures'],
            'in_backoff_period': (
                backoff_until and isinstance(backoff_until, datetime) and now < backoff_until
            ),
            'backoff_until': (
                backoff_until.isoformat() if isinstance(backoff_until, datetime) else None
            ),
            'last_failure_time': (
                last_failure_time.isoformat() if isinstance(last_failure_time, datetime) else None
            ),
            'max_attempts': self.max_attempts,
            'current_time': now.isoformat()
        }
