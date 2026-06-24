# reverie

**A reasoning-first idle engine for persistent LLM agents.**

[![CI](https://github.com/freeze1999/reverie/actions/workflows/ci.yml/badge.svg)](https://github.com/freeze1999/reverie/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](pyproject.toml)

When a long-lived agent is left alone, no message to answer, no task queued , 
what should it do? The usual answer is a *scheduler*: a table of background jobs
that fire on a timer. reverie takes a different stance. The agent **reasons**
about its own idle time, what it notices, what it wants, what it can actually
do, and its behaviour *emerges* from that reasoning. A cheap, model-free gate
sits in front so an always-on loop never burns budget or spams.

The interesting claim is small but specific: **the same machinery that makes an
agent useful when spoken to can make it coherent when it is not.** Idle time is
treated as a first-class cognitive state, not dead air to be filled with scripts.

```
                          every ~10 min (cron / timer)
                                     │
                          ┌──────────▼───────────┐
                          │        GATE          │   no LLM, pure function
                          │  available? window?  │   fully unit-tested
                          │  idle>θ? armed?      │
                          └──────────┬───────────┘
                            fire? ───┘ (at most once per idle gap)
                                     │ yes
        ┌────────────────────────────▼────────────────────────────┐
        │                      REASONING CORE                      │
        │                                                          │
        │   (1) FEEL ───────► given all I can see, what do I       │
        │                     actually want to do?                 │
        │                                                          │
        │   (2) REALIZE ────► I have no body. Of those wants,      │
        │       (firewall)    which can I really act on? Which     │
        │                     can't I, and can I admit that       │
        │                     instead of pretending?              │
        │                                                          │
        │   (3) EXECUTE ────► route by what the action needs:      │
        │                       nothing · tools · reflection       │
        └────────────────────────────┬────────────────────────────┘
                                      │
                  structured envelope (runtime owns the writes)
                                      │
              journal · memory · keepsake · activity · note
                                      │
                       per-fire report  +  blast radius
```

## Why this design

Three problems show up the moment you let an agent act on its own. reverie is
organized around them.

**1. Cost & nuisance, solved by the gate, not the model.**
An always-on agent that thinks on every tick is both expensive and annoying. So
the decision *whether* to act is made by a pure function with no model call and
no side effects ([`gate.py`](reverie/gate.py)). It enforces a working window
(which may wrap past midnight), an idle threshold, an availability check, and , 
the load-bearing one, **fire-once-per-idle-gap**: the agent acts at most once
per silence and re-arms only when a genuinely new input arrives. Because it is
pure, every guarantee is exhaustively unit-tested without a clock or a network.

**2. Confabulation, solved by a capability firewall.**
The failure that most damages a *persistent* agent is fabrication: a single
invented "fact" written to durable memory is recalled forever as if true. The
middle phase, **REALIZE**, exists to catch this. It forces every impulse through
the agent's real affordances, *"I want to check on them" → "I can't see them; I
can read the notes they left"*, and explicitly licenses the model to say **"I
can't"** rather than confabulate a capability. The execute prompts repeat the
contract: get real results, never invent a number, file, link, or the principal's
inner state. When an action needs the world, it runs through real tools (grounded
results) rather than the text-only path (where a model is tempted to imagine the
results instead).

**3. Self-modification, met with observability, not a cage.**
An agent with real tools can change things you didn't anticipate, including its
own code. reverie does not forbid this; it makes every fire auditable. Each fire
writes a full reasoning trace (feel / realize / execute) and a **blast radius**:
an mtime diff over a watch set of files the agent is *not* normally expected to
touch. Unexpected edits surface loudly instead of silently.

## Quickstart

No API key required, the demo runs on a deterministic mock backend.

```bash
git clone https://github.com/freeze1999/reverie
cd reverie
python examples/demo.py        # runs the full feel→realize→execute loop x3
python -m pytest -q            # 25 tests, ~0.1s, no network
```

Minimal real usage:

```python
from reverie import ContextBuilder, ReverieEngine, OpenAICompatBackend, static_source

engine = ReverieEngine(
    llm=OpenAICompatBackend(),  # reads REVERIE_LLM_BASE_URL / _API_KEY / _MODEL
    context_builder=ContextBuilder(
        sources=[static_source(recent_activity="...")],
        tools="web_search, read_file, write_file",
    ),
    persona="You are a long-lived assistant with your own working memory ...",
)
outcome = engine.run()
print(outcome.action_class, outcome.artifacts.journal)
```

Deploying it as an actual idle loop (cron every 10 minutes):

```python
from reverie import Runner
runner = Runner(
    engine=engine,
    state_dir="run_state/",
    last_input_ts=lambda: my_db_last_user_message_ts(),
    is_available=lambda: not currently_busy(),
)
runner.tick()   # gate decides; only fires when it should
```

`OpenAICompatBackend` speaks to any OpenAI-compatible `/chat/completions`
endpoint, OpenAI, DeepSeek, Together, OpenRouter, or a local vLLM/Ollama.

## Layout

| Module | Responsibility |
|---|---|
| [`gate.py`](reverie/gate.py) | The model-free decision: fire this tick? Pure, fully tested. |
| [`engine.py`](reverie/engine.py) | The feel → realize → execute reasoning core and routing. |
| [`prompts.py`](reverie/prompts.py) | The three phase prompts, incl. the capability firewall. |
| [`context.py`](reverie/context.py) | Best-effort assembly of the working context. |
| [`artifacts.py`](reverie/artifacts.py) | Envelope parsing + sandboxed, path-guarded writes. |
| [`observability.py`](reverie/observability.py) | Per-fire reports and blast radius. |
| [`llm.py`](reverie/llm.py) | Provider-agnostic LLM + tool backends (mock & real). |
| [`runner.py`](reverie/runner.py) | Gate + persistence glue for a scheduler entrypoint. |

A deeper design discussion is in [`docs/architecture.md`](docs/architecture.md), and
real (unedited) model output from both routing branches is in
[`docs/example-transcript.md`](docs/example-transcript.md).

## Status & scope

This is a clean-room, single-purpose framework extracted and generalized from a
running deployment. It is provider-agnostic, dependency-free at its core (Python
standard library only; `pytest` for the tests), and intended as a reference
implementation of the idea rather than a batteries-included platform. The tool
backend is deliberately an interface: wire it to whatever agent runtime you
already have.

## License

MIT, see [LICENSE](LICENSE).
