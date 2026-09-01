"""root_agent — the Character Forge. A reasoning LlmAgent that drives three tools
through the five control callbacks. `adk web 01-control/agent` chats with it
(needs GOOGLE_API_KEY for the reasoning model + real Nano Banana)."""

from __future__ import annotations

from google.adk.agents import LlmAgent

from .callbacks import (after_model, after_tool, before_agent, before_model,
                        before_tool)
from .tools import cast_candidates, generate_look, lock_candidate

INSTRUCTION = """
You run a game's Character Forge. Help the player create ONE character and try
looks on it, keeping the same face throughout.

Flow:
- To start, call cast_candidates with the player's description → ONE portrait.
- Then call lock_candidate(0, name) — always, right after the portrait exists.
  It is what names the character and makes it canon. Use the name the player
  already gave you; if they gave none, ask for one. There is nothing to pick
  between, so do not wait to be asked.
- For each outfit/armor/form the player asks for, call generate_look with the form.

Never call generate_look before a portrait exists — there is no face to keep yet.
Keep the same character across every look. Never invent a new face.
Character card: {character_sheet?}
"""

root_agent = LlmAgent(
    name="character_forge",
    model="gemini-3-flash-preview",
    description="Creates one game character and transmogs it, holding identity.",
    instruction=INSTRUCTION,
    tools=[cast_candidates, lock_candidate, generate_look],
    before_agent_callback=before_agent,
    before_model_callback=before_model,
    before_tool_callback=before_tool,
    after_tool_callback=after_tool,
    after_model_callback=after_model,
)
