#!/usr/bin/env bash
# Agent Valley — one-shot environment setup for the CODELAB (uv path).
# Safe to re-run any number of times.
#
# Run ./setup_project.sh FIRST. That one makes the project and puts billing on
# it; this one turns that project into a working lab environment:
#   • aiplatform.googleapis.com enabled on it
#   • .venv built by uv, dependencies pinned by uv.lock
#   • a root .env pointing the lab at Vertex AI on that project
#   • one real Gemini call, so you find out here and not in chapter one
#
# It never prompts and never blocks waiting for input. Every failure exits
# non-zero with a fix to try.
set -euo pipefail
cd "$(dirname "$0")"

say()  { printf '\n\033[1m%s\033[0m\n' "$1"; }
tick() { printf '  ✓ %s\n' "$1"; }
info() { printf '  · %s\n' "$1"; }
warn() { printf '  ! %s\n' "$1" >&2; }

# Print a block of guidance and stop. Never waits for input: this script has
# to survive being run non-interactively.
die() {
    printf '\n\033[1m✗ %s\033[0m\n\n' "$1" >&2
    shift
    for line in "$@"; do printf '%s\n' "$line" >&2; done
    printf '\n' >&2
    exit 1
}

say "Agent Valley · setup"

# ── 0 · gcloud, an account, and a project ────────────────────────────────────
# ./setup_project.sh leaves all three in place. If any is missing, the honest
# answer is to send you back there rather than half-configure the lab.
command -v gcloud >/dev/null 2>&1 || die \
    "gcloud not found." \
    "This script is written for Cloud Shell, where gcloud is preinstalled." \
    "On a laptop, install the Google Cloud SDK first:" \
    "  https://cloud.google.com/sdk/docs/install"

if [ -z "$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null)" ]; then
    die "No active gcloud account." \
        "Authenticate, then re-run this script:" \
        "  gcloud auth login"
fi

# `gcloud config get project` is the modern spelling; `get-value` is the one
# older SDKs understand. ~/project_id.txt is what ./setup_project.sh wrote, and
# is the tiebreaker when gcloud has no project selected.
PROJECT="$(gcloud config get project 2>/dev/null \
    || gcloud config get-value project 2>/dev/null || true)"
PROJECT="$(printf '%s' "$PROJECT" | tr -d '[:space:]')"
case "$PROJECT" in
    "(unset)"|"unset") PROJECT="" ;;
esac

PROJECT_FILE="$HOME/project_id.txt"
if [ -z "$PROJECT" ] && [ -f "$PROJECT_FILE" ]; then
    PROJECT="$(tr -d '[:space:]' < "$PROJECT_FILE" || true)"
    if [ -n "$PROJECT" ]; then
        info "gcloud had no project selected — taking $PROJECT from $PROJECT_FILE"
        gcloud config set project "$PROJECT" >/dev/null 2>&1 || true
    fi
fi

if [ -z "$PROJECT" ]; then
    die "No Google Cloud project selected." \
        "./setup_project.sh creates one, links billing, and records the id" \
        "in ~/project_id.txt. Run it first:" \
        "" \
        "  ./setup_project.sh" \
        "" \
        "Already have a project you want to use? Point gcloud at it instead:" \
        "  gcloud config set project YOUR_PROJECT_ID"
fi

tick "project: $PROJECT"

# ── 1 · the one API this lab calls ───────────────────────────────────────────
# Agent Valley is Gemini-on-Vertex and nothing else: no BigQuery, no Cloud Run,
# no Agent Engine. One API, so one enable. It is idempotent, so re-runs are
# free, but a fresh project can still 403 here while its IAM propagates.
say "1 · Vertex AI API"

if ! ENABLE_ERR="$(gcloud services enable aiplatform.googleapis.com \
        --project="$PROJECT" -q 2>&1)"; then
    die "Could not enable aiplatform.googleapis.com on $PROJECT." \
        "gcloud said:" \
        "" \
        "$ENABLE_ERR" \
        "" \
        "If that mentions 403 or PERMISSION_DENIED, the project is simply too" \
        "new — its IAM policy is still propagating. Wait a minute, then run:" \
        "" \
        "  ./setup_codelab.sh" \
        "" \
        "If it mentions billing, link a billing account and re-run:" \
        "  https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT"
fi
tick "aiplatform.googleapis.com enabled"

# ── 2 · python env + deps (uv owns both) ─────────────────────────────────────
say "2 · Python environment"

# uv may have just been installed into ~/.local/bin by the codelab's curl
# one-liner, in a shell that has not re-read its PATH yet. Look there before
# giving up on it.
if ! command -v uv >/dev/null 2>&1 && [ -x "$HOME/.local/bin/uv" ]; then
    PATH="$HOME/.local/bin:$PATH"
    export PATH
