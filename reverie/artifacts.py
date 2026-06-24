"""Envelope parsing and safe artifact persistence.

The agent returns its result wrapped in ``<<TAG>>...<<END>>`` markers. The
runtime, never the model, parses those markers and performs the writes. This
separation is a safety property: a hallucinated path, an empty filename, or a
path-traversal attempt cannot do anything, because the model never holds the
file handle. ``ArtifactWriter`` additionally clamps every keepsake write inside
the scratch directory via a resolved-path containment check.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .types import Artifacts

_TAG_RE = {
    "journal": re.compile(r"<<JOURNAL>>(.*?)<<END>>", re.S),
    "memory": re.compile(r"<<MEMORY>>(.*?)<<END>>", re.S),
    "activity": re.compile(r"<<ACTIVITY>>(.*?)<<END>>", re.S),
    "note": re.compile(r"<<NOTE>>(.*?)<<END>>", re.S),
}
_KEEP_RE = re.compile(r"<<KEEP:(.*?)>>(.*?)<<END>>", re.S)


def parse_envelope(text: str) -> Artifacts:
    """Extract the structured artifacts from a phase-3 response.

    Missing tags simply yield empty fields, so a partial or sloppy response still
    parses without raising.
    """

    def grab(key: str) -> str:
        m = _TAG_RE[key].search(text)
        return m.group(1).strip() if m else ""

    keep_m = _KEEP_RE.search(text)
    keep = (keep_m.group(1).strip(), keep_m.group(2).strip()) if keep_m else None
    return Artifacts(
        journal=grab("journal"),
        memory=grab("memory"),
        activity=grab("activity"),
        note=grab("note"),
        keep=keep,
    )


class ArtifactWriter:
    """Persists artifacts to a sandbox directory. Every write is isolated so a
    single failure never loses the rest; the keepsake write is path-guarded."""

    def __init__(self, sandbox: Path):
        self.sandbox = Path(sandbox)
        self.journal_dir = self.sandbox / "journal"
        self.box_dir = self.sandbox / "box"
        self.memory_file = self.sandbox / "IDLE_MEMORY.md"
        self.activity_file = self.sandbox / "activity.json"
        self.note_file = self.sandbox / "staged_note.txt"

    def write(self, art: Artifacts, raw: str, action_class: str, now: datetime) -> list[str]:
        """Write all present artifacts. Returns a list of non-fatal error strings
        (empty if everything succeeded)."""
        errors: list[str] = []

        try:
            self.journal_dir.mkdir(parents=True, exist_ok=True)
            body = art.journal or raw
            (self.journal_dir / f"{now:%Y-%m-%d-%H%M}.md").write_text(
                f"# {now:%Y-%m-%d %H:%M} - idle ({action_class})\n\n{body}\n", encoding="utf-8"
            )
        except Exception as e:  # noqa: BLE001
            errors.append(f"journal: {e}")

        if art.memory.strip():
            try:
                existing = self.memory_file.read_text(encoding="utf-8") if self.memory_file.exists() else ""
                if art.memory not in existing:  # dedup against any session self-write
                    with open(self.memory_file, "a", encoding="utf-8") as f:
                        f.write(f"\n{now:%Y-%m-%d %H:%M} - {art.memory}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"memory: {e}")

        if art.keep:
            err = self._write_keep(*art.keep)
            if err:
                errors.append(err)

        try:
            import json

            data = json.loads(self.activity_file.read_text()) if self.activity_file.exists() else {}
            data["last_idle"] = art.activity or f"idle ({action_class})"
            data["ts"] = int(now.timestamp())
            self.activity_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            errors.append(f"activity: {e}")

        if art.note.strip():
            try:
                self.note_file.write_text(art.note, encoding="utf-8")
            except Exception as e:  # noqa: BLE001
                errors.append(f"note: {e}")

        return errors

    def _write_keep(self, filename: str, body: str) -> str:
        """Write a keepsake, clamped strictly inside the box directory."""
        name = Path(str(filename)).name.strip()  # strip any directory components
        if not name or not body.strip():
            return f"keep: empty name or body (name={filename!r})"
        if not name.endswith((".md", ".txt")):
            name += ".md"
        target = (self.box_dir / name).resolve()
        box = self.box_dir.resolve()
        # Must be strictly inside the box, never the box dir itself.
        if target == box or not str(target).startswith(str(box) + "/"):
            return f"keep: unsafe path {target} (name={filename!r})"
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
            return ""
        except Exception as e:  # noqa: BLE001
            return f"keep: {e}"
