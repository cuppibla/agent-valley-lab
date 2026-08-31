"""The finished Character Forge — the agent the valley actually runs on.

`forge/agent/` holds the real tools, the five control callbacks, the trace plugin
and the FastAPI service. The two lab agents (`grove/`, `grove_flow/`) import the
SAME tools from here, so nothing in this lab is a toy copy.

Importing anything from `forge` also settles **how the lab talks to Gemini**, once,
for every surface — adk web, the service, and the scripts — whatever directory you
started them from. Two ways, in this order:

  1. **Vertex AI** (the default): your Google Cloud project + the credentials you
     already have. Nothing to paste, nothing to leak. This is what Cloud Shell
     gives you for free.
  2. **An API key**, if you would rather not use a project. Put it in `.env`.
"""

import os
import re
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _ROOT / ".env"
_ADC = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"

#: Set by load_env() — "vertex", "api-key", or None. Read it for messages, not logic.
MODE: str | None = None


def _read_env_file() -> None:
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text().splitlines():
        m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)", line)
        if m and m.group(2).strip() and m.group(1) not in os.environ:
            os.environ[m.group(1)] = m.group(2).strip().strip('"').strip("'")


def _gcloud_project() -> str | None:
    """The project gcloud is pointed at — so Cloud Shell needs no configuration."""
    for var in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_QUOTA_PROJECT", "GCP_PROJECT"):
        if os.environ.get(var):
            return os.environ[var]
    try:
        out = subprocess.run(["gcloud", "config", "get-value", "project"],
                             capture_output=True, text=True, timeout=8).stdout.strip()
        return out or None
    except (OSError, subprocess.SubprocessError):
        return None


def load_env() -> str | None:
    """Pick a mode and export exactly the variables it needs. Returns the mode."""
    global MODE
    _read_env_file()

    # One key, one name: a learner may paste theirs under either, and leaving both
    # set makes the genai SDK warn.
    if os.environ.get("GEMINI_API_KEY"):
        os.environ.setdefault("GOOGLE_API_KEY", os.environ["GEMINI_API_KEY"])
        os.environ.pop("GEMINI_API_KEY", None)

    wants_vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").upper() in ("1", "TRUE", "YES")
    has_key = bool(os.environ.get("GOOGLE_API_KEY"))

    # An explicit key wins only when Vertex was not explicitly asked for.
    if has_key and not wants_vertex:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
        MODE = "api-key"
        return MODE

    project = _gcloud_project()
    if wants_vertex or (_ADC.exists() and project):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        if project:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
        os.environ.pop("GOOGLE_API_KEY", None)   # never send both
        MODE = "vertex"
        return MODE

    MODE = "api-key" if has_key else None
    return MODE


load_env()
