"""Character Forge agent package — the finished version.

`character_forge.py` here is the grown-up of the one you edit in `grove/`: same three tools,
plus the five lifecycle callbacks that keep a familiar looking like itself. It is not
re-exported as `root_agent` here — this package is a library, not an app. `adk web`
lists a directory as an app when the directory has an `agent.py`, and this one does not.

`grove_locked/` is the app wrapper: one `agent.py` that re-exports this agent, so the
dev UI lists it next to `grove` and you can run the same request against both.

Import it directly when you want it:  from forge.agent.character_forge import root_agent
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
