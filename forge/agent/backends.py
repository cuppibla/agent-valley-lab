"""Image backend — swappable, so the whole W1 flow runs offline without a key.

Two implementations behind one protocol:
  · FakeImageBackend  — deterministic solid-color PNGs, no network. The color is
    derived from the REFERENCE it's pinned to, so anchoring to canon keeps the hue
    stable while anchoring to the last output lets it walk away — the drift lesson,
    visible even in the fake.
  · NanoBananaBackend — the real path (gemini-2.5-flash-image). Credentials come
    from the environment: a Vertex AI project by default, or an API key.

`get_backend()` picks the real one once the lab is configured, else the fake.
"""

from __future__ import annotations

import hashlib
import logging
import os
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

logger = logging.getLogger(__name__)

# Curated example art (Annie's favourites) — every fresh summon is conditioned on
# these so live generations match that exact adorable low-poly charm and eye style,
# instead of us trying to force it with brittle text rules.
_STYLE_REF_DIR = Path(__file__).resolve().parents[2] / "domain" / "style_refs"
_STYLE_REF_CACHE: Optional[list[bytes]] = None


def _style_refs() -> list[bytes]:
    global _STYLE_REF_CACHE
    if _STYLE_REF_CACHE is None:
        out: list[bytes] = []
        if _STYLE_REF_DIR.exists():
            # jpeg, because these are 1024px art: the container costs 4.4 MB as PNG
            # and 0.3 MB as JPEG with no visible change in what the model copies.
            # Downscaling them, though, DOES change it — 512 refs come back saturated
            # and hard-lit instead of pastel. Keep the pixels, drop the container.
            for p in sorted([*_STYLE_REF_DIR.glob("*.png"), *_STYLE_REF_DIR.glob("*.jpg")]):
                try:
                    out.append(p.read_bytes())
                except OSError:
                    pass
        _STYLE_REF_CACHE = out
    return _STYLE_REF_CACHE


