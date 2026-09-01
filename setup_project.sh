#!/usr/bin/env bash
# Agent Valley — create a Google Cloud project and put billing on it.
#
# Run this FIRST, before ./setup_codelab.sh. It leaves you with:
#   • a project that exists, is billing-linked, and is old enough to serve
#   • that project ID in ~/project_id.txt
#   • that project set as gcloud's active project
#
# Safe to re-run. A second run reuses the project recorded in
# ~/project_id.txt instead of creating another one.
#
# It never prompts. Every failure exits non-zero with a fix to try.
set -euo pipefail

PROJECT_FILE="$HOME/project_id.txt"
PREFIX="agent-valley-"
CREATE_ATTEMPTS=3      # fresh random ID per attempt; IDs are globally unique
READY_TIMEOUT=120      # seconds to wait for a new project to be serveable
READY_INTERVAL=10      # seconds between readiness probes

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

say "Agent Valley · project + billing"

# ── 0 · gcloud has to be here ────────────────────────────────────────────────
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

# ── 1 · reuse the project from a previous run ────────────────────────────────
# The point of ~/project_id.txt is that a hiccup halfway through does not cost
# you a second project. Read it before generating anything.
project_exists() {
    gcloud projects describe "$1" --format='value(projectId)' >/dev/null 2>&1
}

project_has_billing() {
    [ "$(gcloud billing projects describe "$1" \
            --format='value(billingEnabled)' 2>/dev/null)" = "True" ]
}

# Set when the recorded project is real but never got its billing linked — a
# half-built project from an interrupted run. That one is worth rescuing, so
# section 3 adopts it and section 4 links billing to it, instead of walking
# away and leaving you with two empty projects.
ADOPT_PROJECT=""

if [ -f "$PROJECT_FILE" ]; then
    EXISTING="$(tr -d '[:space:]' < "$PROJECT_FILE" || true)"
    if [ -n "$EXISTING" ]; then
        info "Found $PROJECT_FILE → $EXISTING"
        if project_exists "$EXISTING"; then
            if project_has_billing "$EXISTING"; then
                gcloud config set project "$EXISTING" >/dev/null 2>&1 \
                    || warn "could not select $EXISTING — run: gcloud config set project $EXISTING"
                tick "reusing $EXISTING (exists, billing linked)"
                say "Project ready: $EXISTING"
                printf '  Next:  ./setup_codelab.sh\n\n'
                exit 0
            fi
            ADOPT_PROJECT="$EXISTING"
            info "$EXISTING exists but has no billing — linking billing to it"
        else
            warn "$EXISTING is gone — creating a fresh project."
        fi
    fi
fi

# ── 2 · pick a billing account ───────────────────────────────────────────────
# One listing, filtered in bash. Preference order:
#   1. newest "[YYYY-MM-DD] GDP Credit: ..." account, if you have one
#   2. any open billing account (a personal card is perfectly fine)
# ISO dates sort correctly as plain strings, so `sort -r` picks the newest
# without any date parsing.
say "1 · Billing account"

BILLING_LIST="$(gcloud billing accounts list \
    --filter="open=true" \
    --format="value(displayName,name)" 2>/dev/null || true)"

if [ -z "$BILLING_LIST" ]; then
    die "No open billing account on this Google account." \
        "This lab calls Gemini on Vertex AI, which needs billing enabled." \
        "" \
        "If you were given a Google Cloud credit for this session, claim it" \
        "first — it takes about a minute and creates the billing account for" \
        "you. Then re-run:" \
        "" \
        "  ./setup_project.sh" \
        "" \
        "No credit? Any Google Cloud account with billing works, including" \
        "the free trial:" \
        "  https://console.cloud.google.com/freetrial" \
        "" \
        "Already claimed one? Check that gcloud is signed in as the same" \
        "account you claimed it with:" \
        "  gcloud auth list"
fi

# "[2026-08-14] GDP Credit: 1234" — newest first.
GDP_LINE="$(printf '%s\n' "$BILLING_LIST" \
    | grep -iE '^\[[0-9]{4}-[0-9]{2}-[0-9]{2}\][[:space:]]*GDP[[:space:]]+Credit:' \
    | sort -r | head -1 || true)"

if [ -n "$GDP_LINE" ]; then
    ACCOUNT_LINE="$GDP_LINE"
    info "using the newest GDP Credit account"
else
    ACCOUNT_LINE="$(printf '%s\n' "$BILLING_LIST" | head -1)"
    info "no GDP Credit account found — using your open billing account"
fi

# `value(a,b)` joins fields with a tab; take the last field as the resource
# name, and strip the billingAccounts/ prefix if gcloud included it.
ACCOUNT_NAME="${ACCOUNT_LINE##*$'\t'}"
ACCOUNT_ID="${ACCOUNT_NAME#billingAccounts/}"
ACCOUNT_DISPLAY="${ACCOUNT_LINE%%$'\t'*}"

if [ -z "$ACCOUNT_ID" ]; then
    die "Could not read a billing account ID out of gcloud's output." \
        "Run this and link the project by hand:" \
        "  gcloud billing accounts list"
