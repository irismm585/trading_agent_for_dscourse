"""Simple TTL cache for data layer to reduce redundant akshare calls."""

import time
import threading
from typing import Any, Callable, Optional


class TTLCache:
    """Thread-safe TTL cache. Each key expires independently."""

    def __init__(self, default_ttl: float = 300.0):
        self._default_ttl = default_ttl
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.time() > expires_at:
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        expires_at = time.time() + (ttl if ttl is not None else self._default_ttl)
        with self._lock:
            self._data[key] = (expires_at, value)

    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[float] = None) -> Any:
        existing = self.get(key)
        if existing is not None:
            return existing
        value = factory()
        self.set(key, value, ttl)
        return value

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


# Global singleton
data_cache = TTLCache(default_ttl=300.0)
