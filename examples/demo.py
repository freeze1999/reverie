#!/usr/bin/env python3
"""End-to-end demo, runs with NO API key, using the deterministic MockBackend.

It drives the engine three times to show each routing branch:

    1. TEXT_ONLY , the agent reflects and writes a journal entry from its head.
    2. NEEDS_TOOL, the agent decides on an action that needs the world, and a
                    (fake) tool backend executes it.
    3. NOTHING   , the agent decides, legitimately, to do nothing.

Run:  python examples/demo.py
To run against a real model instead, see the OpenAICompatBackend note at the end.
"""
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reverie import (  # noqa: E402
    ArtifactWriter,
    CallableToolBackend,
    ContextBuilder,
    MockBackend,
    ReverieEngine,
    static_source,
)

PERSONA = (
    "You are a long-lived assistant with your own working memory. You think for "
    "yourself when no one is talking to you. You are honest about what you can and "
    "cannot do."
)


def make_engine(scripted, tool_fn=None):
    context = ContextBuilder(
        sources=[
            static_source(
                recent_activity="the principal was wrestling with a citation they couldn't place",
                weather="29C, thunderstorm",
            )
        ],
        tools="web_search, read_file, write_file",
        scratch_index=lambda: "(empty)",
    )
    kwargs = {}
    if tool_fn:
        kwargs["tool_backend"] = CallableToolBackend(tool_fn)
    return ReverieEngine(llm=MockBackend(scripted), context_builder=context, persona=PERSONA, **kwargs)


def show(title, outcome, writer):
    print("\n" + "=" * 70)
    print(f"{title}  ->  {outcome.action_class.value}")
    print("=" * 70)
    print("\n[1] FEEL\n   " + outcome.phase1_feel)
    print("\n[2] REALIZE / FIREWALL\n   " + outcome.phase2_realize)
    print("\n[3] EXECUTE (raw)\n   " + outcome.phase3_raw[:400])
    errs = writer.write(outcome.artifacts, outcome.phase3_raw, outcome.action_class.value, outcome.when)
    print(f"\n   artifacts written (errors: {errs or 'none'})")


def main():
    sandbox = Path(tempfile.mkdtemp(prefix="reverie-demo-"))
    writer = ArtifactWriter(sandbox)
    now = datetime(2026, 6, 21, 14, 0)
    print(f"sandbox: {sandbox}")

    # 1) TEXT_ONLY
    e1 = make_engine(
        {
            "look outward": "I keep thinking about that citation they couldn't place. I also just want to write.",
            "come back down": "Without any way to act on that this round, I'll just write. TODO: a short reflection on unfinished questions.",
            "What you wanted to do": (
                "<<JOURNAL>>Some questions are better left open overnight; "
                "the mind keeps working on them.<<END>>"
                "<<MEMORY>>The principal had an unplaceable citation today.<<END>>"
                "<<ACTIVITY>>wrote a short reflection<<END>>"
                "<<NOTE>>thinking about your citation - will dig in next time I have search<<END>>"
            ),
        }
    )
    show("REFLECTION", e1.run(now), writer)
    now = now.replace(minute=10)

    # 2) NEEDS_TOOL
    def fake_tool(directive):
        return (
            "<<JOURNAL>>Searched and found the citation: Newell & Simon, 1976.<<END>>"
            "<<MEMORY>>The unplaceable citation was Newell & Simon (1976).<<END>>"
            "<<NOTE>>found it - it was Newell & Simon 1976<<END>>"
        )

    e2 = make_engine(
        {
            "look outward": "I should just find that citation for them.",
            "come back down": "TODO: search the web for the citation they were missing.",
        },
        tool_fn=fake_tool,
    )
    show("REAL WORK", e2.run(now), writer)
    now = now.replace(minute=20)

    # 3) NOTHING
    e3 = make_engine(
        {
            "look outward": "Honestly, things are calm and there's nothing pressing.",
            "come back down": "Nothing this time. Resting is a valid choice.",
        }
    )
    show("RESTRAINT", e3.run(now), writer)

    print("\n" + "-" * 70)
    print("journals written:")
    for p in sorted((sandbox / "journal").glob("*.md")):
        print("  -", p.name)
    print("\nTo use a real model, swap MockBackend for OpenAICompatBackend and set")
    print("  REVERIE_LLM_BASE_URL / REVERIE_LLM_API_KEY / REVERIE_LLM_MODEL.")


if __name__ == "__main__":
    main()
