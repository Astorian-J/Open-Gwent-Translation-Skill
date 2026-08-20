# Agent Interface — Gwent Translation Lite

This document describes how any AI agent can use the **lite** Gwent translation
flow for short chat content. The interface is mechanical: locate the shared
scripts, run lookup, translate, self-check. No Claude Code-specific knowledge
required.

## Your Task Now

**This skill being loaded means: TRANSLATE Gwent text now — not chat, not analyze.**

Do this right now: get the content to translate → pick a direction (EN↔CN) →
follow the 3 steps below. If the user posts Gwent text in either language
without explicit instruction, default to translating it.

> For **full-article** translation (meta reports, BC proposals, card analysis),
> use the main skill `gwent-translation-style` instead — see the AGENTS.md in the
> main skill directory (resolve it the same way as `$GWENT_SKILL_DIR` in the
> "Locate the shared scripts" section below) for its `translate.py` three-step
> pipeline with pre-injection and completeness guard.

## When to use lite

- Group messages, Discord / QQ / Kook comments, single sentences, short
  paragraphs (roughly < 200 characters)
- Informal, colloquial content
- "translate this line" / "what does this chat mean" requests

**Do not use lite** for long articles or content requiring strict terminology
locking, format skeleton, or full validation — use the main skill.

## Prerequisite

The **main skill** (`gwent-translation-style`) must be installed — lite reuses
its `scripts/` and `references/` without copying them. Install both via
`install.sh` from the repository root.

## Locate the shared scripts

Lite ships no scripts of its own. Resolve the main skill directory once, then
reuse `$GWENT_SKILL_DIR`:

```bash
# Precedence: env var > Claude Code default > hermes default
GWENT_SKILL_DIR="${GWENT_SKILL_DIR:-$HOME/.claude/skills/gwent-translation-style}"
[ -d "$GWENT_SKILL_DIR" ] || GWENT_SKILL_DIR="$HOME/.hermes/skills/gwent-translation-style"
```

For other environments (opencode, custom install paths), set the env var
explicitly:

```bash
export GWENT_SKILL_DIR=/path/to/gwent-translation-style
```

## Workflow (3 steps, on-demand)

### 1. Look up only what you need

Do **not** preload the terminology table. Query a specific card name or term
only when it appears in the source and you are unsure of the official rendering:

```bash
python3 "$GWENT_SKILL_DIR/scripts/lookup.py" "Geralt" --plain
python3 "$GWENT_SKILL_DIR/scripts/lookup.py" "blue coin" --plain
# Fuzzy match when you only roughly remember the spelling
python3 "$GWENT_SKILL_DIR/scripts/lookup.py" "siege" --fuzzy --plain
```

Add `--json` for structured output. The envelope is the same as the main skill:
`{success, exit_code, data, errors}` — so lite composes cleanly into JSON tool
pipelines.

### 2. Translate

Translate per direction (EN→CN or CN→EN):

- **EN→CN**: Bilibili-player register — short sentences, active voice, Arabic
  numerals (5点 / 12人口 / R3), Chinese brackets 「（）」
- **CN→EN**: native-player register — casual, not academic, English parens ()
- Use official renderings from lookup (`blue coin` → 蓝币, not "蓝色的硬币";
  `provision` → 人口, not "费用")
- Preserve rhetoric / hyperbole / irony — translate intent, not literal
  (`loud design` → 存在感太强, not "too loud")
- Keep slang flavor (`bleed` → 逼牌, `brick` → 卡手, `tutor` → 检索)

### 3. Self-check (mental, no script)

Before output, confirm:

- Card names / terms translated (no English card residue in CN output; no
  Chinese residue in EN output)
- Arabic numerals throughout
- No literal translations of locked terms
- Slang register preserved

## Do NOT run (heavy validation, not for chat)

These belong to the main skill's full-article pipeline:

- `auto_pipeline.py pre` — full term injection (runs inside `translate.py
  prepare`); new-term learning runs inside `translate.py finish`
- `completeness_guard.py` — 5-check final gate
- `phase_c_check.py` — Phase C self-check
- `term_enforcer.py` — requires a source / lock file
- `format_skeleton.py`, `learn.py`, `diff_review.py`, `backtranslate.py`

## Optional residue check

If the translation was saved to a file and you want a terminology-residue
sanity check (optional, usually skipped for chat):

```bash
python3 "$GWENT_SKILL_DIR/scripts/check_translation.py" translated.txt --plain
```

Without `--source`, only basic rules run (forbidden terms, residue, Chinese
numerals, brackets).

## Quick Reference

High-frequency items the agent can use without lookup:

### Factions

| Abbr | English | Chinese |
|------|---------|---------|
| MO | Monsters | 怪兽 |
| NR | Northern Realms | 北方领域 |
| NG | Nilfgaard | 尼弗迦德 |
| SK | Skellige | 史凯利格 |
| ST | Scoia'tael | 松鼠党 |
| SY | Syndicate | 辛迪加 |
| NE | Neutral | 中立 |

### Frequent terms

| English | Chinese | Note |
|---------|---------|------|
| provision | 人口 | not "费用" |
| deploy | 部署 | most common keyword |
| bleed | 逼牌 | drain resources in R1 |
| brick | 卡手 | unusable draw |
| thin | 滤牌 / 压缩 | reduce deck size |
| blue coin | 蓝币 | = going first |
| red coin | 红币 | = going second |
| tutor | 检索 | find a specific card |
| highroll / lowroll | 上限发挥 / 下限发挥 | best / worst case |
| tempo | 节奏 | points per turn |

### Community slang (deck archetypes)

| English | Chinese |
|---------|---------|
| no unit archetype | 气宗 |
| Arachas Swarm | 蟹蜘蛛 |
| Fruits / Fruits midrange | 蛆妈 / 破烂怪 |
| Devotion Knights (NR) | 赤诚骑士北 |
| Armor abuse (SK) | 互口岛 |
| enemy boost (NG) | 毒奶 |

For anything not listed, run `lookup.py`.

## Notes for agent implementers

- Lite is a **documentation-only** skill (this file + `SKILL.md`). It has no
  scripts of its own — everything is reused from the main skill via
  `$GWENT_SKILL_DIR`.
- If `$GWENT_SKILL_DIR` is unset and neither default path exists, the main
  skill is not installed; run `install.sh` first.
- `lookup.py` and `check_translation.py` `--json` output follows the same
  envelope as the main skill, so lite composes cleanly into deterministic
  JSON tool pipelines.
- For programmatic / cross-agent tool access (Cursor, Claude Desktop, remote
  agents without a local filesystem), an MCP server is planned but not yet
  built; until then, agents with a local filesystem use this file's
  `$GWENT_SKILL_DIR`-based commands.
