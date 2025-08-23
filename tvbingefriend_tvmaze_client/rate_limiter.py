"""Rate limiting functionality for TVMaze API calls."""

import time
from datetime import datetime, timedelta, UTC
from typing import Optional, Callable, Any
from functools import wraps
from collections import deque
from logging import Logger, getLogger


class TVMazeRateLimiter:
    """Rate limiter specifically designed for TVMaze API constraints.
    
    TVMaze allows approximately 60 requests per minute with burst handling.
    This implements a sliding window algorithm to respect those limits.
    """
    
    def __init__(self, 
                 requests_per_minute: int = 60, 
                 burst_requests: int = 10,
                 logger: Optional[Logger] = None):
        """Initialize the TVMaze rate limiter.
        
        Args:
            requests_per_minute: Maximum requests allowed per minute (default: 60 for TVMaze)
            burst_requests: Maximum burst requests before enforcing delays (default: 10)
            logger: Optional logger instance
        """
        self.requests_per_minute = requests_per_minute
        self.burst_requests = burst_requests
        self.logger = logger or getLogger(__name__)
        
        self.request_times = deque()
        self.burst_count = 0
        self.last_burst_reset = datetime.now(UTC)
    
    def can_make_request(self) -> bool:
        """Check if a request can be made without exceeding rate limits.
        
        Returns:
            True if request can be made immediately, False if rate limited
        """
        now = datetime.now(UTC)
        
        # Clean old requests (older than 1 minute)
        cutoff_time = now - timedelta(minutes=1)
        while self.request_times and self.request_times[0] <= cutoff_time:
            self.request_times.popleft()
        
        # Reset burst count every minute
        if now - self.last_burst_reset > timedelta(minutes=1):
            self.burst_count = 0
            self.last_burst_reset = now
        
        # Check both per-minute and burst limits
        within_per_minute_limit = len(self.request_times) < self.requests_per_minute
        within_burst_limit = self.burst_count < self.burst_requests
        
        return within_per_minute_limit and within_burst_limit
    
    def record_request(self) -> None:
        """Record that a request was made."""
        now = datetime.now(UTC)
        self.request_times.append(now)
        self.request_times.append(now)
        self.burst_count += 1
    
    def time_until_next_request(self) -> float:
        """Calculate seconds until next request can be made.
        
        Returns:
            Seconds to wait before next request (0.0 if can make request now)
        """
        if self.can_make_request():
            return 0.0
        
        now = datetime.now(UTC)

        # Time until oldest request expires (for per-minute limit)
        if self.request_times:
            time_until_minute_reset = 60 - (now - self.request_times[0]).total_seconds()
        else:
            time_until_minute_reset = 0.0
        
        # Time until burst limit resets
        time_until_burst_reset = 60 - (now - self.last_burst_reset).total_seconds()
        
        return max(1.0, min(time_until_minute_reset, time_until_burst_reset))
    
    def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limits."""
        if not self.can_make_request():
            wait_time = self.time_until_next_request()
            self.logger.info(f"TVMaze API rate limit reached. Waiting {wait_time:.1f} seconds.")
            time.sleep(wait_time)
    
    def rate_limited(self, func: Callable) -> Callable:
        """Decorator to apply rate limiting to TVMaze API calls.
        
        Args:
            func: Function to rate limit
            
        Returns:
            Rate-limited function
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            """Wrapper function."""
            self.wait_if_needed()
            self.record_request()
            return func(*args, **kwargs)
        return wrapper
    
    def get_status(self) -> dict[str, Any]:
        """Get current rate limiting status.
        
        Returns:
            Dictionary with current rate limiting information
        """
        now = datetime.now(UTC)
        
        return {
            'can_make_request': self.can_make_request(),
            'time_until_next_request': self.time_until_next_request(),
            'requests_in_last_minute': len(self.request_times),
            'requests_per_minute_limit': self.requests_per_minute,
            'burst_requests_used': self.burst_count,
            'burst_requests_limit': self.burst_requests,
            'last_burst_reset': self.last_burst_reset.isoformat(),
            'current_time': now.isoformat()
        }
