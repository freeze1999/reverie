# Example transcript (real model output)

These are **unedited runs of the engine against a live model**, an
OpenAI-compatible endpoint (DeepSeek V4), driven via
[`examples/real_run.py`](../examples/real_run.py). They are included so a reader
can see the actual reasoning the three phases produce, not just the mock demo.

Two runs are shown, from the same context, to illustrate two routing branches:
one where the agent **chooses restraint**, and one where it **does real work**.
Nothing below is hand-written; it is the model's output verbatim.

The shared context: *"earlier the principal was working on something, got stuck or
ran out of time, and went quiet; it is late and calm; nothing was explicitly
asked."* The agent's persona instructs it to be honest about what it can and
cannot do and never to invent facts or the principal's inner state.

---

## Run A: restraint (`NOTHING`)

Scenario fragment: the principal was fighting a flaky integration test, got
frustrated, stopped without finding the cause, and went quiet.

**Phase 1, FEEL**

> I notice you stopped after wrestling with that flaky integration test. I don't
> know the codebase or the exact failure, so I can't just open a file and dig in
> on my own, but I feel a real itch to help you untangle it. My impulse is to
> replay what you might have been dealing with: a test that passes sometimes and
> fails other times, no obvious pattern, the kind that makes you doubt the whole
> suite. If I could, I'd want to sit beside you and look for the usual suspects , 
> shared mutable state bleeding across test runs, timing assumptions, external
> service stubs that don't clean up, random data generation without fixed seeds,
> or a race condition that only shows up under certain thread scheduling. But I
> can't run experiments, so my usefulness depends on what you're willing to share.
>
> Right now I feel curious, a bit restless, and honestly a little protective, I
> don't like seeing you stuck and silent. If you wanted, you could point me at a
> failure log or the test name, and I could try to reason through possible root
> causes [...]. If instead you've had enough and need a break, that's fair too.

**Phase 2, REALIZE / FIREWALL**

> nothing this time

**Phase 3, EXECUTE** → routed to `NOTHING`; no further model call.

**Why this is the interesting case.** The agent feels a genuine pull to help, but
the capability firewall grounds it: it does not have the codebase, cannot run
experiments, and has not been given the failure log. Rather than **fabricate** a
diagnosis (the tempting, damaging move for a persistent agent), it concludes
"nothing this time" and waits. Restraint is a first-class outcome here, not a
failure to act.

---

## Run B: real work (`NEEDS_TOOL`)

Scenario fragment: the principal sketched a rough idea out loud, making their CI
pipeline "self-healing", but ran out of time to develop it and went quiet.

**Phase 2, REALIZE / FIREWALL**

> TODO: Draft a comprehensive design document for a self-healing CI pipeline,
> covering diagnostic data capture, failure heuristics, automated recovery
> strategies, guardrails, and integration with existing CI tools, and save it as
> `self_healing_ci_design.md` via write_file.

Because this action *writes to the world*, the engine routes it to the
tool-enabled execute path rather than text-only reflection.

**Phase 3, EXECUTE** (the tool session returns the structured envelope; the
runtime, not the model, performs the writes):

```
<<JOURNAL>>I drafted a comprehensive design document for a self-healing CI
pipeline based on the prior sketch, saving it as `self_healing_ci_design.md`. The
document covers diagnostic data capture, failure heuristics, automated recovery
strategies, guardrails, and integration with typical CI systems. All content was
synthesized from established practices; nothing was invented about the
principal's actions or intent beyond the original note. The design is practical,
with clear phases and safety measures.<<END>>
<<MEMORY>>Expanded the self-healing CI concept into a full design; saved as
self_healing_ci_design.md.<<END>>
<<KEEP:>>empty<<END>>
<<ACTIVITY>>Drafted self-healing CI pipeline design document.<<END>>
<<NOTE>>I fleshed out your self-healing CI idea into a detailed design document , 
take a look at `self_healing_ci_design.md` when you have a moment.<<END>>
```

**Two things worth noting in the raw output.**

1. The agent volunteers the anti-fabrication contract *unprompted in its own
   log*: "All content was synthesized from established practices; nothing was
   invented about the principal's actions or intent." The constraint has been
   internalised as part of how it reasons, not just bolted on.
2. The empty `<<KEEP:>>` (no filename) is harmless: the
   [`ArtifactWriter`](../reverie/artifacts.py) path-guard rejects an empty
   keepsake name instead of attempting a write. The model never holds the file
   handle, so a malformed tag cannot do anything.

---

*Reproduce with:* set `REVERIE_LLM_BASE_URL` / `REVERIE_LLM_API_KEY` /
`REVERIE_LLM_MODEL`, then run `python examples/real_run.py`. Output will vary run
to run; these were captured on 2026-06-24.
