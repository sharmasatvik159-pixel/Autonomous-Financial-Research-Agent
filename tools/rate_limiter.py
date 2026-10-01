"""Rate Limiting Infrastructure for ARA-1 Tool Invocations.

Implements token bucket rate limiting to comply with SEC EDGAR (10 req/s),
Alpha Vantage, Tavily, and financial data provider access quotas.
"""

from __future__ import annotations
import time
import threading
import logging
from typing import Dict

logger = logging.getLogger("ARA1.RateLimiter")

class TokenBucket:
    """Token bucket rate limiter for a specific API domain."""

    def __init__(self, rate_per_sec: float, capacity: Optional[float] = None):
        self.rate = rate_per_sec
        self.capacity = capacity if capacity is not None else max(1.0, rate_per_sec)
        self.tokens = self.capacity
        self.last_update = time.perf_counter()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        """Blocks until a token is available to proceed."""
        with self.lock:
            while True:
                now = time.perf_counter()
                elapsed = now - self.last_update
                self.last_update = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

                deficit = 1.0 - self.tokens
                sleep_time = deficit / self.rate
                time.sleep(sleep_time)

class APIRateLimiter:
    """Central coordinator of per-tool rate limits."""

    def __init__(self):
        self._limiters: Dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def get_limiter(self, tool_name: str, default_rps: float = 5.0) -> TokenBucket:
        with self._lock:
            if tool_name not in self._limiters:
                if tool_name == "sec_filing_search":
                    rps = 10.0
                elif tool_name == "financial_data_api":
                    rps = 5.0
                elif tool_name == "web_search":
                    rps = 4.0
                elif tool_name == "news_sentiment":
                    rps = 5.0
                else:
                    rps = default_rps
                self._limiters[tool_name] = TokenBucket(rate_per_sec=rps)
            return self._limiters[tool_name]

    def acquire(self, tool_name: str, rps: float = 5.0) -> None:
        """Blocks until the tool has permission to dispatch."""
        limiter = self.get_limiter(tool_name, default_rps=rps)
        limiter.acquire()

_GLOBAL_RATE_LIMITER: Optional[APIRateLimiter] = None

def get_rate_limiter(tool_name: Optional[str] = None, rate_per_second: float = 5.0) -> Any:
    """Singleton getter for APIRateLimiter or a specific tool's TokenBucket."""
    global _GLOBAL_RATE_LIMITER
    if _GLOBAL_RATE_LIMITER is None:
        _GLOBAL_RATE_LIMITER = APIRateLimiter()
    if tool_name is not None:
        return _GLOBAL_RATE_LIMITER.get_limiter(tool_name, default_rps=rate_per_second)
    return _GLOBAL_RATE_LIMITER

