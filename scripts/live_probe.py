"""Live probe — drive grove's real root_agent through ADK and record tool calls.

Not a unit test. This talks to the real reasoning model (gemini-3-flash-preview)
through the same ADK Runner code path `adk web` uses, and prints the *actual*
function call names the model emitted for each turn.

  A101_FAKE_IMAGES=1   keeps the image backend offline so a routing probe costs
                       reasoning tokens only. grove has no callbacks, so the
                       model sees the identical tool-response dict either way.

Usage:
    python scripts/live_probe.py "prompt one" "prompt two" ...
    PROBE_AGENT=grove_locked.agent python scripts/live_probe.py "..."
"""
from __future__ import annotations

import asyncio
import sys

import forge  # settles credentials (Vertex project or API key)

from google.adk.runners import InMemoryRunner
from google.genai import types

import importlib, os
root_agent = importlib.import_module(os.environ.get("PROBE_AGENT", "grove.agent")).root_agent

APP = "grove_probe"
USER = "probe"


async def main(prompts: list[str]) -> None:
    tool_names = [getattr(t, "__name__", str(t)) for t in (root_agent.tools or [])]
    print(f"agent    : {root_agent.name}")
    print(f"model    : {root_agent.model}")
    print(f"tools    : {tool_names or '(none)'}")
    print("=" * 72)

    runner = InMemoryRunner(agent=root_agent, app_name=APP)
    session = await runner.session_service.create_session(app_name=APP, user_id=USER)

    summary: list[tuple[str, list[str]]] = []

    for prompt in prompts:
        print(f"\n>>> USER: {prompt}")
        called: list[str] = []
        try:
            async for event in runner.run_async(
                user_id=USER,
                session_id=session.id,
                new_message=types.Content(role="user", parts=[types.Part(text=prompt)]),
            ):
                for part in (event.content.parts if event.content else []) or []:
                    if part.function_call:
                        called.append(part.function_call.name)
                        print(f"    [TOOL CALL] {part.function_call.name}({part.function_call.args})")
                    if part.function_response:
                        resp = str(part.function_response.response)
                        print(f"    [TOOL RESP] {part.function_response.name} -> {resp[:160]}")
                    if part.text:
                        print(f"    [TEXT] {part.text.strip()}")
                    if part.inline_data:
                        n = len(part.inline_data.data or b"")
                        print(f"    [INLINE {part.inline_data.mime_type} {n}B]")
        except Exception as exc:  # noqa: BLE001 — the hallucination surfaces here
            print(f"    [ERROR] {type(exc).__name__}: {exc}")
            called.append(f"<ERROR {type(exc).__name__}>")
        summary.append((prompt, called))

    print("\n" + "=" * 72)
    print("SUMMARY  prompt -> tool(s) actually called")
    for prompt, called in summary:
        print(f"  {prompt!r:<58} -> {called or ['(no tool call)']}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
