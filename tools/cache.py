"""Response Caching System for ARA-1 Tool Executions.

Provides file-backed and in-memory caching with Time-To-Live (TTL) expiration,
preventing duplicate API invocations and preserving rate limits.
"""

from __future__ import annotations
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional, Dict

logger = logging.getLogger("ARA1.Cache")

class ToolCache:
    """Persistent and in-memory cache for external tool responses."""

    def __init__(self, cache_dir: str = "./data/cache", default_ttl_seconds: int = 3600):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl_seconds
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def _generate_key(self, tool_name: str, kwargs: Optional[Dict[str, Any]] = None) -> str:
        """Computes a deterministic hash key from tool name and arguments."""
        if kwargs:
            clean_args = {k: v for k, v in sorted(kwargs.items())}
            raw_repr = f"{tool_name}:{json.dumps(clean_args, sort_keys=True, default=str)}"
        else:
            raw_repr = tool_name
        return hashlib.sha256(raw_repr.encode("utf-8")).hexdigest()

    def get(self, tool_name: str, kwargs: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Retrieves cached response if present and not expired."""
        key = self._generate_key(tool_name, kwargs)

        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if time.time() < entry["expires_at"]:
                logger.debug(f"Memory cache HIT for {tool_name}")
                return entry["data"]
            else:
                del self._memory_cache[key]

        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    entry = json.load(f)
                if time.time() < entry["expires_at"]:
                    logger.debug(f"Disk cache HIT for {tool_name}")
                    self._memory_cache[key] = entry
                    return entry["data"]
                else:
                    cache_file.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Error reading cache file {cache_file}: {e}")

        return None

    def set(
        self,
        tool_name: str,
        kwargs: Any,
        data: Any = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        if data is None:
            actual_data = kwargs
            actual_kwargs = {}
        else:
            actual_kwargs = kwargs if isinstance(kwargs, dict) else {}
            actual_data = data

        key = self._generate_key(tool_name, actual_kwargs)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        entry = {
            "tool_name": tool_name,
            "data": actual_data,
            "cached_at": time.time(),
            "expires_at": time.time() + ttl,
        }

        self._memory_cache[key] = entry
        cache_file = self.cache_dir / f"{key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(entry, f, default=str)
        except Exception as e:
            logger.warning(f"Failed to persist cache file {cache_file}: {e}")

    def clear(self) -> None:
        """Purges all cached data."""
        self._memory_cache.clear()
        for f in self.cache_dir.glob("*.json"):
            try:
                f.unlink()
            except Exception:
                pass

_GLOBAL_CACHE: Optional[ToolCache] = None

def get_tool_cache() -> ToolCache:
    """Singleton getter for ToolCache."""
    global _GLOBAL_CACHE
    if _GLOBAL_CACHE is None:
        _GLOBAL_CACHE = ToolCache()
    return _GLOBAL_CACHE
