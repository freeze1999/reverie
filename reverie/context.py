"""Context assembly.

A deliberately *generous but curated* working context is what lets the agent do
something useful instead of looping on the same shallow reflection. The guiding
analogy is a human brain: a small working memory (recent activity, the agent's
own idle history, the scratch index) plus recall-on-demand through tools in
phase 3, not a bulk dump of everything.

A ``ContextSource`` is any zero-argument callable returning a ``{label: value}``
fragment. Sources are best-effort: if one raises, it degrades to a placeholder
instead of taking the whole tick down. This mirrors a real deployment where the
weather API, the balance check, or the database might each be transiently
unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

ContextSource = Callable[[], dict]


@dataclass
class ContextBuilder:
    """Assembles the ``[CONTEXT]`` block handed to phases 1 and 2.

    Args:
        sources: ordered list of best-effort fragment providers.
        tools: human-readable inventory of what phase 3 can actually do. This is
            injected into the phase-2 capability firewall, so it must honestly
            describe the agent's real affordances.
        scratch_index: callable returning the current scratch-box index (shown so
            the agent can continue unfinished work rather than restart).
    """

    sources: list[ContextSource] = field(default_factory=list)
    tools: str = ""
    scratch_index: Callable[[], str] = lambda: "(empty)"
    header: str = "[CONTEXT]"

    def build(self, now: Optional[datetime] = None) -> tuple[str, dict]:
        now = now or datetime.now()
        fragments: dict[str, object] = {"time": now.strftime("%A %H:%M")}
        for src in self.sources:
            try:
                fragments.update(src())
            except Exception:  # noqa: BLE001 - best-effort by design
                continue
        sandbox = _safe(self.scratch_index, "(empty)")
        lines = [self.header]
        for label, value in fragments.items():
            lines.append(f"- {label}: {value}")
        lines.append(f"- scratch box:\n  {sandbox}")
        meta = {"now": now, "tools": self.tools, "sandbox": sandbox, "fragments": fragments}
        return "\n".join(lines), meta


def _safe(fn: Callable[[], str], fallback: str) -> str:
    try:
        return fn() or fallback
    except Exception:  # noqa: BLE001
        return fallback


def static_source(**fields) -> ContextSource:
    """Convenience: a fixed fragment, handy for demos and tests."""

    def _src() -> dict:
        return dict(fields)

    return _src
