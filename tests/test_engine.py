"""Routing and the full feel -> realize -> execute loop, driven by MockBackend."""
from datetime import datetime

from reverie import (
    ActionClass,
    CallableToolBackend,
    ContextBuilder,
    MockBackend,
    ReverieEngine,
    classify,
    static_source,
)


def test_classify_nothing():
    assert classify("On reflection, nothing this time.") is ActionClass.NOTHING


def test_classify_needs_tool():
    assert classify("TODO: search the web for the citation.") is ActionClass.NEEDS_TOOL


def test_classify_text_only():
    assert classify("TODO: write a short reflection on the day.") is ActionClass.TEXT_ONLY


def _engine(scripted, tool_fn=None):
    cb = ContextBuilder(
        sources=[static_source(mood="quiet")],
        tools="web_search, read_file, write_file",
        scratch_index=lambda: "(empty)",
    )
    kwargs = {}
    if tool_fn is not None:
        kwargs["tool_backend"] = CallableToolBackend(tool_fn)
    return ReverieEngine(llm=MockBackend(scripted), context_builder=cb, persona="You are a test agent.", **kwargs)


def test_text_only_path_runs_three_calls():
    eng = _engine(
        {
            "look outward": "I feel like writing.",            # phase 1
            "come back down": "TODO: write a short reflection.",  # phase 2 (text-only)
            "What you wanted to do": "<<JOURNAL>>a reflection<<END>><<ACTIVITY>>wrote<<END>>",  # phase 3 text
        }
    )
    out = eng.run(datetime(2026, 6, 21, 14, 0))
    assert out.action_class is ActionClass.TEXT_ONLY
    assert out.artifacts.journal == "a reflection"
    assert len(eng.llm.calls) == 3  # feel, realize, execute(text)


def test_nothing_path_runs_two_calls():
    eng = _engine(
        {
            "look outward": "I'm content.",
            "come back down": "Nothing this time.",
        }
    )
    out = eng.run()
    assert out.action_class is ActionClass.NOTHING
    assert out.artifacts.memory == "nothing this time"
    assert len(eng.llm.calls) == 2  # no phase-3 model call


def test_needs_tool_path_uses_tool_backend():
    seen = {}

    def fake_tool(directive: str) -> str:
        seen["directive"] = directive
        return "<<JOURNAL>>searched and found it<<END>><<MEMORY>>citation X confirmed<<END>>"

    eng = _engine(
        {
            "look outward": "I want to verify that citation.",
            "come back down": "TODO: search the web for the citation.",
        },
        tool_fn=fake_tool,
    )
    out = eng.run()
    assert out.action_class is ActionClass.NEEDS_TOOL
    assert out.artifacts.memory == "citation X confirmed"
    # The directive is tagged so a real deployment won't re-arm the idle clock.
    assert seen["directive"].startswith("[REVERIE] ")
    # Only feel + realize go to the LLM; execution went to the tool backend.
    assert len(eng.llm.calls) == 2
