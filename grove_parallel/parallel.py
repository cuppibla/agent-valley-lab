"""grove_parallel — an aside: running nodes at the same time.

Not part of the main lab path (that is why there is no `agent.py` here — the dev
UI does not list it). Read it, or run it by renaming this file to `agent.py`.


                       ┌──▶ summon_first  ──┐
    START ──▶ parse ───┼──▶ summon_second ──┼──▶ join ──▶ announce
                       └──▶ summon_third  ──┘

Compare the last three lines of this file with the last three of `grove_flow`.
The only difference is that one slot holds a TUPLE instead of a single node —
which is how you say "run these together". A `JoinNode` waits for every branch
before the step after it.

Same functions, same tool, same everything. One line has a different shape, and
three summons now take about as long as one.

Try:  fox, cat, owl
"""

from __future__ import annotations

import asyncio
from typing import Any

from google.adk import Event, Workflow
from google.adk.workflow import JoinNode
from google.genai import types

from forge.agent.backends import shrink
from forge.agent.tools import render_look

# self-contained: grove_flow is two agents now, so this aside keeps its own list
SPECIES = ["fox", "cat", "owl", "dragon", "deer", "bunny"]


def parse_three(node_input: str) -> list[str]:
    """Node 1 — up to three species off one line. A fixed graph needs a fixed
    number of slots, so short input gets padded."""
    picks = [w.strip() for w in node_input.lower().split(",") if w.strip() in SPECIES][:3]
    while len(picks) < 3:
        picks.append(SPECIES[len(picks)])
    return picks


async def _summon(picks: list[str], slot: int):
    species = picks[slot]
    # to_thread, so the three branches really overlap — render_look blocks on a
    # network call, and a blocking node would stall the whole graph.
    png, _meta = await asyncio.to_thread(
        render_look, sheet=f"a {species}", form="base portrait",
        reference_seed=f"parallel-{species}")
    yield Event(message=[
        types.Part.from_text(text=f"summoned: {species}"),
        types.Part.from_bytes(data=shrink(png), mime_type="image/jpeg"),
    ])


# Three nodes, identical but for their slot. All three receive the SAME node_input
# — whatever `parse_three` returned.
async def summon_first(node_input: list[str]):
    async for e in _summon(node_input, 0):
        yield e


async def summon_second(node_input: list[str]):
    async for e in _summon(node_input, 1):
        yield e


async def summon_third(node_input: list[str]):
    async for e in _summon(node_input, 2):
        yield e


join = JoinNode(name="join")


async def announce(node_input: dict[str, Any]):
    """Runs only once every branch above it has finished."""
    yield Event(message=f"all three answered · branches joined: {len(node_input)}")


root_agent = Workflow(
    name="grove_parallel",
    description="Parse one line, then summon three familiars at the same time.",

    edges=[("START", parse_three,
            (summon_first, summon_second, summon_third),
            join, announce)],
)
