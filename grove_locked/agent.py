"""grove_locked — `grove`, plus the third tool and the five callbacks.

Same model, same instruction, same first two tools. What it adds is the whole
rest of the chapter: `generate_look`, and the five lifecycle callbacks that pin
the canon image to every render so the familiar keeps its face.

It is a re-export, not a copy — the agent is `forge/agent/character_forge.py`,
byte for byte the finished one. This package exists for one reason: `adk web`
lists a directory as an app when that directory has an `agent.py`, so putting
one here puts the finished agent in the app picker next to `grove`. Run the same
request against both and the difference is the lesson.
"""
from __future__ import annotations

from forge.agent.character_forge import root_agent

__all__ = ["root_agent"]
