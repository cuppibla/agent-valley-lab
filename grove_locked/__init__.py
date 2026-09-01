"""Repo root on sys.path (adk web passes an agent path, not the repo root)."""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from .agent import root_agent  # noqa: E402

__all__ = ["root_agent"]
