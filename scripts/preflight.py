"""Prove the toolchain is green before the lab starts. Boots nothing.

    python scripts/preflight.py
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OK, BAD = "  ✓", "  ✗"
problems: list[str] = []


def check(label: str, ok: bool, hint: str = "") -> None:
    print(f"{OK if ok else BAD} {label}")
    if not ok:
        problems.append(hint or label)


def main() -> None:
    print("\nAgent Valley · preflight\n")

    check(f"python {sys.version_info.major}.{sys.version_info.minor}",
          sys.version_info >= (3, 11), "python 3.11+ required")

    try:
        import google.adk  # noqa: F401
        check("google-adk", True)
    except ImportError:
        check("google-adk", False, "run: uv sync")

    check("node + npm", bool(shutil.which("npm")), "install Node 20+ for the valley app")

    import forge  # settles Vertex-vs-key config
    from forge.agent.backends import configured, using_vertex

    if using_vertex():
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        check(f"Vertex AI · project {project or '(none found)'}", bool(project),
              "gcloud config set project YOUR_PROJECT_ID  (and gcloud auth application-default login)")
    else:
        check("API key (.env)", configured(),
              "cp .env.example .env — then either leave GOOGLE_GENAI_USE_VERTEXAI=TRUE "
              "(and point gcloud at a project), or paste a key from https://aistudio.google.com/apikey")

    from forge.agent.tools import cast_candidates, generate_look, lock_candidate  # noqa: F401
    check("the forge tools import", True)

    import grove

    n = len(grove.root_agent.tools)
    hint = {0: "  ← no edits yet (correct — chapter 2 makes the first one)",
            1: "  ← edit one done; chapter 4 adds the second tool",
            2: "  ← both edits done"}.get(n, "")
    print(f"{OK} grove       · agent · {n} tool{'s' if n != 1 else ''}{hint}")
    print()
    if problems:
        print("PREFLIGHT RED — fix these first:")
        for p in problems:
            print(f"   · {p}")
        sys.exit(1)
    print("PREFLIGHT GREEN — nothing is running yet; each chapter boots what it needs.\n")


if __name__ == "__main__":
    main()
