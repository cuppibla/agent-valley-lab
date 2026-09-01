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
from forge.agent.callbacks import (_resolve_reference, after_tool, before_agent,
                                   before_tool)  # noqa: E402
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

    async def summon_only(self, description="a seal-ish creature in a yellow raincoat"):
        """Annie's run: a summon, and then straight to the outfit. No lock."""
        ctx = self.ctx()
        await before_agent(ctx)
        await tools.cast_candidates(description, ctx)
        return ctx


class TestCastAlonePinsAnAnchor(ForgeCase):
    """The bug: seal in, bunny out.

    One portrait means there is no picking moment, so the model never called
    `lock_candidate`; `character_ref` stayed unset, the seed resolved to
    "unpinned", no bytes were found, and `backends.py` took its no-reference
    branch — the one whose prompt literally says "BRAND-NEW animal spirit
    familiar (… deer, bunny, …)". Cast now pins provisionally, so that branch
    is unreachable once anything has been summoned.
    """

    async def test_cast_alone_leaves_a_provisional_anchor(self):
        ctx = await self.summon_only()

        self.assertEqual(ctx.state["provisional_ref"], "candidate_0.png")
        self.assertEqual(ctx.state["temp:provisional_ref_png"],
                         await self.artifact_bytes("candidate_0.png"))
        # provisional is not canon: nothing has been named, nothing is locked
        self.assertNotIn("character_ref", ctx.state)
        self.assertEqual(ctx.state["character_sheet"]["name"], "")
        self.assertEqual(ctx.state["temp:candidates"], ["candidate_0.png"])

    async def test_resolve_reference_no_longer_falls_through_to_unpinned(self):
        ctx = await self.summon_only()
        self.assertEqual(_resolve_reference(ctx.state), ("candidate_0.png", "canon"))
        # and "unpinned" still means what it says: nothing was ever summoned
        self.assertEqual(_resolve_reference({}), ("unpinned", "canon"))

    async def test_the_bunny_path_now_reaches_the_backend_with_bytes(self):
        """The exact sequence that produced the bunny, asserted on the bytes."""
        ctx = await self.summon_only()
        summoned = await self.artifact_bytes("candidate_0.png")

        await before_tool(GENERATE_LOOK, {"form": "a blue scarf"}, ctx)
        await tools.generate_look("a blue scarf", ctx)

        self.assertIsNotNone(self.backend.last["reference_png"],
                             "no lock, no anchor — this is the bunny")
        self.assertEqual(self.backend.last["reference_png"], summoned)
        self.assertEqual(self.backend.last["reference_seed"], "candidate_0.png")

    async def test_the_provisional_pin_survives_the_turn_boundary(self):
        """adk web casts in turn one and dresses in turn two. temp: does not
        cross that line; `provisional_ref` is session-tier so that it can, and
        the bytes come back off the artifact by name."""
        ctx = await self.summon_only()
        summoned = await self.artifact_bytes("candidate_0.png")

        self.session.state.pop("temp:provisional_ref_png", None)
        self.session.state.pop("temp:candidates", None)
        ctx = self.ctx()
        self.assertNotIn("temp:provisional_ref_png", ctx.state)
        self.assertEqual(ctx.state["provisional_ref"], "candidate_0.png")

        await before_tool(GENERATE_LOOK, {"form": "a blue scarf"}, ctx)
        await tools.generate_look("a blue scarf", ctx)

        self.assertEqual(self.backend.last["reference_png"], summoned)


