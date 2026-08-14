"""Estado determinista de privacidad financiera para UI y pruebas."""

from __future__ import annotations

import time


class FinancialPrivacy:
    MASK = "••••••••"

    def __init__(self, timeout_seconds: int = 300, clock=time.monotonic) -> None:
        self.timeout_seconds = timeout_seconds
        self.clock = clock
        self.hidden = False
        self.last_activity = clock()

    def activity(self) -> None:
        self.last_activity = self.clock()

    def hide(self) -> None:
        self.hidden = True

    def show(self) -> None:
        self.hidden = False
        self.activity()

    def check_timeout(self) -> bool:
        if self.clock() - self.last_activity >= self.timeout_seconds:
            self.hidden = True
        return self.hidden

    def display(self, value: str) -> str:
        return self.MASK if self.hidden else value
