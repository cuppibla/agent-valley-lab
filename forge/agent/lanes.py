"""The two agents the valley actually runs.

Both are `character_forge` with the tool list narrowed to one. Same instruction,
same five callbacks, same everything else — the only difference is what each one
is allowed to do:

    summoner  tools=[cast_candidates]   ← the ▲ Summon screen
    dresser   tools=[generate_look]     ← the request box on the forge screen

Narrowing to one tool is not a limitation, it is the point: an agent's tool list
is the complete list of what it can do, so a lane that must never re-summon simply
is not given the ability to. That is a stronger guarantee than asking it not to.

`character_forge.py` keeps all three and stays the reference the codelab diffs
against.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from .callbacks import (after_model, after_tool, before_agent, before_model,
                        before_tool)
from .tools import cast_candidates, generate_look

MODEL = "gemini-3-flash-preview"

_SUMMON = """
You run the forge in the Summoning Grove. A traveler describes what they are
looking for; you draw it.

Call cast_candidates with a vivid description of what they asked for. Whatever
they describe, what comes out is always a CUTE ANIMAL familiar — never a person.

Then say ONE warm sentence. Never print the tool's result.
"""

_DRESS = """
You dress a familiar that already exists. The traveler asks for a look; you render it.

Call generate_look with the form they asked for, as a short noun phrase
("a golden crown", "a starry cape"). Never call it more than once per request.

Never invent a new creature — you are changing an outfit, not a character.
Character card: {character_sheet?}

Then say ONE warm sentence. Never print the tool's result.
"""


def _lane(name: str, instruction: str, tool) -> LlmAgent:
    return LlmAgent(
        name=name, model=MODEL, instruction=instruction, tools=[tool],
        before_agent_callback=before_agent,
        before_model_callback=before_model,
        before_tool_callback=before_tool,
        after_tool_callback=after_tool,
        after_model_callback=after_model,
    )


summoner = _lane("summoner", _SUMMON, cast_candidates)
dresser = _lane("dresser", _DRESS, generate_look)
