"""Thread-safe generation IDs for discarding stale AI responses."""

from __future__ import annotations

import threading


class RequestGenerationGuard:
    """Issue increasing request IDs and identify the newest active request."""

    def __init__(self):
        self._lock = threading.Lock()
        self._generation = 0

    def begin(self) -> int:
        with self._lock:
            self._generation += 1
            return self._generation

    def is_current(self, request_id: int) -> bool:
        with self._lock:
            return bool(request_id) and request_id == self._generation


__all__ = ["RequestGenerationGuard"]
