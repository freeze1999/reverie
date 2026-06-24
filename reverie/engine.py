"""The reasoning core: feel -> realize -> execute.

``ReverieEngine.run`` performs one full idle fire. The gate (``gate.py``) has
already decided that a fire *should* happen; the engine decides *what* happens,
by reasoning rather than by lookup.

Routing: the class of action is inferred from the phase-2 output. Pure
reflection stays a single cheap text call; only an action that reads or changes
the world spends a real tool session; "do nothing" costs nothing further. This
keeps an always-on loop cheap in the common case while still allowing real work
when the agent decides real work is warranted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from pathlib import Path

from . import prompts as P
from .artifacts import parse_envelope
from .context import ContextBuilder
from .llm import LLMBackend, NullToolBackend, ToolBackend
from .observability import blast_radius, snapshot
from .types import ActionClass, Artifacts, Outcome

# Substrings in the phase-2 result that route phase 3. These are intentionally
# broad on the "needs a tool" side: when in doubt, prefer a grounded tool session
# (real results) over the text-only path (where the model is tempted to invent).
TOOL_HINTS = (
    "search", "browse", "fetch", "http", "read file", "read_file", "audit",
    "edit", "patch", "write file", "run ", "code", "compile", "look up",
    "check the", "open ", ".py", ".md", ".json", ".txt",
)
NOTHING_HINTS = ("nothing this time", "do nothing", "[nothing]", "nothing to do")


def classify(phase2: str) -> ActionClass:
    low = phase2.lower()
    if any(k in low for k in NOTHING_HINTS):
        return ActionClass.NOTHING
    if any(k in low for k in TOOL_HINTS):
        return ActionClass.NEEDS_TOOL
    return ActionClass.TEXT_ONLY


@dataclass
class ReverieEngine:
    """Wires an LLM, an optional tool backend, and a context builder together.

    Args:
        llm: the model backend for phases 1-2 and the text-only phase 3.
        context_builder: produces the working-context block and metadata.
        persona: the agent's system prompt / identity. Phases share it so the
            agent reasons *as itself*, not as a generic assistant.
        tool_backend: executes phase 3 when the action needs the world. Defaults
            to a no-op, which forces every action onto the text-only path.
        directive_tag: prefix prepended to the directive sent to the tool
            backend. In a real deployment this should mark the session as
            engine-originated so it does not re-arm the idle clock.
    """

    llm: LLMBackend
    context_builder: ContextBuilder
    persona: str = ""
    tool_backend: ToolBackend = field(default_factory=NullToolBackend)
    directive_tag: str = "[REVERIE] "
    #: Files/dirs the agent is NOT normally expected to touch. mtimes are snapshotted
    #: before and after the tool session; anything that changed is reported as blast radius.
    blast_watch: list[Path] = field(default_factory=list)
    blast_root: Optional[Path] = None
    p1_max_tokens: int = 700
    p2_max_tokens: int = 950
    p3_text_max_tokens: int = 1200

    def run(self, now: Optional[datetime] = None) -> Outcome:
        now = now or datetime.now()
        context, meta = self.context_builder.build(now)
        tools = meta.get("tools", "")
        sandbox = meta.get("sandbox", "(empty)")

        # Phase 1, feel.
        phase1 = self._call(P.PHASE1_FEEL.format(context=context), self.p1_max_tokens)
        # Phase 2, realize / capability firewall.
        phase2 = self._call(
            P.PHASE2_REALIZE.format(context=context, phase1=phase1, tools=tools, sandbox=sandbox),
            self.p2_max_tokens,
        )
        action_class = classify(phase2)

        # Phase 3, execute, routed by class.
        blast: list[str] = []
        if action_class is ActionClass.NOTHING:
            raw = phase2
            art = Artifacts(
                journal=f"{phase1}\n\n---\n\n{phase2}",
                memory="nothing this time",
                activity="idle - chose to do nothing",
            )
        elif action_class is ActionClass.NEEDS_TOOL:
            directive = self.directive_tag + P.PHASE3_EXECUTE.format(
                context=context, todo=phase2, envelope=P.ENVELOPE
            )
            before = snapshot(self.blast_watch) if self.blast_watch else {}
            raw = self.tool_backend.run(directive)
            if self.blast_watch:
                blast = blast_radius(before, snapshot(self.blast_watch), self.blast_root)
            art = parse_envelope(raw)
        else:  # TEXT_ONLY
            raw = self._call(
                P.PHASE3_TEXT_ONLY.format(context=context, todo=phase2, envelope=P.ENVELOPE),
                self.p3_text_max_tokens,
            )
            art = parse_envelope(raw)

        return Outcome(
            when=now,
            action_class=action_class,
            phase1_feel=phase1,
            phase2_realize=phase2,
            phase3_raw=raw,
            artifacts=art,
            blast_radius=blast,
        )

    def _call(self, user: str, max_tokens: int) -> str:
        return self.llm.complete(self.persona, user, max_tokens=max_tokens)
