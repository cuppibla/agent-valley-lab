"""Shared Nano Banana scene renderer — style-ref conditioned, browser-sized output.

Used by district assembly (W2) and any later zone that renders a scene once per
run. Familiar generation stays in 01-control/agent/backends.py (it pins identity;
this pins only style)."""

from __future__ import annotations

import base64
import io
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STYLE_REFS = sorted((ROOT / "domain" / "style_refs").glob("*.png"))

STYLE = ("Cute low-poly diorama art style — faceted geometric shapes with soft flat "
         "shading, gentle Monument Valley aesthetic, warm pastel colours, soft gradient "
         "light, a tiny self-contained scene on a plain soft pastel background, centered, "
         "charming and adorable. Match the art style of the reference images exactly. "
         "No text, no letters, no logos.")


def render_scene(prompt: str, api_key: str, size: int = 640, quality: int = 85) -> str:
    """One scene generation → small JPEG data URL."""
    from google import genai
    from google.genai import types
    from PIL import Image

    client = genai.Client(api_key=api_key)
    refs = [types.Part(inline_data=types.Blob(mime_type="image/png", data=p.read_bytes()))
            for p in STYLE_REFS]
    resp = client.models.generate_content(
        model="gemini-2.5-flash-image", contents=[*refs, f"{prompt} {STYLE}"],
        config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]))
    png = next(p.inline_data.data for p in resp.candidates[0].content.parts
               if getattr(p, "inline_data", None) and p.inline_data.data)
    im = Image.open(io.BytesIO(png)).convert("RGB")
    im.thumbnail((size, size))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
