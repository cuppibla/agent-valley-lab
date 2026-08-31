"""grove_flow_adk1 — the SAME graph, written the ADK 1.x way, for comparison.

Two nodes in a fixed order, and no model anywhere:

    parse  →  summon

`parse` is an input gate you wrote: it accepts `species, palette` and nothing
else. `summon` calls the same render the agent calls. There is no decision in
this file — the graph was decided when it was written, and it runs exactly this
way every time, including when it fails.

In 1.x the unit of orchestration was the AGENT. To get two steps in a row you
reached for a container agent (`SequentialAgent`) and filled it with sub-agents;
anything that wasn't an LLM had to be smuggled in as a `BaseAgent` subclass with
an `_run_async_impl` generator, and the two steps talked through `session.state`.

Open `grove_flow/agent.py` next to this file. Same two steps, same tool, same
result — a third of the code, and no classes at all. That is the 2.0 change:
**the unit stopped being the agent and became the node.**
"""

from __future__ import annotations

from typing import AsyncGenerator

from google.adk.agents import BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from forge.agent.backends import shrink
from forge.agent.tools import render_look

SPECIES = ["fox", "cat", "owl", "dragon", "deer", "bunny"]
PALETTES = ["autumn", "moonlit", "dawn", "storm", "sage"]


def _said(ctx: InvocationContext) -> str:
    """The traveler's line, whatever ADK version is underneath."""
    content = getattr(ctx, "user_content", None)
    if content is None:
        for event in reversed(getattr(ctx.session, "events", []) or []):
            if getattr(event, "author", "") == "user" and event.content:
                content = event.content
                break
    parts = getattr(content, "parts", None) or []
    return " ".join(p.text for p in parts if getattr(p, "text", None)).strip()


def _text(node: str, body: str, actions: EventActions | None = None) -> Event:
    return Event(
        author=node,
        content=types.Content(role="model", parts=[types.Part(text=body)]),
        actions=actions or EventActions(),
    )


class Parse(BaseAgent):
    """Node 1 — the input gate. Two fields, spelled the way the code expects."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        said = _said(ctx).lower()
        species, _, palette = said.partition(",")
        species, palette = species.strip(), palette.strip()

        if species not in SPECIES:
            # Blank lines, not single newlines: the dev UI renders this as markdown.
            # Angle brackets would be eaten as tags, so the usage line uses backticks.
            yield _text(
                self.name,
                f"✗ unknown species: `{species or '(empty)'}`\n\n"
                f"expected one of: {', '.join(SPECIES)}\n\n"
                f"usage: `species, palette` — for example `fox, autumn`",
                EventActions(state_delta={"parsed": None}),
            )
            return

        if palette not in PALETTES:
            palette = PALETTES[0]

        yield _text(
            self.name,
            f"✓ species={species}  palette={palette}",
            EventActions(state_delta={"parsed": {"species": species, "palette": palette}}),
        )


class Summon(BaseAgent):
    """Node 2 — always runs, because the graph says so."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        parsed = ctx.session.state.get("parsed")
        if not parsed:
            yield _text(self.name, "— nothing to summon (node 1 rejected the input)")
            return

        png, _meta = render_look(
            sheet=f"a {parsed['palette']} {parsed['species']}",
            form="base portrait",
            reference_seed=f"flow-{parsed['species']}",
        )
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[
                    types.Part(inline_data=types.Blob(mime_type="image/jpeg", data=shrink(png))),
                    types.Part(text=f"summoned: {parsed['palette']} {parsed['species']}"),
                ],
            ),
        )


root_agent = SequentialAgent(
    name="grove_flow_adk1",
    description="A fixed two-node pipeline: parse the input, then summon.",
    sub_agents=[Parse(name="parse"), Summon(name="summon")],
)