_MAGIC = ((b"\x89PNG\r\n\x1a\n", "image/png"), (b"\xff\xd8\xff", "image/jpeg"),
          (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"))


def sniff_mime(data: bytes) -> Optional[str]:
    """The real type of these bytes, or None if they are not an image we know.

    The reference the browser sends back is a JPEG — `service._shrink` makes it one —
    so labelling every blob "image/png" was always a lie. Vertex sniffs and forgives
    it; say the true thing anyway, and use this as the gate for whether the bytes are
    an image at all.
    """
    mime = None
    for magic, m in _MAGIC:
        if data.startswith(magic):
            mime = m
            break
    if mime is None and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        mime = "image/webp"
    if mime is None:
        return None
    # A magic number only proves the header. A TRUNCATED jpeg still starts ff d8 ff
    # and still reaches the model as `400 INVALID_ARGUMENT: Provided image is not
    # valid` — so decode it here, where we can say which image and how big.
    try:
        from io import BytesIO
        from PIL import Image
        Image.open(BytesIO(data)).load()
    except Exception:
        return None
    return mime


def as_image_part(data: bytes, where: str):
    """A Part for these bytes, or None with a loud log line if they are not an image.

    A bad reference used to reach the model and come back as a bare
    `400 INVALID_ARGUMENT: Provided image is not valid`, which says nothing about
    which image, how big, or where it came from.
    """
    from google.genai import types
    mime = sniff_mime(data) if data else None
    if not mime:
        head = data[:12].hex() if data else "(empty)"
        logger.warning("%s: not a usable image — %d bytes, starts %s", where, len(data or b""), head)
        return None
    return types.Part(inline_data=types.Blob(mime_type=mime, data=data))


@dataclass
class RenderResult:
    png: bytes
    # A synthetic identity signal the drift eval (M2) can score. The real backend
    # leaves this None (M2 computes similarity from the pixels via an embedding).
    identity_hue: Optional[float] = None


class ImageBackend(Protocol):
    def render(self, *, sheet: str, form: str, reference_seed: str,
               reference_png: "Optional[bytes]" = None,
               instruction: "Optional[str]" = None) -> RenderResult:
        """One generation. `reference_seed` is whatever the pin resolved to
        (the canon ref id, or the last output id) — the mechanism under test.
        `reference_png` is the actual pinned image bytes when available (real backend).
        `instruction` overrides the edit prompt (multiturn outfit builds it per-turn)."""
        ...


# ── a tiny dependency-free PNG encoder (solid color) ────────────────────────

def _solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    row = b"\x00" + bytes(rgb) * width                            # filter byte + pixels
    raw = row * height
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def _hue_to_rgb(hue: float) -> tuple[int, int, int]:
    """hue in [0,1) → a saturated RGB, so drift is visible to the eye."""
    h = (hue % 1.0) * 6.0
    x = int(255 * (1 - abs(h % 2 - 1)))
    table = [(255, x, 0), (x, 255, 0), (0, 255, x),
             (0, x, 255), (x, 0, 255), (255, 0, x)]
    return table[int(h) % 6]


class FakeImageBackend:
    """Offline, deterministic. Hue is a hash of (sheet, reference_seed): pin to the
    same canon ref every turn → identical hue (flat drift); pin to each new output
    → the seed changes every turn → the hue wanders (rising drift)."""

    def render(self, *, sheet: str, form: str, reference_seed: str,
               reference_png: Optional[bytes] = None,
               instruction: Optional[str] = None) -> RenderResult:
        digest = hashlib.sha256(f"{sheet}|{reference_seed}".encode()).digest()
        hue = digest[0] / 255.0
        rgb = _hue_to_rgb(hue)
        return RenderResult(png=_solid_png(64, 64, rgb), identity_hue=hue)


class NanoBananaBackend:
    """Real path — gemini-2.5-flash-image. With no api_key the client reads the
    environment, which is how Vertex mode works (project + your own credentials);
    pass a key to use AI Studio instead. The reference the pin resolved to is fed in
    as `reference_seed` (a handle); when a real reference image is available it's
    attached too."""

    MODEL = "gemini-2.5-flash-image"

    def __init__(self, api_key: Optional[str] = None) -> None:
        from google import genai  # lazy so the fake path has no dep weight
        self._client = genai.Client(api_key=api_key) if api_key else genai.Client()

    def render(self, *, sheet: str, form: str, reference_seed: str,
               reference_png: Optional[bytes] = None,
               instruction: Optional[str] = None) -> RenderResult:
        from google.genai import types
        style = ("Cute low-poly art style — faceted geometric shapes with soft flat shading, in the "
                 "gentle Monument Valley / Alto's Odyssey aesthetic. Big soft expressive eyes, a sweet "
                 "friendly face, warm pastel colours, soft gradient light, sitting on a small glowing "
                 "cloud, plain pastel background, centered, charming and adorable. No text, no logos.")
        contents: list = []
        ref_part = as_image_part(reference_png, "reference image") if reference_png else None
        if reference_png and ref_part is None:
            # Falling through to the else-branch here would quietly re-summon a
            # BRAND-NEW creature instead of dressing this one — a worse failure than
            # stopping, because it looks like it worked.
            raise ValueError(
                f"the reference image is not a usable image "
                f"({len(reference_png)} bytes, starts {reference_png[:12].hex()})")
        if ref_part:  # pin: send the locked reference image every turn
            contents.append(ref_part)
            edit = instruction or (
                f"The EXACT same familiar as the reference image — identical face, colours, markings "
                f"and low-poly style — now with {form}. Keep the identity and the style unchanged.")
            contents.append(f"{edit} {style}")
        else:
            # condition every fresh summon on the curated example art so the charm + eye
            # style matches those exactly, then vary only the species/details from `sheet`.
            for i, ref in enumerate(_style_refs()):
                part = as_image_part(ref, f"style ref {i}")
                if part:
                    contents.append(part)
            contents.append(
                f"Study the art style of the reference images above — that same adorable cute low-poly "
                f"look, the same big soft eyes, the same pastel palette and glowing cloud. Now create a "
                f"BRAND-NEW animal spirit familiar (a little creature — fox, cat, owl, dragon, deer, bunny, "
                f"etc., never a human) in that identical style, based on: {sheet}. If that is not an animal, "
                f"reimagine it as a charming animal familiar. {style}")
        resp = self._client.models.generate_content(
            model=self.MODEL, contents=contents,
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]))
        for part in resp.candidates[0].content.parts:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                d = part.inline_data.data
                import base64 as _b64
                return RenderResult(png=d if isinstance(d, bytes) else _b64.b64decode(d))
        raise RuntimeError("Nano Banana returned no image part")


def shrink(png: bytes, size: int = 512, quality: int = 82) -> bytes:
    """Downscale a generated image before it reaches a browser. A fresh render is
    ~1.3 MB; a few of those inline will crawl. Always shrink for display."""
    from io import BytesIO
    from PIL import Image
    im = Image.open(BytesIO(png)).convert("RGB")
    im.thumbnail((size, size))
    buf = BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def api_key() -> Optional[str]:
    """The key, if this lab is running in API-key mode. Under Vertex there is none —
    the credentials come from the environment (see forge/__init__.py)."""
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def using_vertex() -> bool:
    return os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() in ("1", "TRUE", "YES")


def configured() -> bool:
    """Can we reach a real model at all?"""
    return using_vertex() or bool(api_key())


def get_backend() -> ImageBackend:
    """Real images whenever the lab is configured — Vertex project or API key.
    `A101_FAKE_IMAGES=1` forces the offline fake (used by tests)."""
    if os.environ.get("A101_FAKE_IMAGES") == "1":
        return FakeImageBackend()
    if using_vertex():
        return NanoBananaBackend()          # credentials from the environment
    if api_key():
        return NanoBananaBackend(api_key())
    return FakeImageBackend()
