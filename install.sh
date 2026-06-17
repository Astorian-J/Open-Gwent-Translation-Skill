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

if [ -d "$SKILL_DIR" ]; then
    echo "Found existing installation, updating..."
    if [ -d "$SKILL_DIR/.git" ]; then
        # Try fast update first to preserve local pending_terms.md
        (cd "$SKILL_DIR" && git pull --ff-only) && exit 0
        echo "Fast-forward pull failed. Re-cloning..."
    fi
    # Preserve user data before re-cloning
    if [ -f "$SKILL_DIR/references/pending_terms.md" ]; then
        PENDING_BACKUP=$(mktemp)
        cp "$SKILL_DIR/references/pending_terms.md" "$PENDING_BACKUP"
        echo "Backed up pending_terms.md"
    fi
    rm -rf "$SKILL_DIR"
fi

echo "Cloning from GitHub..."
git clone --depth 1 "$REPO_URL" "$SKILL_DIR"

if [ -n "$PENDING_BACKUP" ] && [ -f "$PENDING_BACKUP" ]; then
    mv "$PENDING_BACKUP" "$SKILL_DIR/references/pending_terms.md"
    echo "Restored pending_terms.md"
fi

echo ""
echo "Gwent Translation Skill installed successfully!"
echo "Location: $SKILL_DIR"
echo ""
echo "To use with Claude Code, restart Claude Code or type '/' to see the skill."
echo "To use with other agents, run scripts from $SKILL_DIR and see AGENTS.md."