class TestLockIsStillTheLock(ForgeCase):
    """Chapter 4 teaches `lock_candidate` as its own lesson: a tool that spends
    no model, a pure state write, the tool → agent wire. The provisional pin is
    a floor under `generate_look`, not a replacement for locking — locking is
    still what names the character and dissolves the candidates."""

    async def test_lock_still_sets_the_name_and_clears_the_candidates(self):
        ctx = await self.summon_and_lock(name="Nori")

        self.assertEqual(ctx.state["character_sheet"]["name"], "Nori")
        self.assertEqual(ctx.state["temp:candidates"], [])
        self.assertEqual(ctx.state["character_ref"], "candidate_0.png")
        # the provisional pin was promoted, so it stops competing for the eye
        self.assertFalse(ctx.state.get("provisional_ref"))

    async def test_lock_is_the_only_thing_that_writes_character_ref(self):
        ctx = await self.summon_only()
        self.assertNotIn("character_ref", ctx.state)
        await tools.lock_candidate(0, "Nori", ctx)
        self.assertEqual(ctx.state["character_ref"], "candidate_0.png")

    async def test_canon_outranks_a_stale_provisional_pin(self):
        state = {"provisional_ref": "candidate_0.png", "character_ref": "canon.png"}
        self.assertEqual(_resolve_reference(state), ("canon.png", "canon"))

    async def test_cast_lock_look_anchors_to_the_locked_reference(self):
        ctx = await self.summon_and_lock(name="Nori")
        canon = await self.artifact_bytes("candidate_0.png")

        await before_tool(GENERATE_LOOK, {"form": "a golden crown"}, ctx)
        await tools.generate_look("a golden crown", ctx)

        self.assertEqual(self.backend.last["reference_seed"], ctx.state["character_ref"])
        self.assertEqual(self.backend.last["reference_png"], canon)


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

    async def test_the_provisional_pin_does_not_leak_into_the_grove_shape(self):
        """Chapter 5's whole demonstration is that grove — two tools, no
        callbacks — cannot hold a face, because only `before_tool` moves bytes
        into `temp:active_reference_png`. Pinning at cast must not quietly fix
        that: the provisional pin is state, and state is not the anchor."""
        import grove

        self.assertIsNone(grove.root_agent.before_tool_callback)
        self.assertEqual([t.__name__ for t in (grove.root_agent.tools or [])], [],
                         "grove ships with its tool list commented out")

        ctx = await self.summon_only()                        # provisional pin exists
        self.assertEqual(ctx.state["provisional_ref"], "candidate_0.png")
        self.assertIsNotNone(ctx.state["temp:provisional_ref_png"])

        await tools.generate_look("a blue scarf", ctx)        # no before_tool

        self.assertIsNone(self.backend.last["reference_png"],
                          "grove must still drift — that drift is chapter 5")
        self.assertNotIn("temp:active_reference_png", ctx.state)

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

    async def test_a_leftover_provisional_pin_cannot_shadow_the_injected_canon(self):
        """/cast and /adorn share a session id, so the summon lane's provisional
        pin is sitting in state when the dress lane runs. It must stay invisible
        there: `requested_reference` routes through _apply_identity_lock, which
        reads the bytes service.py injected and nothing else."""
        canon, picked = b"\x89PNG-canon", b"\x89PNG-picked"
        ctx = self.ctx({
            "provisional_ref": "candidate_0.png",      # left by the summon lane
            "temp:provisional_ref_png": b"\x89PNG-provisional",
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

        self.assertEqual(self.backend.last["reference_png"], canon)
        self.assertEqual(self.backend.last["reference_seed"], "canon")

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


class TestTheInstructionMatchesTheFlow(unittest.TestCase):
    """Belt and braces. The provisional pin is the guarantee; the instruction is
    the hint. It used to promise four candidates and a picking moment that one
    portrait never produces — which is why the model skipped the lock."""

    def test_the_forge_no_longer_promises_four_candidates(self):
        from forge.agent.character_forge import INSTRUCTION

        self.assertNotIn("4 candidates", INSTRUCTION)
        self.assertIn("ONE portrait", INSTRUCTION)

    def test_the_forge_is_told_to_lock_without_being_asked(self):
        from forge.agent.character_forge import INSTRUCTION

        self.assertIn("lock_candidate(0, name)", INSTRUCTION)
        self.assertIn("do not wait to be asked", INSTRUCTION)
        self.assertIn("Never call generate_look before a portrait exists",
                      INSTRUCTION)

    def test_grove_is_left_alone(self):
        """grove has two tools and no generate_look, so it has no look to render
        from nothing and nothing to say about anchors. Chapter 2/3 unchanged."""
        import grove.agent as grove_agent

        self.assertNotIn("generate_look", grove_agent.INSTRUCTION)
        self.assertNotIn("lock_candidate", grove_agent.INSTRUCTION)


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
