# Agent Interface — Gwent Translation Lite

This document describes how any AI agent can use the **lite** Gwent translation
flow for short chat content. The interface is mechanical: locate the shared
scripts, run prepare (term lock pack), translate, gate with `finish --lite`.
No Claude Code-specific knowledge required.

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

## Term rule (the one that matters most)

Any proper noun in the source — character / card names / keywords / mechanics —
that could be a Gwent-specific term MUST use the official rendering from the
prepare lock table or a `lookup.py` result. **Never coin a translation from
memory**: your "remembered" rendering may be wrong; that is exactly what the
machine gate exists to catch.

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

> **When neither default exists** (custom `INSTALL_DIR` layout, e.g. `~/.agents/skills/`):
> the main skill sits as a sibling of this lite directory —
> `<this file's directory>/../gwent-translation-style` (the standard install.sh
> layout). Derive it from the actual path you read this file from and
> `export GWENT_SKILL_DIR=<that path>`.

For other environments (opencode, custom install paths), set the env var
explicitly:

```bash
export GWENT_SKILL_DIR=/path/to/gwent-translation-style
```

## Workflow (3 steps: prepare -> translate -> finish --lite)

### 1. prepare — save the content, get the lock table

Save the chat content to a temp file and build the term-lock pack:

```bash
printf '%s\n' "content to translate" > /tmp/gwent-lite-src.md
python3 "$GWENT_SKILL_DIR/scripts/translate.py" prepare /tmp/gwent-lite-src.md
```

Read the generated `/tmp/gwent-lite-src.pack.md` — focus on the **[COPY]**
sections (locked term table, ambiguous names with context clues). The pack for
chat-length content is small (a few KB). `lookup.py` remains available for
one-off interactive queries:

```bash
python3 "$GWENT_SKILL_DIR/scripts/lookup.py" "Geralt" --plain
python3 "$GWENT_SKILL_DIR/scripts/lookup.py" "siege" --fuzzy --plain  # rough spelling
```

`--json` on any script follows the shared envelope `{success, exit_code, data, errors}`.

### 2. Translate

Translate per direction (EN→CN or CN→EN):

- **EN→CN**: Bilibili-player register — short sentences, active voice, Arabic
  numerals (5点 / 12人口 / R3), Chinese brackets 「（）」
- **CN→EN**: native-player register — casual, not academic, English parens ()
- No dashes: never use 「——」 (or — in English output) to introduce or pad text;
  rewrite with commas, periods, or brackets, even when the source uses em-dashes
- Use official renderings from the pack's [COPY] tables (`blue coin` → 蓝币,
  not "蓝色的硬币"; `provision` → 人口, not "费用")
- Preserve rhetoric / hyperbole / irony — translate intent, not literal
  (`loud design` → 存在感太强, not "too loud")
- Keep slang flavor (`bleed` → 逼牌, `brick` → 卡手, `tutor` → 检索)

Save the translation:

```bash
printf '%s\n' "your translation" > /tmp/gwent-lite-out.md
```

### 3. finish --lite — machine term gate (fix until PASS)

```bash
python3 "$GWENT_SKILL_DIR/scripts/translate.py" finish /tmp/gwent-lite-out.md \
  --source /tmp/gwent-lite-src.md --lite
```

- **PASS** → deliver the translation to the user. Done.
- **BLOCKED** → every violation carries the official rendering
  (`「term」 -> official`); apply it to the translation file and re-run step 3.
  Up to 3 fix rounds; still BLOCKED, hand the violation list + translation to
  the user and say which terms have no official rendering.

`--lite` runs the terminology / residue / term-authority gates only (right-sized
for chat) and skips the article-grade Phase C style check, learn, and the
effect audit.

## Do NOT run (article-grade, not for chat)

These belong to the main skill's full-article pipeline:

- `auto_pipeline.py` / `phase_c_check.py` / `term_enforcer.py` /
  `completeness_guard.py` — internal steps of prepare / finish; never run by hand
- `learn.py`, `diff_review.py`, `backtranslate.py` — full-article pipeline tools
- `format_skeleton.py` — standalone structure tool (not part of prepare/finish)
- finish **without** `--lite` — runs the article-grade style check, which
  misfires on chat-length content

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
- All scripts' `--json` output follows the same envelope as the main skill
  (`{success, exit_code, data, errors}`), so lite composes cleanly into
  deterministic JSON tool pipelines. `finish --lite --json` reports the same
  `violations` shape as the main gate (each entry carries `expected_official`).
- For programmatic / cross-agent tool access (Cursor, Claude Desktop, remote
  agents without a local filesystem), an MCP server is planned but not yet
  built; until then, agents with a local filesystem use this file's
  `$GWENT_SKILL_DIR`-based commands.
