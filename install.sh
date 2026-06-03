#!/bin/bash
set -e

SKILL_NAME="gwent-translation-style"
SKILL_DIR="$HOME/.claude/skills/$SKILL_NAME"
REPO_URL="https://github.com/Astorian-J/Open-Gwent-Translation-Skill.git"

echo "Installing Gwent Translation Skill..."

if [ ! -d "$HOME/.claude/skills" ]; then
    echo "Creating Claude Code skills directory..."
    mkdir -p "$HOME/.claude/skills"
fi

if [ -d "$SKILL_DIR" ]; then
    echo "Found existing installation, updating..."
    rm -rf "$SKILL_DIR"
fi

echo "Cloning from GitHub..."
git clone --depth 1 "$REPO_URL" "$SKILL_DIR"

echo ""
echo "Gwent Translation Skill installed successfully!"
echo "Location: $SKILL_DIR"
echo ""
echo "Restart Claude Code or type '/' to see the skill in action."
