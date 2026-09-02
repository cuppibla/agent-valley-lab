"""The session id the service hands the runner must be one that EXISTS.

The bug this file locks down, in order:

  1. `/adorn` read `sid = body.get("session_id")` with no fallback, while `/cast`
     had one. A page reload resets the browser's `sessionId` to "", so the very
     next accessory click posted an empty id.
  2. `_run` did a get-or-create and then THREW AWAY the session it created:
     `InMemorySessionService.create_session` mints its own id when handed a falsy
     one, so the created session's real id was never used — `run_async` was still
     driven with "".
  3. On ADK 2.8 `run_async` raises `SessionNotFoundError: Session not found:`
     for an id that does not exist (older ADK get-or-created instead), and the
     Next proxy turns that 500 into the `POST /api/w1/adorn 502` a student sees.

`_ensure_session` is the fix; these are the tests it shipped without. The
assertions are about PLUMBING, not pixels: no model, no key, no network. A
recording stub stands in for the ADK Runner and enforces the one rule the real
one enforces — refuse a session that was never created.

Run:  uv run python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import sys
import unittest
from io import BytesIO
from pathlib import Path

os.environ["A101_FAKE_IMAGES"] = "1"       # before any forge import: pin the fake backend
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "0")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from google.adk.errors.session_not_found_error import SessionNotFoundError  # noqa: E402
from google.adk.events import Event  # noqa: E402
from google.genai import types  # noqa: E402

from forge.agent import service  # noqa: E402


def _png() -> bytes:
    """A real 1x1 PNG — `_shrink` runs it through Pillow, so it has to decode."""
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (1, 1), (120, 90, 200)).save(buf, format="PNG")
    return buf.getvalue()


class RecordingRunner:
    """Stands in for an ADK Runner.

    Records every session id it is driven with, and raises `SessionNotFoundError`
    for one the session service does not have — which is exactly what ADK 2.8's
    `Runner.run_async` does, and is the behaviour that unmasked this bug. A stub
    that accepted anything would let the regression back in.
    """

    def __init__(self, sessions, tool_name: str, response: dict | None = None) -> None:
        self._sessions = sessions
        self._tool = tool_name
        self._response = response
        self.seen: list[str | None] = []

    async def run_async(self, *, user_id, session_id, new_message, **_kw):
        self.seen.append(session_id)
        sess = await self._sessions.get_session(
            app_name=service.APP, user_id=user_id, session_id=session_id)
        if sess is None:
            raise SessionNotFoundError(f"Session not found: {session_id}")
        if self._response is not None:
            yield Event(author="forge", content=types.Content(role="model", parts=[
                types.Part(function_call=types.FunctionCall(name=self._tool, args={})),
                types.Part(function_response=types.FunctionResponse(
                    name=self._tool, response=self._response)),
            ]))


class ServiceSessionCase(unittest.IsolatedAsyncioTestCase):
    """Fresh session + artifact stores and stub runners for every test."""

    maxDiff = None

    async def asyncSetUp(self) -> None:
        from google.adk.artifacts import InMemoryArtifactService
        from google.adk.sessions import InMemorySessionService

        self._real_runners = service._runners
        self._real_sessions = service._sessions
        self._real_artifacts = service._artifacts

        service._sessions = InMemorySessionService()
        service._artifacts = InMemoryArtifactService()
        self.dress = RecordingRunner(service._sessions, "generate_look",
                                     {"status": "ok", "artifact": "look_0.png",
                                      "form": "a golden crown", "identity_hue": 12})
        self.summon = RecordingRunner(service._sessions, "cast_candidates",
                                      {"status": "ok", "candidates": ["cast_0.png"]})
        service._runners = {"summon": self.summon, "dress": self.dress}
        self.client = TestClient(service.app)

    async def asyncTearDown(self) -> None:
        service._runners = self._real_runners
        service._sessions = self._real_sessions
        service._artifacts = self._real_artifacts

    async def live(self, sid: str) -> bool:
        return await service._sessions.get_session(
            app_name=service.APP, user_id="traveler", session_id=sid) is not None

    async def session_ids(self) -> list[str]:
        listed = await service._sessions.list_sessions(app_name=service.APP, user_id="traveler")
        return [s.id for s in listed.sessions]

    def adorn(self, **over) -> dict:
        body = {"request": "give it a golden crown", "item": "a golden crown",
                "op": "equip", "outfit": [], "history_ids": [],
                "canon_id": "canon", "reference_id": "canon", "identity_lock": True}
        body.update(over)
        return body


class TestEnsureSession(ServiceSessionCase):
    """The normaliser itself: whatever it returns must be a session that exists."""

    async def test_an_empty_id_becomes_a_real_one(self):
        sid = await service._ensure_session("")
        self.assertTrue(sid, "_ensure_session returned a falsy id")
        self.assertTrue(await self.live(sid))

    async def test_none_becomes_a_real_one(self):
        sid = await service._ensure_session(None)
        self.assertTrue(sid)
        self.assertTrue(await self.live(sid))

    async def test_whitespace_is_not_an_id(self):
        """`"   "` is truthy in Python and useless as a key — it must not survive."""
        sid = await service._ensure_session("   ")
        self.assertEqual(sid, sid.strip())
        self.assertTrue(sid)
        self.assertTrue(await self.live(sid))

    async def test_a_never_created_id_is_created_under_that_same_id(self):
        sid = await service._ensure_session("s-ghost-0001")
        self.assertEqual(sid, "s-ghost-0001")
        self.assertTrue(await self.live("s-ghost-0001"))

    async def test_an_existing_session_is_reused_not_replaced(self):
        await service._sessions.create_session(
            app_name=service.APP, user_id="traveler", session_id="s-known")
        sid = await service._ensure_session("s-known")
        self.assertEqual(sid, "s-known")
        self.assertEqual(await self.session_ids(), ["s-known"], "a duplicate session was minted")

    async def test_two_blank_calls_do_not_collide(self):
        first, second = await service._ensure_session(""), await service._ensure_session("")
        self.assertNotEqual(first, second)
        self.assertEqual(sorted(await self.session_ids()), sorted([first, second]))


class TestRunNeverDrivesAGhostSession(ServiceSessionCase):
    """The actual crash site: what `_run` hands to `run_async`."""

    async def test_run_uses_a_real_session_id_when_handed_an_empty_one(self):
        results, called = await service._run("dress", "", "give it a crown")
        self.assertEqual(len(self.dress.seen), 1)
        sid = self.dress.seen[0]
        self.assertTrue(sid, "the runner was driven with a falsy session id")
        self.assertTrue(await self.live(sid), "the runner was driven with a session that does not exist")
        self.assertTrue(called)
        self.assertEqual(results[0]["artifact"], "look_0.png")

    async def test_the_runner_is_never_handed_a_falsy_id(self):
        for handed in ("", None, "   "):
            with self.subTest(handed=handed):
                await service._run("dress", handed, "give it a crown")
        self.assertTrue(all(self.dress.seen), f"runner saw a falsy id: {self.dress.seen!r}")
        for sid in self.dress.seen:
            self.assertTrue(await self.live(sid))

    async def test_the_seed_lands_in_the_session_the_runner_drives(self):
        """The old fallback seeded one session and ran another. Same one now."""
        seed = {"identity_lock": True, "requested_reference": "look_0",
                "character_ref": "canon", "character_ref_png": b"\x89PNG-canon"}
        await service._run("dress", "", "give it a crown", seed)
        sid = self.dress.seen[0]
        sess = await service._sessions.get_session(
            app_name=service.APP, user_id="traveler", session_id=sid)
        self.assertEqual(sess.state["requested_reference"], "look_0")
        self.assertIs(sess.state["identity_lock"], True)
        self.assertEqual(sess.state["character_ref_png"], b"\x89PNG-canon")

    async def test_a_named_session_is_driven_under_its_own_name(self):
        await service._run("dress", "s-known", "give it a crown")
        self.assertEqual(self.dress.seen, ["s-known"])


class TestEveryEndpointReturnsAUsableSessionId(ServiceSessionCase):
    """The browser can only reuse an id if the response actually carries it."""

    def test_adorn_with_no_session_id_field_at_all(self):
        r = self.client.post("/adorn", json=self.adorn())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["session_id"])

    def test_adorn_with_an_empty_session_id(self):
        r = self.client.post("/adorn", json=self.adorn(session_id=""))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["session_id"], "adorn echoed the empty id back")

    def test_adorn_with_a_session_id_that_was_never_created(self):
        r = self.client.post("/adorn", json=self.adorn(session_id="s-ghost-0001"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["session_id"], "s-ghost-0001")

    def test_cast_then_adorn_stay_in_the_same_session(self):
        c = self.client.post("/cast", json={"description": "a moonlit fox"})
        self.assertEqual(c.status_code, 200, c.text)
        sid = c.json()["session_id"]
        self.assertTrue(sid)
        a = self.client.post("/adorn", json=self.adorn(session_id=sid))
        self.assertEqual(a.status_code, 200, a.text)
        self.assertEqual(a.json()["session_id"], sid)
        self.assertEqual(self.summon.seen + self.dress.seen, [sid, sid])

    def test_cast_with_an_empty_session_id_still_answers_with_one(self):
        c = self.client.post("/cast", json={"description": "a moonlit fox", "session_id": ""})
        self.assertEqual(c.status_code, 200, c.text)
        self.assertTrue(c.json()["session_id"])

    def test_the_artifact_lookup_is_keyed_on_the_effective_session(self):
        """The image only comes back if `_artifact_png` used the real id too."""
        from anyio.from_thread import start_blocking_portal
        with start_blocking_portal() as portal:
            portal.call(lambda: service._artifacts.save_artifact(
                app_name=service.APP, user_id="traveler", session_id="s-ghost-0001",
                filename="look_0.png",
                artifact=types.Part(inline_data=types.Blob(
                    mime_type="image/png", data=_png()))))
        r = self.client.post("/adorn", json=self.adorn(session_id="s-ghost-0001"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["look_id"], "look_0.png")
        self.assertTrue((r.json()["image"] or "").startswith("data:image/jpeg;base64,"))


class TestTheOldBugStaysFixed(ServiceSessionCase):
    """A guard that fails loudly if anyone reintroduces the empty-sid path."""

    def test_adorn_no_longer_raises_session_not_found(self):
        for body in (self.adorn(), self.adorn(session_id=""), self.adorn(session_id=None)):
            with self.subTest(session_id=body.get("session_id", "<absent>")):
                r = self.client.post("/adorn", json=body)
                self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(all(self.dress.seen),
                        f"the runner was driven with a falsy id: {self.dress.seen!r}")

    def test_adorn_still_seeds_the_identity_lock_for_before_tool(self):
        """Chapter 5 must be untouched: the lock and the canon bytes still land."""
        r = self.client.post("/adorn", json=self.adorn(
            session_id="s-lock", identity_lock=True, reference_id="look_0",
            canon="data:image/png;base64,iVBORw0KGgo="))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIs(r.json()["identity_lock"], True)
        self.assertEqual(r.json()["reference_id"], "look_0")

        from anyio.from_thread import start_blocking_portal
        with start_blocking_portal() as portal:
            sess = portal.call(lambda: service._sessions.get_session(
                app_name=service.APP, user_id="traveler", session_id="s-lock"))
        self.assertIs(sess.state["identity_lock"], True)
        self.assertEqual(sess.state["requested_reference"], "look_0")
        self.assertTrue(sess.state["character_ref_png"], "canon bytes never reached state")


if __name__ == "__main__":
    unittest.main()
