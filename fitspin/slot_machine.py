from __future__ import annotations

import random
import time
from dataclasses import dataclass, field


@dataclass
class SlotMachineState:
    reels: list[str] = field(default_factory=lambda: ["-", "-", "-"])
    score: int = 0
    last_reward: int = 0
    last_combo: str = "---"
    spinning: bool = False


class SlotMachineEngine:
    SYMBOLS = ("7", "BAR", "CHERRY", "STAR", "COIN")

    def __init__(self) -> None:
        self.state = SlotMachineState()
        self._pending_spins = 0
        self._spin_ends_at = 0.0
        self._final_result: list[str] | None = None

    def trigger_spin(self) -> None:
        self._pending_spins += 1
        if not self.state.spinning:
            self._start_next_spin()

    def reset(self) -> None:
        self.state = SlotMachineState()
        self._pending_spins = 0
        self._spin_ends_at = 0.0
        self._final_result = None

    def tick(self) -> None:
        if not self.state.spinning:
            return

        now = time.monotonic()
        if now < self._spin_ends_at:
            self.state.reels = [random.choice(self.SYMBOLS) for _ in range(3)]
            return

        self.state.reels = list(self._final_result or self.state.reels)
        self.state.last_combo = " ".join(self.state.reels)
        self.state.last_reward = self._reward(self.state.reels)
        self.state.score += self.state.last_reward
        self.state.spinning = False
        self._final_result = None

        if self._pending_spins:
            self._start_next_spin()

    def _start_next_spin(self) -> None:
        if self._pending_spins <= 0:
            return
        self._pending_spins -= 1
        self.state.spinning = True
        self._final_result = [random.choice(self.SYMBOLS) for _ in range(3)]
        self._spin_ends_at = time.monotonic() + 0.8

    @staticmethod
    def _reward(reels: list[str]) -> int:
        unique = len(set(reels))
        if unique == 1:
            return 100 if reels[0] == "7" else 50
        if unique == 2:
            return 12
        return 3
