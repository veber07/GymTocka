from __future__ import annotations

import math
import random
import time
from collections import Counter
from dataclasses import dataclass, field


DEFAULT_REELS = ["cherry", "lemon", "orange"]
FRUIT_SYMBOLS = {"cherry", "grapes", "lemon", "orange", "plum", "watermelon"}


@dataclass
class SlotMachineState:
    reels: list[str] = field(default_factory=lambda: list(DEFAULT_REELS))
    score: int = 0
    last_reward: int = 0
    last_combo: str = "Fresh start"
    spinning: bool = False
    pending_spins: int = 0
    spin_mix: float = 0.0
    celebration: float = 0.0


class SlotMachineEngine:
    SYMBOLS = ("bell", "seven", "cherry", "grapes", "lemon", "orange", "plum", "watermelon")
    WEIGHTS = (0.72, 0.5, 1.15, 1.0, 0.95, 1.0, 0.9, 0.82)
    JACKPOT_REWARDS = {
        "seven": 150,
        "bell": 90,
        "watermelon": 72,
        "grapes": 66,
        "cherry": 60,
        "lemon": 56,
        "orange": 56,
        "plum": 56,
    }
    DISPLAY_NAMES = {
        "bell": "Bell",
        "seven": "Lucky 7",
        "cherry": "Cherry",
        "grapes": "Grapes",
        "lemon": "Lemon",
        "orange": "Orange",
        "plum": "Plum",
        "watermelon": "Watermelon",
    }
    SPIN_BASE_DURATION = 0.64
    REEL_STAGGER = 0.16
    SPIN_WOBBLE_SPEED = 16.0
    CELEBRATION_DURATION = 0.95

    def __init__(self) -> None:
        self.state = SlotMachineState()
        self._pending_spins = 0
        self._spin_started_at = 0.0
        self._reel_stop_times = [0.0, 0.0, 0.0]
        self._final_result: list[str] | None = None
        self._celebration_ends_at = 0.0

    def trigger_spin(self) -> None:
        self._pending_spins += 1
        self.state.pending_spins = self._pending_spins
        if not self.state.spinning:
            self._start_next_spin()

    def reset(self) -> None:
        self.state = SlotMachineState()
        self._pending_spins = 0
        self._spin_started_at = 0.0
        self._reel_stop_times = [0.0, 0.0, 0.0]
        self._final_result = None
        self._celebration_ends_at = 0.0

    def tick(self) -> None:
        now = time.monotonic()
        self.state.pending_spins = self._pending_spins

        if self.state.spinning:
            self.state.spin_mix = 0.45 + 0.55 * abs(math.sin(now * self.SPIN_WOBBLE_SPEED))
            self.state.celebration = 0.0

            completed = 0
            assert self._final_result is not None
            for index in range(3):
                if now < self._reel_stop_times[index]:
                    self.state.reels[index] = self._weighted_symbol()
                else:
                    self.state.reels[index] = self._final_result[index]
                    completed += 1

            if completed == 3:
                self._finish_spin(now)
            return

        self.state.spin_mix = 0.0
        if now < self._celebration_ends_at:
            remaining = max(0.0, self._celebration_ends_at - now)
            strength = remaining / self.CELEBRATION_DURATION
            self.state.celebration = max(0.0, strength) * (0.4 + 0.6 * abs(math.sin(now * 10.0)))
        else:
            self.state.celebration = 0.0

    def _finish_spin(self, now: float) -> None:
        self.state.reels = list(self._final_result or self.state.reels)
        self.state.last_combo = self._combo_label(self.state.reels)
        self.state.last_reward = self._reward(self.state.reels)
        self.state.score += self.state.last_reward
        self.state.spinning = False
        self.state.spin_mix = 0.0
        self.state.celebration = 1.0 if self.state.last_reward >= 14 else 0.45
        self._celebration_ends_at = now + self.CELEBRATION_DURATION
        self._final_result = None

        if self._pending_spins:
            self._start_next_spin()
        else:
            self.state.pending_spins = 0

    def _start_next_spin(self) -> None:
        if self._pending_spins <= 0:
            return

        self._pending_spins -= 1
        now = time.monotonic()
        self._spin_started_at = now
        self.state.spinning = True
        self.state.last_reward = 0
        self.state.pending_spins = self._pending_spins
        self._final_result = [self._weighted_symbol() for _ in range(3)]
        self._reel_stop_times = [
            now + self.SPIN_BASE_DURATION + self.REEL_STAGGER * index for index in range(3)
        ]

    def _weighted_symbol(self) -> str:
        return random.choices(self.SYMBOLS, weights=self.WEIGHTS, k=1)[0]

    def _reward(self, reels: list[str]) -> int:
        counts = Counter(reels)
        highest = max(counts.values(), default=0)

        if highest == 3:
            return self.JACKPOT_REWARDS.get(reels[0], 60)
        if highest == 2:
            pair_symbol = next(symbol for symbol, count in counts.items() if count == 2)
            if pair_symbol == "seven":
                return 30
            if pair_symbol == "bell":
                return 24
            return 14
        if set(reels).issubset(FRUIT_SYMBOLS):
            return 6
        return 3

    def _combo_label(self, reels: list[str]) -> str:
        return "  •  ".join(self.DISPLAY_NAMES.get(symbol, symbol.title()) for symbol in reels)
