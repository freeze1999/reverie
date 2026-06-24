"""Observability for a self-acting agent.

An autonomous agent that can run real tools can, in principle, change things you
did not anticipate, including its own code. The stance taken here is
*observability, not a cage*: don't forbid the agent from acting, but make every
fire fully auditable after the fact.

Two mechanisms:

* **Fire reports**, one JSON file per fire, capturing the entire reasoning
  trace (feel / realize / execute) plus the extracted artifacts. You can read
  back exactly *why* the agent did what it did.
* **Blast radius**, an mtime snapshot of a watch set taken before and after the
  execute phase. Any file in the watch set that changed during a fire is flagged.
  The watch set should list things the agent is *not* normally expected to touch
  (its own source, config, identity files), so unexpected edits surface loudly.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .types import Outcome


def snapshot(watch: list[Path]) -> dict[str, float]:
    """Map every file under the watch paths to its mtime."""
    snap: dict[str, float] = {}
    for base in watch:
        try:
            if base.is_file():
                snap[str(base)] = base.stat().st_mtime
            elif base.is_dir():
                for q in base.rglob("*"):
                    if q.is_file() and "__pycache__" not in str(q):
                        snap[str(q)] = q.stat().st_mtime
        except Exception:  # noqa: BLE001
            continue
    return snap


def blast_radius(before: dict[str, float], after: dict[str, float], root: Path | None = None) -> list[str]:
    """Files whose mtime changed (or that appeared) between two snapshots."""
    changed = sorted(k for k, v in after.items() if before.get(k) != v)
    if root is not None:
        prefix = str(root) + "/"
        changed = [k[len(prefix):] if k.startswith(prefix) else k for k in changed]
    return changed


class FireReporter:
    """Writes one JSON report per fire into ``<dir>/fires/``."""

    def __init__(self, directory: Path):
        self.dir = Path(directory) / "fires"

    def write(self, outcome: Outcome, extra: dict | None = None) -> Path | None:
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            report = {
                "time": outcome.when.strftime("%Y-%m-%d %H:%M"),
                "action_class": outcome.action_class.value,
                "phase1_feel": outcome.phase1_feel,
                "phase2_realize": outcome.phase2_realize,
                "phase3_raw": outcome.phase3_raw,
                "memory": outcome.artifacts.memory,
                "keep": (outcome.artifacts.keep or [None])[0],
                "blast_radius": outcome.blast_radius,
            }
            if extra:
                report.update(extra)
            path = self.dir / f"{outcome.when:%Y-%m-%d-%H%M}.json"
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            return path
        except Exception:  # noqa: BLE001
            return None
