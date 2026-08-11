import time


class Cooldown:
    def __init__(self, seconds: float):
        self.seconds = float(seconds)
        self._last = {}

    def ready(self, key: str) -> bool:
        if self.seconds <= 0:
            return True
        now = time.monotonic()
        if now - self._last.get(key, 0.0) >= self.seconds:
            self._last[key] = now
            return True
        return False

    def remaining(self, key: str) -> float:
        if self.seconds <= 0:
            return 0.0
        return max(0.0, self.seconds - (time.monotonic() - self._last.get(key, 0.0)))