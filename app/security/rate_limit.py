"""Rate limiting de login: ventana deslizante en memoria por IP (por proceso)."""

import time
from collections import defaultdict


class LoginRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def is_blocked(self, ip: str) -> bool:
        """Poda los intentos viejos y devuelve True si la IP superó el límite."""
        now = time.time()
        recientes = [t for t in self._attempts[ip] if now - t < self.window_seconds]
        self._attempts[ip] = recientes
        return len(recientes) >= self.max_attempts

    def record_failure(self, ip: str) -> None:
        self._attempts[ip].append(time.time())

    def reset(self, ip: str) -> None:
        self._attempts.pop(ip, None)
