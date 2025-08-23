"""Combined reliability features for TVMaze API - rate limiting and retry handling."""

from typing import Optional, Callable, Any, Dict
from logging import Logger, getLogger
from functools import wraps

from .rate_limiter import TVMazeRateLimiter
from .retry_handler import TVMazeRetryHandler


class TVMazeReliabilityManager:
    """Combines rate limiting and retry handling for robust TVMaze API usage.
    
    This class provides a unified interface for both rate limiting and retry logic,
    making it easy to add reliability features to any TVMaze API client.
    """
    
    def __init__(self,
                 rate_limiter: Optional[TVMazeRateLimiter] = None,
                 retry_handler: Optional[TVMazeRetryHandler] = None,
                 logger: Optional[Logger] = None):
        """Initialize the reliability manager.
        
        Args:
            rate_limiter: Optional rate limiter instance (creates default if None)
            retry_handler: Optional retry handler instance (creates default if None)  
            logger: Optional logger instance
        """
        self.logger = logger or getLogger(__name__)
        self.rate_limiter = rate_limiter or TVMazeRateLimiter(logger=self.logger)
        self.retry_handler = retry_handler or TVMazeRetryHandler(logger=self.logger)
    
    def reliable_api_call(
            self,
            operation_id: str = "tvmaze_api",
            max_attempts: Optional[int] = None
    ) -> Callable:
        """Decorator that combines rate limiting and retry logic.
        
        Args:
            operation_id: Identifier for the operation (for tracking)
            max_attempts: Override default retry attempts
            
        Returns:
            Decorator function that adds reliability features
        """
        def decorator(func: Callable) -> Callable:
            """First apply retry logic, then rate limiting"""
            retry_decorated = self.retry_handler.with_retry(
                operation_id=operation_id,
                max_attempts=max_attempts
            )(func)
            
            rate_limited = self.rate_limiter.rate_limited(retry_decorated)
            
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                """Wrapper function"""
                return rate_limited(*args, **kwargs)
            
            return wrapper
        return decorator
    
    def get_status(self, operation_id: str = "tvmaze_api") -> Dict[str, Any]:
        """Get comprehensive status of reliability features.
        
        Args:
            operation_id: Operation identifier
            
        Returns:
            Dictionary with status of both rate limiting and retry features
        """
        return {
            'rate_limiting': self.rate_limiter.get_status(),
            'retry_handling': self.retry_handler.get_status(operation_id),
            'operation_id': operation_id
        }
    
    def wait_if_needed(self) -> None:
        """Wait if rate limiting requires it."""
        self.rate_limiter.wait_if_needed()
    
    def is_healthy(self, operation_id: str = "tvmaze_api") -> bool:
        """Check if the API client is in a healthy state.
        
        Args:
            operation_id: Operation identifier
            
        Returns:
            True if healthy (can make requests and not in excessive backoff)
        """
        rate_status = self.rate_limiter.get_status()
        retry_status = self.retry_handler.get_status(operation_id)
        
        # Healthy if we can make requests and don't have too many consecutive failures
        can_make_requests = rate_status['can_make_request'] or rate_status['time_until_next_request'] < 60
        not_failing_excessively = retry_status['consecutive_failures'] < 5
        
        return can_make_requests and not_failing_excessively
