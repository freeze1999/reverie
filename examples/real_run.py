#!/usr/bin/env python3
"""Run one real idle fire against a live OpenAI-compatible endpoint.

Unlike ``demo.py`` (which uses the deterministic mock), this calls a real model,
so you can see the actual feel -> realize -> execute reasoning. It uses the
text-only path by default (no tool backend wired), which is the most portable: it
runs anywhere with just an API key, and it is also where the capability firewall
is most visible, the agent must honestly downgrade an impulse it cannot act on
instead of fabricating a result.

Configure via environment:
    REVERIE_LLM_BASE_URL   e.g. https://api.openai.com/v1  |  https://api.deepseek.com/v1
    REVERIE_LLM_API_KEY    your key (never hard-code it)
    REVERIE_LLM_MODEL      e.g. gpt-4o-mini  |  deepseek-v4-pro  |  ...

Run:  python examples/real_run.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reverie import (  # noqa: E402
    ContextBuilder,
    OpenAICompatBackend,
    ReverieEngine,
    static_source,
)

PERSONA = (
    "You are a long-lived assistant with your own persistent working memory. "
    "When no one is talking to you, you think for yourself. You are honest about "
    "what you can and cannot do, and you never invent facts, results, or how the "
    "principal feels."
)


def main():
    if not os.environ.get("REVERIE_LLM_API_KEY"):
        sys.exit("Set REVERIE_LLM_API_KEY (and optionally _BASE_URL / _MODEL) first.")

    engine = ReverieEngine(
        llm=OpenAICompatBackend(),
        context_builder=ContextBuilder(
            sources=[
                static_source(
                    recent_activity=(
                        "earlier the principal was fighting a flaky integration test, got "
                        "frustrated, and stopped without finding the cause; then went quiet"
                    ),
                    note="it is late and calm; nothing was explicitly asked of you",
                )
            ],
            tools="web_search, read_file, write_file",
            scratch_index=lambda: "(empty)",
        ),
        persona=PERSONA,
    )

    out = engine.run(datetime.now())
    print("ACTION CLASS:", out.action_class.value)
    print("\n=== PHASE 1, FEEL ===\n" + out.phase1_feel)
    print("\n=== PHASE 2, REALIZE / FIREWALL ===\n" + out.phase2_realize)
    print("\n=== PHASE 3, EXECUTE ===\n" + out.phase3_raw)


if __name__ == "__main__":
    main()
