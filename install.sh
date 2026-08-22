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
# Same strategy as card_names_4lang below: local card-db mirror first (offline,
# seconds), online fetch from api.gwent.one as fallback (~3 min, CN-reachable).
# Wrapped in `if` so a failure degrades gracefully under `set -e` instead of
# aborting the install: translation still works, only official-effect verbatim
# injection is disabled.
if command -v python3 >/dev/null 2>&1; then
    echo "Building effect_text.json (local mirror first, online fallback)..."
    if python3 "$SKILL_DIR/scripts/build_effect_reference.py"; then
        echo "effect_text.json built (local mirror)."
    elif python3 "$SKILL_DIR/scripts/build_effect_reference.py" --fetch; then
        echo "effect_text.json built (api.gwent.one online)."
    else
        echo "WARNING: both local mirror and online fetch failed. Skill installed in degraded mode"
        echo "         (translation works; official card-effect injection disabled)."
        echo "         Retry later: python3 scripts/build_effect_reference.py --fetch"
    fi
else
    echo "WARNING: python3 not found; skipping effect_text.json build."
fi

# Build card_names_4lang.json (4-language card name table; NOT committed — see NOTICE).
# This table is the FOUNDATION for the skill rebuild: every later extraction /
# cross-check query reads it, so — unlike effect_text.json — it does NOT degrade.
# A missing/truncated table would silently disable downstream checks (empty-table
# silent-pass). Local mirror preferred; online --fetch fallback; hard-fail on both
# so the install aborts loudly instead of shipping a broken skill.
if command -v python3 >/dev/null 2>&1; then
    echo "Building 4-language card name table (card_names_4lang.json)..."
    if python3 "$SKILL_DIR/scripts/build_card_names_reference.py"; then
        echo "card_names_4lang.json built (local mirror)."
    elif python3 "$SKILL_DIR/scripts/build_card_names_reference.py" --fetch; then
        echo "card_names_4lang.json built (api.gwent.one online)."
    else
        echo "ERROR: card_names_4lang.json 构建失败（本地镜像 + 在线拉取均失败）。" >&2
        echo "       这是 skill 地基表，缺失会导致后续提取/核对静默漏检，故安装中止。" >&2
        echo "       请设置 GWENT_CARD_DB 指向本地镜像，或稍后重试 --fetch 后重新安装。" >&2
        exit 1
    fi
else
    echo "ERROR: python3 未找到；card_names_4lang.json 无法构建（skill 地基表，不可跳过）。" >&2
    exit 1
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

# Post-install self-check (informational; never aborts the install — a
# degraded install is visible above, health_check just restates it with
# per-check detail).
if command -v python3 >/dev/null 2>&1; then
    echo ""
    echo "Running post-install self-check (health_check.py)..."
    python3 "$SKILL_DIR/scripts/health_check.py" || \
        echo "NOTE: health_check reported failures above — review before relying on the skill."
fi

echo ""
echo "Gwent Translation Skill installed successfully!"
echo "  Full skill: $SKILL_DIR"
echo "  Lite skill: $LITE_DIR (for chat / short content)"
echo ""
echo "To use with Claude Code, restart Claude Code or type '/' to see the skills."
echo "To use with other agents, run scripts from $SKILL_DIR and see AGENTS.md."
