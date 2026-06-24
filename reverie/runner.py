"""Deployment glue: gate -> engine -> persist, with crash-safe arming.

``Runner`` is what a scheduler (cron, systemd timer, APScheduler) calls every few
minutes. It is intentionally thin: load arming state, ask the gate, and only on a
fire run the engine and persist the result. Everything expensive lives behind the
gate's single boolean.

Crash safety: the arming state is consumed (saved) *before* the engine runs, so a
crash mid-fire cannot cause the same idle gap to fire again on the next tick. A
lockfile guards against overlapping ticks.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .engine import ReverieEngine
from .gate import Decision, GatePolicy, GateState, decide
from .observability import FireReporter
from .types import Outcome


@dataclass
class Runner:
    """Ties the gate, the engine, and persistence together for a cron entrypoint.

    Args:
        engine: the reasoning core.
        state_dir: where arming state, the lockfile, and fire reports live.
        last_input_ts: callable returning the POSIX timestamp of the last external
            input (e.g. ``MAX(timestamp)`` over the human's messages).
        is_available: callable returning whether the agent may act right now.
        policy: gate thresholds.
        on_fire: optional hook called with the Outcome after a fire (e.g. to write
            artifacts, deposit a memory into the live session, or notify).
    """

    engine: ReverieEngine
    state_dir: Path
    last_input_ts: Callable[[], float]
    is_available: Callable[[], bool] = lambda: True
    policy: GatePolicy = GatePolicy()
    on_fire: Optional[Callable[[Outcome], None]] = None

    def __post_init__(self):
        self.state_dir = Path(self.state_dir)
        self.state_file = self.state_dir / "gate_state.json"
        self.lock_file = self.state_dir / ".fire.lock"
        self.reporter = FireReporter(self.state_dir)

    def tick(self, now: Optional[datetime] = None) -> tuple[Decision, Optional[Outcome]]:
        """Run one scheduler tick. Returns the gate decision and, if it fired, the
        engine Outcome."""
        now = now or datetime.now()
        state = self._load_state()
        decision = decide(now, self.last_input_ts(), self.is_available(), state, self.policy)
        if not decision.fire:
            return decision, None
        if self.lock_file.exists():
            return Decision(False, "fire lock present - overlapping tick skipped"), None

        self.lock_file.touch()
        try:
            # Consume the gap BEFORE running, so a crash can't re-fire it.
            state.last_fired_input_ts = self.last_input_ts()
            state.last_fire_at = now.timestamp()
            self._save_state(state)

            outcome = self.engine.run(now)
            self.reporter.write(outcome)
            if self.on_fire is not None:
                self.on_fire(outcome)
            return decision, outcome
        finally:
            self.lock_file.unlink(missing_ok=True)

    def _load_state(self) -> GateState:
        try:
            d = json.loads(self.state_file.read_text())
            return GateState(
                last_fired_input_ts=float(d.get("last_fired_input_ts", 0.0)),
                last_fire_at=float(d.get("last_fire_at", 0.0)),
            )
        except Exception:  # noqa: BLE001
            return GateState()

    def _save_state(self, state: GateState) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(
                {"last_fired_input_ts": state.last_fired_input_ts, "last_fire_at": state.last_fire_at},
                indent=2,
            )
        )
