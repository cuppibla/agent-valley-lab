"""The identity lock, end to end, offline.

What the anchor really is: `backends.py` only attaches an image to the request
when it is handed `reference_png`. `character_ref` is a filename — the model
never sees it. So every test here asserts on the BYTES the backend was handed.

`FakeImageBackend` is deterministic (hue = sha256("{sheet}|{reference_seed}")),
so the whole file runs with no model, no key and no network.

Run:  uv run python -m unittest discover -s tests -v
      uv run pytest tests            (if you have pytest; these are plain
                                      TestCases, pytest collects them as-is)
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path

os.environ["A101_FAKE_IMAGES"] = "1"       # before any forge import: pin the fake backend
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "0")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.adk.agents.invocation_context import InvocationContext  # noqa: E402
from google.adk.artifacts import InMemoryArtifactService  # noqa: E402
from google.adk.events import Event, EventActions  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.adk.tools import ToolContext  # noqa: E402

from forge.agent import tools  # noqa: E402
from forge.agent.backends import FakeImageBackend  # noqa: E402
from forge.agent.callbacks import after_tool, before_agent, before_tool  # noqa: E402
from forge.agent.character_forge import root_agent as forge_agent  # noqa: E402

Tool = namedtuple("Tool", "name")          # ADK passes the tool; only .name is read
GENERATE_LOOK = Tool("generate_look")

APP = "test_forge"
USER = "traveler"


class RecordingBackend:
    """FakeImageBackend, plus a log of exactly what each render was handed."""

    def __init__(self) -> None:
        self._inner = FakeImageBackend()
        self.calls: list[dict] = []

    def render(self, *, sheet, form, reference_seed, reference_png=None, instruction=None):
        self.calls.append({"sheet": sheet, "form": form, "reference_seed": reference_seed,
                           "reference_png": reference_png, "instruction": instruction})
        return self._inner.render(sheet=sheet, form=form, reference_seed=reference_seed,
                                  reference_png=reference_png, instruction=instruction)

    @property
    def last(self) -> dict:
        return self.calls[-1]


class ForgeCase(unittest.IsolatedAsyncioTestCase):
    """One session, one artifact store, real ADK context objects."""

    async def asyncSetUp(self) -> None:
        self.backend = RecordingBackend()
        tools.set_backend(self.backend)
        self.sessions = InMemorySessionService()
        self.artifacts = InMemoryArtifactService()
        self.session = await self.sessions.create_session(app_name=APP, user_id=USER)

    def ctx(self, state: dict | None = None) -> ToolContext:
        """A ToolContext over the real session/artifact services.

        `state` seeds the session state the way a previous turn (or, in the app
        path, `service.py`) would have left it.
        """
        if state:
            self.session.state.update(state)
        ictx = InvocationContext(
            artifact_service=self.artifacts,
            session_service=self.sessions,
            invocation_id="inv-1",
            agent=forge_agent,
            session=self.session,
        )
        return ToolContext(ictx)

    async def artifact_bytes(self, name: str) -> bytes:
        part = await self.artifacts.load_artifact(
            app_name=APP, user_id=USER, session_id=self.session.id, filename=name)
        return part.inline_data.data

    async def summon_and_lock(self, description="a cozy red panda", name="Mochi"):
        """The two turns every later test starts from."""
        ctx = self.ctx()
        await before_agent(ctx)
        await tools.cast_candidates(description, ctx)
        await tools.lock_candidate(0, name, ctx)
        return ctx


class TestLockStoresTheBytes(ForgeCase):

    async def test_lock_candidate_pins_the_chosen_candidate_bytes(self):
        ctx = await self.summon_and_lock()

        self.assertEqual(ctx.state["character_ref"], "candidate_0.png")
        self.assertIn("temp:character_ref_png", ctx.state)
        self.assertEqual(ctx.state["temp:character_ref_png"],
                         await self.artifact_bytes("candidate_0.png"))
        self.assertTrue(ctx.state["temp:character_ref_png"].startswith(b"\x89PNG"))

    async def test_lock_keeps_its_dict_contract_when_the_artifact_is_unreachable(self):
        """No artifact service at all: the lock still succeeds, just byte-less."""
        ictx = InvocationContext(
            artifact_service=None,                     # load_artifact will raise
            session_service=self.sessions,
            invocation_id="inv-1",
            agent=forge_agent,
            session=self.session,
        )
        ctx = ToolContext(ictx)
        ctx.state["temp:candidates"] = ["candidate_0.png"]

        result = await tools.lock_candidate(0, "Mochi", ctx)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["character_ref"], "candidate_0.png")
        self.assertNotIn("temp:character_ref_png", ctx.state)

    async def test_bad_index_still_returns_the_error_dict(self):
        ctx = self.ctx({"temp:candidates": []})
        self.assertEqual((await tools.lock_candidate(3, "Mochi", ctx))["status"], "error")


class TestTheBytesReachTheBackend(ForgeCase):

    async def test_with_callbacks_generate_look_is_handed_the_locked_bytes(self):
        ctx = await self.summon_and_lock()
        canon = await self.artifact_bytes("candidate_0.png")

        await before_tool(GENERATE_LOOK, {"form": "a golden crown"}, ctx)
        await tools.generate_look("a golden crown", ctx)

        self.assertIsNotNone(self.backend.last["reference_png"],
                             "the backend was called with no anchor image")
        self.assertEqual(self.backend.last["reference_png"], canon)
        self.assertEqual(self.backend.last["reference_seed"], "candidate_0.png")

    async def test_without_callbacks_the_backend_gets_nothing_to_anchor_to(self):
        """The `grove` shape: tools wired, no before_tool. This is the drift."""
        import grove

        self.assertIsNone(grove.root_agent.before_tool_callback,
                          "grove is only the drift case while it has no before_tool")

        ctx = await self.summon_and_lock()
        await tools.generate_look("a golden crown", ctx)      # no before_tool

        self.assertIsNone(self.backend.last["reference_png"])

    async def test_the_two_paths_differ_only_in_the_bytes(self):
        """Same request, same seed, anchored vs not — the hue is identical, and
        that is the point: in the fake, only `reference_png` tells them apart."""
        ctx = await self.summon_and_lock()
        await tools.generate_look("a golden crown", ctx)       # drift path
        without = self.backend.last

        ctx2 = await self.summon_and_lock()
        await before_tool(GENERATE_LOOK, {"form": "a golden crown"}, ctx2)
        await tools.generate_look("a golden crown", ctx2)      # locked path
        with_bytes = self.backend.last

        self.assertEqual(without["reference_seed"], with_bytes["reference_seed"])
        self.assertIsNone(without["reference_png"])
        self.assertIsNotNone(with_bytes["reference_png"])


class TestLatestAnchor(ForgeCase):

    async def test_latest_picks_up_the_last_output_bytes(self):
        ctx = await self.summon_and_lock()

        await before_tool(GENERATE_LOOK, {"form": "a golden crown"}, ctx)
        first = await tools.generate_look("a golden crown", ctx)
        await after_tool(GENERATE_LOOK, {"form": "a golden crown"}, ctx, first)

        self.assertEqual(ctx.state["_last_output"], "look_0.png")
        self.assertEqual(ctx.state["temp:_last_output_png"],
                         await self.artifact_bytes("look_0.png"))

        ctx.state["anchor_mode"] = "latest"
        await before_tool(GENERATE_LOOK, {"form": "a starry cape"}, ctx)

        self.assertEqual(ctx.state["temp:active_reference"], "look_0.png")
        self.assertEqual(ctx.state["temp:active_reference_png"],
                         await self.artifact_bytes("look_0.png"))
        self.assertNotEqual(ctx.state["temp:active_reference_png"],
                            await self.artifact_bytes("candidate_0.png"))


class TestALaterTurn(ForgeCase):
    """temp: state dies with the turn. The artifact does not."""

    async def test_before_tool_reloads_the_canon_bytes_when_temp_is_gone(self):
        await self.summon_and_lock()
        canon = await self.artifact_bytes("candidate_0.png")

        # a fresh turn: only what the session store persisted survives
        self.session.state.pop("temp:character_ref_png", None)
        self.session.state.pop("temp:candidates", None)
        ctx = self.ctx()
        self.assertNotIn("temp:character_ref_png", ctx.state)

        await before_tool(GENERATE_LOOK, {"form": "a golden crown"}, ctx)
        await tools.generate_look("a golden crown", ctx)

        self.assertEqual(self.backend.last["reference_png"], canon)


class TestAppPathUnaffected(ForgeCase):
    """service.py seeds raw canon bytes per request and lets the lock overrule
    the traveler's pick. That path must resolve to the canon bytes, unchanged."""

    async def test_identity_lock_on_overrules_the_pick(self):
        canon, picked = b"\x89PNG-canon", b"\x89PNG-picked"
        ctx = self.ctx({
            "character_ref": "canon",
            "character_ref_png": canon,
            "requested_reference": "look_1.png",
            "requested_reference_png": picked,
            "identity_lock": True,
            "equipped": ["Crown"],
            "op": "equip Crown",
            "look_history": ["look_0.png", "look_1.png"],
        })

        await before_tool(GENERATE_LOOK, {"form": "Crown"}, ctx)
        await tools.generate_look("Crown", ctx)

        self.assertEqual(ctx.state["temp:active_reference_png"], canon)
        self.assertEqual(self.backend.last["reference_png"], canon)
        self.assertEqual(self.backend.last["reference_seed"], "canon")
        self.assertEqual(ctx.state["anchor_mode"], "canon")

    async def test_identity_lock_off_honours_the_pick(self):
        canon, picked = b"\x89PNG-canon", b"\x89PNG-picked"
        ctx = self.ctx({
            "character_ref": "canon",
            "character_ref_png": canon,
            "requested_reference": "look_1.png",
            "requested_reference_png": picked,
            "identity_lock": False,
        })

        await before_tool(GENERATE_LOOK, {"form": "Crown"}, ctx)
        await tools.generate_look("Crown", ctx)

        self.assertEqual(self.backend.last["reference_png"], picked)
        self.assertEqual(self.backend.last["reference_seed"], "look_1.png")


