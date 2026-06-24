"""The gate: a cheap, LLM-free decision about whether to fire *this* tick.

This is the safety layer that makes an always-on autonomy loop affordable and
non-annoying. It runs on a schedule (e.g. every 10 minutes from cron) and makes
a single boolean decision with no model call and no side effects. All of the
"don't burn money / don't spam" guarantees live here, as a pure function, so
they can be unit-tested exhaustively without a clock, a database, or a network.

Design invariants enforced by ``decide``:

* **Availability**, never fire while the agent is marked unavailable
  (quiet hours, sleeping, busy on a real task).
* **Active window**, only fire inside a configured wall-clock window. The
  window may wrap past midnight (e.g. 12:00 -> 02:00).
* **Idle threshold**, only fire after enough silence since the last input.
* **Fire-once-per-gap**, fire at most once per idle gap. The gate re-arms only
  when a *new* external input arrives. Without this, a single long silence would
  fire on every tick and drain budget.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GatePolicy:
    """Tunable thresholds for the gate. Immutable so a policy can be shared."""

    idle_threshold_min: float = 60.0
    window_start_hour: int = 12   # inclusive
    window_end_hour: int = 2      # exclusive; if < start, the window wraps midnight

    def in_window(self, now: datetime) -> bool:
        h = now.hour
        if self.window_start_hour <= self.window_end_hour:
            return self.window_start_hour <= h < self.window_end_hour
        # wrapped window, e.g. 12:00 -> 02:00 spans midnight
        return h >= self.window_start_hour or h < self.window_end_hour


@dataclass
class GateState:
    """Persistent arming state. Serialize this between ticks (e.g. as JSON).

    ``last_fired_input_ts`` records the input timestamp that the most recent fire
    consumed. The gate re-arms only when ``last_input_ts`` exceeds it, i.e. when
    a genuinely newer input has arrived.
    """

    last_fired_input_ts: float = 0.0
    last_fire_at: float = 0.0


@dataclass(frozen=True)
class Decision:
    fire: bool
    reason: str


def decide(
    now: datetime,
    last_input_ts: float,
    available: bool,
    state: GateState,
    policy: GatePolicy = GatePolicy(),
) -> Decision:
    """Pure decision function, no I/O, no side effects.

    Args:
        now: current local time (tz-aware recommended).
        last_input_ts: POSIX timestamp of the last *external* input (the human's
            last message). 0 means "nothing on record".
        available: whether the agent is currently available to act.
        state: persistent arming state from the previous tick.
        policy: thresholds.

    Returns:
        Decision(fire, human-readable reason). The reason string is logged so a
        deployment is auditable from its logs alone.
    """
    if not available:
        return Decision(False, "agent unavailable (quiet hours / busy)")
    if not policy.in_window(now):
        return Decision(
            False,
            f"outside active window (now {now.hour:02d}:00, "
            f"window {policy.window_start_hour:02d}:00-{policy.window_end_hour:02d}:00)",
        )
    if last_input_ts <= 0:
        return Decision(False, "no external input on record")
    idle_min = (now.timestamp() - last_input_ts) / 60.0
    if idle_min < policy.idle_threshold_min:
        return Decision(
            False, f"not idle enough ({idle_min:.0f} < {policy.idle_threshold_min:.0f} min)"
        )
    if last_input_ts <= state.last_fired_input_ts:
        return Decision(
            False, "already fired this idle gap (re-arms on a new input)"
        )
    return Decision(True, f"idle {idle_min:.0f} min, armed, in window")
