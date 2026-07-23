#!/bin/bash
set -e

SKILL_NAME="gwent-translation-style"
DEFAULT_SKILL_DIR="$HOME/.claude/skills/$SKILL_NAME"
SKILL_DIR="${INSTALL_DIR:-$DEFAULT_SKILL_DIR}"
REPO_URL="https://github.com/Astorian-J/Open-Gwent-Translation-Skill.git"

echo "Installing Gwent Translation Skill..."
echo "Target directory: $SKILL_DIR"

if [ ! -d "$(dirname "$SKILL_DIR")" ]; then
    echo "Creating installation directory..."
    mkdir -p "$(dirname "$SKILL_DIR")"
fi

NEEDS_CLONE=1
if [ -d "$SKILL_DIR" ]; then
    echo "Found existing installation, updating..."
    if [ -d "$SKILL_DIR/.git" ]; then
        # Try fast update first to preserve local pending_terms.md
        if (cd "$SKILL_DIR" && git pull --ff-only); then
            NEEDS_CLONE=0
        else
            echo "Fast-forward pull failed. Re-cloning..."
        fi
    fi
    if [ "$NEEDS_CLONE" = "1" ]; then
        # Preserve user data before re-cloning
        if [ -f "$SKILL_DIR/references/pending_terms.md" ]; then
            PENDING_BACKUP=$(mktemp)
            cp "$SKILL_DIR/references/pending_terms.md" "$PENDING_BACKUP"
            echo "Backed up pending_terms.md"
        fi
        rm -rf "$SKILL_DIR"
    fi
fi

if [ "$NEEDS_CLONE" = "1" ]; then
    echo "Cloning from GitHub..."
    git clone --depth 1 "$REPO_URL" "$SKILL_DIR"
fi

if [ -n "$PENDING_BACKUP" ] && [ -f "$PENDING_BACKUP" ]; then
    mv "$PENDING_BACKUP" "$SKILL_DIR/references/pending_terms.md"
    echo "Restored pending_terms.md"
fi

# Build effect_text.json (CDPR official card ability text; NOT committed — see NOTICE).
# Online fetch from api.gwent.one (~3 min, CN-reachable). Wrapped in `if` so a fetch
# failure degrades gracefully under `set -e` instead of aborting the install:
# translation still works, only official-effect verbatim injection is disabled.
if command -v python3 >/dev/null 2>&1; then
    echo "Fetching official card data from api.gwent.one (approx. 3 min, CN-reachable)..."
    if python3 "$SKILL_DIR/scripts/build_effect_reference.py" --fetch; then
        echo "effect_text.json built."
    else
        echo "WARNING: online fetch failed. Skill installed in degraded mode"
        echo "         (translation works; official card-effect injection disabled)."
        echo "         Retry later: python3 scripts/build_effect_reference.py --fetch"
    fi
else
    echo "WARNING: python3 not found; skipping effect_text.json build."
fi

# Deploy lite skill (chat / short-content translation; reuses main skill's scripts)
LITE_DIR="$(dirname "$SKILL_DIR")/gwent-translation-lite"
if [ -f "$SKILL_DIR/lite/SKILL.md" ]; then
    mkdir -p "$LITE_DIR"
    cp "$SKILL_DIR/lite/"*.md "$LITE_DIR/"
    echo "Lite skill installed at: $LITE_DIR"
else
    echo "WARNING: lite/SKILL.md not found in repo, skipping lite skill"
fi

echo ""
echo "Gwent Translation Skill installed successfully!"
echo "  Full skill: $SKILL_DIR"
echo "  Lite skill: $LITE_DIR (for chat / short content)"
echo ""
echo "To use with Claude Code, restart Claude Code or type '/' to see the skills."
echo "To use with other agents, run scripts from $SKILL_DIR and see AGENTS.md."