class TestBytesNeverReachThePersistedState(unittest.IsolatedAsyncioTestCase):
    """Why the pin lives under `temp:`.

    `adk web` persists session state to SQLite as JSON. PNG bytes are not JSON:
    a persisted `character_ref_png` does not merely look ugly in the State tab,
    it throws on write. `temp:` keys are trimmed before persistence, so they
    cost nothing and show nothing.
    """

    async def asyncSetUp(self) -> None:
        from google.adk.cli.utils.local_storage import create_local_database_session_service
        self.tmp = tempfile.mkdtemp()
        self.svc = create_local_database_session_service(base_dir=self.tmp)

    async def test_a_persisted_png_key_breaks_the_session_store(self):
        session = await self.svc.create_session(app_name=APP, user_id=USER)
        event = Event(author="tool", invocation_id="inv-1",
                      actions=EventActions(state_delta={"character_ref_png": b"\x89PNG\r\n"}))
        # ADK logs the failure before raising; the log line is expected here.
        logging.disable(logging.CRITICAL)
        try:
            with self.assertRaises(UnicodeDecodeError):
                await self.svc.append_event(session=session, event=event)
        finally:
            logging.disable(logging.NOTSET)

    async def test_a_temp_png_key_is_accepted_and_never_persisted(self):
        session = await self.svc.create_session(app_name=APP, user_id=USER)
        event = Event(author="tool", invocation_id="inv-1",
                      actions=EventActions(state_delta={
                          "temp:character_ref_png": b"\x89PNG\r\n",
                          "character_ref": "candidate_0.png"}))
        await self.svc.append_event(session=session, event=event)

        reloaded = await self.svc.get_session(app_name=APP, user_id=USER, session_id=session.id)
        self.assertEqual(reloaded.state["character_ref"], "candidate_0.png")
        self.assertNotIn("temp:character_ref_png", reloaded.state)


if __name__ == "__main__":
    unittest.main()
