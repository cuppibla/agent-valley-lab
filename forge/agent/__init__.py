"""Character Forge agent package — the finished version.

`character_forge.py` here is the grown-up of the one you edit in `grove/`: same three tools,
plus the five lifecycle callbacks that keep a familiar looking like itself. It is
deliberately NOT re-exported as `root_agent`, so `adk web` lists exactly two apps —
the two ways of wiring a tool, which is this chapter's whole comparison.

Import it directly when you want it:  from forge.agent.character_forge import root_agent
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
