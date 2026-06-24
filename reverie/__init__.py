"""reverie, a reasoning-first idle engine for persistent LLM agents.

When a long-lived agent is left alone, what should it do? The common answer is a
scheduler firing scripted background tasks. reverie takes a different stance: the
agent *reasons* about its own idle time, what it notices, what it wants, what it
can actually do, and behaviour emerges from that reasoning, gated by a cheap
safety layer so it never burns budget or spams.

Public API:

    from reverie import (
        GatePolicy, GateState, Decision, decide,   # the LLM-free gate
        ReverieEngine, classify,                    # the three-phase reasoning core
        ContextBuilder, static_source,              # working-context assembly
        Artifacts, ArtifactWriter, parse_envelope,  # structured, sandboxed output
        FireReporter,                               # per-fire audit trail
        MockBackend, OpenAICompatBackend,           # LLM backends
        CallableToolBackend, NullToolBackend,       # tool backends
        Runner,                                     # gate + persistence glue
    )
"""
from .artifacts import ArtifactWriter, parse_envelope
from .context import ContextBuilder, static_source
from .engine import ReverieEngine, classify
from .gate import Decision, GatePolicy, GateState, decide
from .llm import (
    CallableToolBackend,
    MockBackend,
    NullToolBackend,
    OpenAICompatBackend,
)
from .observability import FireReporter, blast_radius, snapshot
from .runner import Runner
from .types import ActionClass, Artifacts, Outcome

__version__ = "0.1.0"

__all__ = [
    "GatePolicy",
    "GateState",
    "Decision",
    "decide",
    "ReverieEngine",
    "classify",
    "ContextBuilder",
    "static_source",
    "Artifacts",
    "ArtifactWriter",
    "parse_envelope",
    "Outcome",
    "ActionClass",
    "FireReporter",
    "snapshot",
    "blast_radius",
    "MockBackend",
    "OpenAICompatBackend",
    "CallableToolBackend",
    "NullToolBackend",
    "Runner",
]
