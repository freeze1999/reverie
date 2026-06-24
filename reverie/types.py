"""Shared value types for the reverie engine.

These are deliberately plain dataclasses with no behaviour, so they are easy to
serialize (for fire reports) and easy to reason about in tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ActionClass(str, Enum):
    """How the engine routes phase 3 after the agent has decided what to do.

    The class is inferred from the phase-2 (realize) output, so that expensive
    tool sessions are only spawned when the chosen action actually needs them.
    """

    NOTHING = "NOTHING"        # the agent decided to do nothing this cycle
    NEEDS_TOOL = "NEEDS_TOOL"  # the action reads or changes the world -> real tools
    TEXT_ONLY = "TEXT_ONLY"    # pure reflection from the agent's own head


@dataclass
class Artifacts:
    """The structured output the agent returns, extracted from its envelope.

    The runtime (not the model) owns the actual persistence of these, which is
    what keeps a hallucinated file path or a malformed write from doing damage.
    """

    journal: str = ""
    memory: str = ""
    activity: str = ""
    note: str = ""
    keep: Optional[tuple[str, str]] = None  # (filename, body)


@dataclass
class Outcome:
    """The full result of one idle fire, everything needed to audit it later."""

    when: datetime
    action_class: ActionClass
    phase1_feel: str
    phase2_realize: str
    phase3_raw: str
    artifacts: Artifacts
    blast_radius: list[str] = field(default_factory=list)
