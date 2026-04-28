"""Tiny in-memory TTL cache, thread-safe."""
from __future__ import annotations
import threading
import time
from typing import Any, Callable, Optional, Tuple


class TTLCache:
    def __init__(self, default_ttl: int = 1800):
        self._store: dict[str, Tuple[float, Any]] = {}
        self._ttl = default_ttl
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            ts, val = entry
            if time.time() - ts > self._ttl:
                self._store.pop(key, None)
                return None
            return val

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.time(), value)

    def get_or_compute(self, key: str, fn: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = fn()
        if value is not None:
            self.set(key, value)
        return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def stats(self) -> dict:
        with self._lock:
            return {"entries": len(self._store), "ttl_seconds": self._ttl}