fi

if ! command -v uv >/dev/null 2>&1; then
  printf '  ✗ uv not found. Install it, then re-run ./setup_codelab.sh:\n' >&2
  printf '      curl -LsSf https://astral.sh/uv/install.sh | sh\n' >&2
  exit 1
fi
# uv is the only dependency path here: `uv venv` makes .venv, `uv sync` installs
# exactly what uv.lock pins. Nothing is pip-installed on the side.
#
# Some uv versions refuse to create a venv over one that already exists, which
# would make a second run of this script fail on a clean environment. Only
# create it when it is not there; `uv sync` reconciles it either way.
if [ -d .venv ]; then
    info "reusing the existing .venv"
else
    uv venv
fi
uv sync
tick "uv env + google-adk / google-genai (locked by uv.lock)"

# ── 3 · credentials and .env ─────────────────────────────────────────────────
# In Cloud Shell application-default credentials are already there, so this is
# a check and not a login: `gcloud auth application-default login` opens a
# browser and waits, which would hang this script. On a laptop without ADC we
# warn and tell you the command to run yourself.
say "3 · Credentials"

if [ -f "$HOME/.config/gcloud/application_default_credentials.json" ] \
   || [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] \
   || [ -n "${CLOUD_SHELL:-}" ]; then
    tick "application-default credentials present"
else
    warn "no application-default credentials found."
    warn "If the Gemini call below fails, run this once and re-run the script:"
    warn "  gcloud auth application-default login"
fi

# The lab reads exactly these three. The credential is your gcloud identity,
# so there is nothing to paste into this file and nothing to leak out of it.
#
# A re-run rewrites those three and keeps everything else. If you added your
# own settings to .env by hand, this script is not going to eat them.
ENV_KEPT=""
if [ -f .env ]; then
    ENV_KEPT="$(grep -vE '^[[:space:]]*(GOOGLE_GENAI_USE_VERTEXAI|GOOGLE_CLOUD_PROJECT|GOOGLE_CLOUD_LOCATION)[[:space:]]*=' .env || true)"
fi

{
  echo "GOOGLE_GENAI_USE_VERTEXAI=True"
  echo "GOOGLE_CLOUD_PROJECT=$PROJECT"
  # global, not a region: Gemini here runs on dynamic shared quota, so one
  # busy region can 429 through no fault of the student. global draws on
  # capacity across regions. ADK loads .env OVER shell exports, so this
  # file is what actually decides the endpoint.
  echo "GOOGLE_CLOUD_LOCATION=global"
  if [ -n "$ENV_KEPT" ]; then
      printf '%s\n' "$ENV_KEPT"
  fi
} > .env
tick "wrote .env — Vertex AI on project $PROJECT"
if [ -n "$ENV_KEPT" ]; then
    info "kept the other lines that were already in .env"
fi

# ── 4 · prove the model answers ──────────────────────────────────────────────
# The only check worth having: a real call to a real model over the credentials
# this lab will actually use. Everything above is a guess until this line ticks.
say "4 · Live check"

export GOOGLE_GENAI_USE_VERTEXAI="True"
export GOOGLE_CLOUD_PROJECT="$PROJECT"
export GOOGLE_CLOUD_LOCATION="global"

if CHECK_OUT="$(uv run python - <<'PY' 2>&1
from google import genai
from google.genai import types as gt

client = genai.Client()
r = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Reply with exactly: agent valley, ready to summon.",
    config=gt.GenerateContentConfig(
        thinking_config=gt.ThinkingConfig(thinking_budget=0), temperature=0.0))
print(r.text.strip())
PY
)"; then
    tick "gemini-2.5-flash: $(printf '%s' "$CHECK_OUT" | tail -1)"
else
    case "$CHECK_OUT" in
        *403*|*PERMISSION_DENIED*)
            die "Gemini answered 403 on $PROJECT." \
                "Nothing is broken — a project this new is still propagating its" \
                "IAM policy, and Vertex AI says no until it finishes. Wait a" \
                "minute, then run:" \
                "" \
                "  ./setup_codelab.sh" \
                "" \
                "It will reuse $PROJECT and pick up where this left off." \
                "" \
                "Vertex AI said:" \
                "" \
                "$CHECK_OUT"
            ;;
        *)
            die "The Gemini call failed on $PROJECT." \
                "Vertex AI said:" \
                "" \
                "$CHECK_OUT" \
                "" \
                "If that mentions credentials, run this once and re-run the script:" \
                "  gcloud auth application-default login" \
                "" \
                "If it mentions billing, link a billing account and re-run:" \
                "  https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT"
            ;;
    esac
fi

say "Setup finished. Next:  uv run python scripts/preflight.py"
printf '\n'
