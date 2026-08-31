"""grove_flow — two agents, wired together. One of them has a tool.

    START ──▶ describe ──▶ forge ──▶ (answer)
              (agent)      (agent)
                             └── cast_candidates  (tool)

Nothing here is new. `Agent(...)` is the thing you built in chapter 1.
`tools=[cast_candidates]` is the line you uncommented in chapter 2. This chapter
is only about the arrow between them.

What `describe` says comes out of its mouth and goes straight in as `forge`'s
input — you will see its sentence appear, word for word, as the argument `forge`
passes to the tool. Nobody wrote code to move it. It travelled the edge.

That is the difference worth holding on to:

    agent ↔ tool   share a dictionary   (tool_context.state)
    node  ↔ node   hand over a value    (along the edge)

One is a room everyone can reach into. The other is a baton.

Try:  something cozy that likes rain and drinks tea
"""

from __future__ import annotations

from google.adk import Agent, Workflow

from forge.agent.tools import cast_candidates

# ── node 1 ───────────────────────────────────────────────────────────────────
# An ordinary agent with no tools — exactly chapter 1. All it does is turn a
# vague human sentence into one clean description.
describe = Agent(
    name="describe",
    model="gemini-3-flash-preview",
    instruction=(
        "Turn whatever the traveler says into ONE short, vivid description of a "
        "cute animal familiar — species, colours, mood. Whatever they describe, it "
        "is always an animal, never a person.\n\n"
        "Reply with the description and nothing else. No greeting, no explanation."
    ),
)

# ── node 2 ───────────────────────────────────────────────────────────────────
# The same agent shape, plus the tool from chapter 2.
forge = Agent(
    name="forge",
    model="gemini-3-flash-preview",
    instruction=(
        "You are handed a description of a familiar. Call cast_candidates with it, "
        "exactly as written.\n\n"
        "Then say ONE warm sentence to the traveler. Never print the tool's result."
    ),
    tools=[cast_candidates],
)

# ── the wire ─────────────────────────────────────────────────────────────────
# One line. START feeds `describe`; whatever `describe` returns feeds `forge`.
root_agent = Workflow(
    name="grove_flow",
    description="Two agents in a row — the second one holds the tool.",
    edges=[("START", describe, forge)],
)