fi

tick "billing account: $ACCOUNT_DISPLAY ($ACCOUNT_ID)"

# ── 3 · create the project ───────────────────────────────────────────────────
# agent-valley-XXXX. Project IDs are unique across all of Google Cloud and a
# deleted ID stays reserved, so a collision is a normal outcome, not an error:
# retry with a new number before giving up.
say "2 · Project"

if [ -n "$ADOPT_PROJECT" ]; then
    PROJECT_ID="$ADOPT_PROJECT"
    tick "adopting $PROJECT_ID"
else
    PROJECT_ID=""
    CREATE_ERR=""
    for _ in $(seq 1 "$CREATE_ATTEMPTS"); do
        CANDIDATE="${PREFIX}$(printf '%04d' $((RANDOM % 10000)))"
        info "creating $CANDIDATE"
        if CREATE_ERR="$(gcloud projects create "$CANDIDATE" \
                --name="Agent Valley" 2>&1)"; then
            PROJECT_ID="$CANDIDATE"
            break
        fi
        warn "$CANDIDATE was refused, trying another ID"
    done

    if [ -z "$PROJECT_ID" ]; then
        die "Could not create a project after $CREATE_ATTEMPTS attempts." \
            "gcloud said:" \
            "" \
            "$CREATE_ERR" \
            "" \
            "Usual causes: you are at your project quota, or your account is in" \
            "an organization that does not let you create projects." \
            "" \
            "Create one by hand instead — it takes a minute:" \
            "  1. https://console.cloud.google.com/projectcreate" \
            "  2. give it any name, note the PROJECT ID it assigns" \
            "  3. link billing:  Billing → Link a billing account" \
            "  4. tell this lab about it:" \
            "       echo YOUR_PROJECT_ID > ~/project_id.txt" \
            "       gcloud config set project YOUR_PROJECT_ID" \
            "  5. re-run ./setup_project.sh — it will pick that project up"
    fi

    tick "created $PROJECT_ID"
fi

# ── 4 · link billing, record, and select ─────────────────────────────────────
# Record the ID the moment the project exists, before anything below it can
# fail. Every die() past this point tells you to re-run, and a re-run can only
# keep that promise if the ID is already on disk.
printf '%s\n' "$PROJECT_ID" > "$PROJECT_FILE"

if ! LINK_ERR="$(gcloud billing projects link "$PROJECT_ID" \
        --billing-account="$ACCOUNT_ID" 2>&1)"; then
    die "Could not link billing to $PROJECT_ID." \
        "gcloud said:" \
        "" \
        "$LINK_ERR" \
        "" \
        "Link it in the console, then re-run this script (it will reuse the" \
        "project, not make another one):" \
        "  https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID"
fi
tick "billing linked"

if ! SELECT_ERR="$(gcloud config set project "$PROJECT_ID" 2>&1)"; then
    die "Linked billing to $PROJECT_ID, but could not make it the active project." \
        "gcloud said:" \
        "" \
        "$SELECT_ERR" \
        "" \
        "$PROJECT_ID itself is fine, and it is already recorded in" \
        "$PROJECT_FILE. Select it by hand:" \
        "" \
        "  gcloud config set project $PROJECT_ID" \
        "" \
        "Then re-run ./setup_project.sh — it will reuse $PROJECT_ID."
fi
tick "recorded in $PROJECT_FILE and set as the active gcloud project"

# ── 5 · wait for the project to actually be allowed to serve ─────────────────
# A project that is seconds old will answer 403 IAM_PERMISSION_DENIED while its
# IAM policy propagates. ./setup_codelab.sh makes a real Gemini call almost
# immediately, so absorb that wait here instead of failing there.
say "3 · Waiting for the project to come up"
info "a brand new project answers 403 for a minute or so — this is normal"

deadline=$(( SECONDS + READY_TIMEOUT ))
ready=0
while [ "$SECONDS" -lt "$deadline" ]; do
    if [ "$(gcloud billing projects describe "$PROJECT_ID" \
                --format='value(billingEnabled)' 2>/dev/null)" = "True" ] \
       && gcloud services list --enabled --project="$PROJECT_ID" \
                --limit=1 --format='value(config.name)' >/dev/null 2>&1; then
        ready=1
        break
    fi
    printf '  · not ready yet, retrying in %ss\n' "$READY_INTERVAL"
    sleep "$READY_INTERVAL"
done

if [ "$ready" -ne 1 ]; then
    die "$PROJECT_ID is created and billing-linked, but still not serving after ${READY_TIMEOUT}s." \
        "Nothing is broken — new projects sometimes take longer than this to" \
        "propagate. Wait a minute, then run:" \
        "" \
        "  ./setup_project.sh" \
        "" \
        "It will reuse $PROJECT_ID rather than create another project."
fi

tick "$PROJECT_ID is serving"

say "Project ready: $PROJECT_ID"
printf '  Next:  ./setup_codelab.sh\n\n'
