"""grove — a model, and the two lines that give it hands.

Right now this agent has no tools. It can talk about summoning a familiar; it
cannot summon one. The tools are imported directly below — sitting in the file,
one line away. Having a function in your codebase is not the same as giving it
to the model.

There are two edits in this lab and they are both one line:

    EDIT ONE (chapter 2)  give it ONE tool, and watch what a tool call is
    EDIT TWO (chapter 3)  add a SECOND one, and find out how the two talk

Nothing else in this file changes.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

# Two of the three tools the valley's buttons call.
#   cast_candidates(description) → a portrait of what they described
#   lock_candidate(index, name)  → make one canon (spends no model — a pure state write)
#
# The third, generate_look(form), needs a callback to keep the same face, so it
# stays where that callback lives: the app, and chapter 5.
from forge.agent.tools import cast_candidates, lock_candidate

INSTRUCTION = """
You keep the forge in the Summoning Grove, in Agent Valley.

A traveler tells you what they are looking for. Whatever they describe, what
comes out of the forge is always a CUTE ANIMAL familiar — a banker becomes a
smug little badger in a waistcoat, a heavy-metal drummer becomes a tiny bear
with wild fur. Never a person.

Be brief and warm. One or two lines.
"""

root_agent = LlmAgent(
    name="grove",
    model="gemini-3-flash-preview",
    description="The forge in the Summoning Grove — turns a description into a familiar.",
    instruction=INSTRUCTION,

    # 👉 EDIT ONE (chapter 2) — delete the "# " at the start of the next line,
    #    then save, then restart adk web (Ctrl+C, ↑, Enter) and ask again.
    #
    #    EDIT TWO comes in chapter 3: you will add one more name inside those
    #    brackets. That is the whole lab.
    # tools=[cast_candidates],
)
