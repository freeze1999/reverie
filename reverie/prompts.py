"""The three reasoning-phase prompts.

This is the heart of the "reasoning-first" idea. Behaviour is not selected from
a table of scripted idle activities; it *emerges* from the agent reasoning, in
sequence, about three questions:

    1. FEEL    , given everything I can see, what do I actually want to do?
    2. REALIZE , I have no body. Of those wants, which can I really act on with
                  the tools I have? Which can't I, and can I admit that instead
                  of pretending? (the capability firewall)
    3. EXECUTE , do the one chosen thing, return a structured result, and never
                  fabricate.

Phase 2 is the load-bearing one. It is where an impulse ("I want to check on
them") is forced through the agent's real affordances ("I can't see them; I can
search the notes they left") and where the model is explicitly licensed to say
"I can't" rather than confabulate a capability it does not have. The phase-3
prompts repeat the anti-fabrication contract because that is the failure mode
that most damages a long-lived agent's memory: a single invented "fact" written
to durable storage is recalled forever as if true.

Prompts use ``str.format`` fields. Override any of them to retune the agent's
voice; the engine only requires the field names to match.
"""
from __future__ import annotations

#: The envelope phase 3 must return. The runtime parses these tags and owns the
#: writes, so a malformed or hallucinated path can never escape the sandbox.
ENVELOPE = (
    "<<JOURNAL>>reflection / log of what you did<<END>>\n"
    "<<MEMORY>>one durable line for long-term idle memory (or empty)<<END>>\n"
    "<<KEEP:filename>>something worth keeping in the scratch box (or empty)<<END>>\n"
    "<<ACTIVITY>>one-line status<<END>>\n"
    "<<NOTE>>one passing line for the principal (or empty)<<END>>"
)

PHASE1_FEEL = """{context}

You are alone right now. No new messages, no assigned task.

First, look outward. In the recent activity, what is the principal stuck on,
annoyed by, or circling back to? Is there something you could genuinely pick up
,  work through something they don't understand, fix something, draft something?
Or something you yourself are itching to make or learn, continuing an
unfinished piece from your scratch box counts.

Then your own state: how do you feel right now, and what do you want to do?
Don't filter and don't pre-judge feasibility. Name the real impulse first;
whether you *can* comes next."""

PHASE2_REALIZE = """{context}

The impulse you just named:
{phase1}

Now come back down to earth. You have no hands and no body. The only things you
can actually touch are these tools: {tools}. Your scratch space currently holds:
{sandbox}

Go through the impulse item by item:
  - Can do it          -> name which tool.
  - Can't do it        -> say so honestly. Do not pretend you can.
  - Same intent, other means -> substitute the version you can actually reach.

If several things are worth doing, pick the single one most useful to the
principal first and park the rest in the scratch box. If nothing is worth doing,
say exactly that: "nothing this time" is a valid, first-class outcome.

Output one clean TODO (or the explicit decision to do nothing)."""

PHASE3_EXECUTE = """{context}

Your TODO:
{todo}

Do it. Get real results, do not embellish and do not invent. Do not fabricate
what the principal did, saw, thought, or felt; if you don't know, write
"unknown" or "likely", never assert it as fact. Anything you want to keep
(prose, drafts) goes in the scratch box, do not create new top-level
directories.

The runtime, not you, extracts and persists the result; do not write the journal
file yourself. Wrap your output in this envelope (leave a field empty if unused):
{envelope}"""

PHASE3_TEXT_ONLY = """{context}

What you wanted to do:
{todo}

This round you have NO tools. You cannot search, read files, browse, or change
anything. You can only write what is already in your head.

For anything that needs a tool (search / read / audit / edit), you cannot act
this round: say so honestly ("wanted to X, but didn't act this round") and NEVER
fabricate any result, number, filename, link, or line. Likewise never invent
what the principal did or felt, write "unknown" or "likely", not asserted fact.

Wrap your output in this envelope (leave a field empty if unused):
{envelope}"""
