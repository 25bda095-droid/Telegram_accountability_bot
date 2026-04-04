import time
from typing import Any

class TTLCache:
    def __init__(self, default_ttl: int = 300):
        self._store: dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        if key in self._store:
            value, expires_at = self._store[key]
            if time.monotonic() < expires_at:
                return value
            del self._store[key]
        return None

    def set(self, key: str, value: Any, ttl: int | None = None):
        ttl = ttl or self.default_ttl
        self._store[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str):
        self._store.pop(key, None)

    def clear(self):
        self._store.clear()

# Module-level singletons (import these in services)
leaderboard_cache = TTLCache(default_ttl=300)   # 5 min
rate_limit_cache  = TTLCache(default_ttl=3600)  # 1 hr