# Architecture

This document explains the design decisions behind reverie in more depth than
the README. It is written for a reader evaluating the *ideas*, not just the API.

## The premise

Most "autonomous agent" systems treat idle time as a problem of *scheduling*:
given a clock, fire some background work. That framing pushes all the interesting
decisions out of the model and into a static configuration, a list of cron jobs,
a behaviour tree, an NPC-style table of "when bored, do X". The agent does not
decide anything; it is dispatched.

reverie inverts this. The only thing the schedule decides is *when the agent is
allowed to think*. **What** it does is a reasoning problem handed to the model,
under constraints. The hypothesis is that an agent which reasons about its idle
state, rather than executing a script, produces behaviour that is (a) coherent
with its identity and recent history, and (b) honest about its own limits,
because honesty can be made part of the reasoning rather than bolted on after.

## Two layers, on purpose

The system is split into a **gate** (cheap, deterministic, model-free) and a
**reasoning core** (expensive, model-driven). This split is the central
engineering decision.

The gate exists because an always-on loop that calls a model on every tick is
both costly and socially wrong, an agent that interjects every ten minutes is a
nuisance regardless of how good each interjection is. By pushing every "should I
even act" guarantee into a pure function, those guarantees become:

* **cheap**: no tokens spent to decide *not* to act, which is the common case;
* **testable**: `decide()` takes a time, a timestamp, a boolean and some state,
  and returns a decision. No clock, no database, no network. The test suite
  enumerates the window edges, the idle threshold, the re-arm logic, and the
  midnight-wrapping window directly.

### Fire-once-per-gap

The subtlest gate invariant is that the agent fires *at most once per idle gap*
and re-arms only on a new external input. Without it, a single long silence would
satisfy "idle > threshold" on every subsequent tick and fire repeatedly. The
implementation records the input timestamp a fire *consumed*; the next fire is
only permitted when a strictly newer input has arrived. This makes "the human
went to sleep" produce exactly one reverie, not one every ten minutes until
morning.

Crash-safety is layered on in the runner: the arming state is persisted *before*
the engine runs, so a crash mid-fire cannot replay the same gap.

## The three phases

The reasoning core is three prompts, run in sequence, sharing the agent's persona
as the system prompt so it reasons *as itself*.

### Phase 1: FEEL

The agent looks at its working context (recent activity, its own idle history,
its scratch box) and names what it actually wants to do, *before* judging
feasibility. The deliberate instruction to "name the real impulse first; whether
you can comes next" separates *desire* from *capability*, which is what makes the
next phase meaningful. A context that is too thin produces shallow, repetitive
reflection; the [`ContextBuilder`](../reverie/context.py) is therefore "generous
but curated", enough working memory to spark real action, with deeper recall
deferred to tools in phase 3.

### Phase 2: REALIZE (the capability firewall)

This is the load-bearing phase. The impulse from phase 1 is forced through the
agent's real affordances:

* can do it → name the tool;
* can't do it → say so, honestly, without pretending;
* same intent, reachable by other means → substitute the version it can do.

Two things fall out of this. First, *behaviour stays grounded*: a wish to "check
on" someone becomes "read the note they left", because that is the reachable
form. Second, **"do nothing" becomes a first-class outcome.** An agent that is
never allowed to conclude "nothing worth doing this time" will manufacture
busywork; making restraint an explicit, respected option is what keeps an
always-on agent from becoming noise.

The firewall is also the primary defence against confabulation. A persistent
agent is uniquely vulnerable to fabrication because its mistakes are *durable* , 
an invented fact written to long-term memory is later recalled as truth. By
making "I can't" a sanctioned answer at the point where capability is assessed,
the system removes the pressure that pushes a model toward inventing a capability
or a result it does not have.

### Phase 3: EXECUTE (routed)

The class of action is inferred from phase 2 and routes execution three ways:

* **NOTHING**: no further model call; the reflection is recorded and the cycle
  ends.
* **NEEDS_TOOL**: the action reads or changes the world, so it runs through a
  real tool-enabled session. Grounding in real tool results is itself an
  anti-fabrication measure: the model reports what the tools returned instead of
  imagining what they might.
* **TEXT_ONLY**: pure reflection from the agent's own head, a single cheap call,
  under an explicit contract never to fabricate results, numbers, files, or the
  principal's inner state.

Routing by need keeps the common case cheap while still permitting real work when
the agent decides real work is warranted.

#### A note on the classifier

`classify()` is a transparent keyword heuristic, and it is intentionally biased:
when in doubt it prefers the grounded tool path over the text-only path, because
the cost of a wrong "use tools" is a wasted session, while the cost of a wrong
"reflect only" is an invented result. Keyword classification is *fragile*, a
phase-2 sentence that merely mentions "search" while saying it *cannot* search
will trip it, and that fragility is exactly why the firewall, not the
classifier, is treated as the real safeguard. A production deployment can replace
`classify()` with an explicit decision token emitted by phase 2 without touching
the rest of the engine.

## Structured output, runtime-owned writes

Phase 3 returns its result inside an envelope of `<<TAG>>...<<END>>` markers. The
runtime, never the model, parses those markers and performs the writes. This is
a security boundary: a hallucinated path, an empty filename, or a traversal
attempt cannot do anything because the model never holds a file handle. The
keepsake writer additionally clamps every write inside the scratch directory via
a resolved-path containment check, and each artifact write is isolated so one
failure never loses the rest.

## Observability over containment

The final stance concerns a self-acting agent's capacity to change things , 
including itself. reverie deliberately does *not* sandbox the agent away from its
own code. The argument is that an idle agent reasoning as itself is the same
agent that does useful work when spoken to; caging the idle version degrades the
whole. Instead, every fire is made fully auditable: a JSON report captures the
complete reasoning trace, and a **blast radius**, an mtime diff over a watch set
of files the agent should not normally touch, flags any unexpected change. The
governance is *after the fact and visible*, not *before the fact and restrictive*.

## What is intentionally left out

* **No bundled persistence.** `last_input_ts` and `is_available` are callables;
  wire them to whatever store you have. The framework does not assume a database.
* **No bundled tool runtime.** The tool backend is an interface. Connect it to an
  existing agent session; reverie does not reimplement one.
* **No provider lock-in.** The only model dependency is an OpenAI-compatible
  chat-completions shape, behind a one-method protocol.

These omissions keep the project a faithful reference for the *idea*, idle time
as reasoning under a cheap gate, rather than a platform that buries the idea in
infrastructure.
