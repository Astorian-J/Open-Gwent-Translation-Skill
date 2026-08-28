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
> main skill directory (the sibling `gwent-translation-style` directory, as
> resolved in the "Locate the shared scripts" section below) for its
> `translate.py` three-step pipeline with pre-injection and completeness guard.

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

Lite ships no scripts of its own. The **main skill** sits as a sibling of this
lite directory — `<this file's directory>/../gwent-translation-style` (the
standard install.sh layout; holds for `~/.claude`, `~/.kimi`, `~/.agents`,
`~/.hanako` and any custom `INSTALL_DIR`). If the `GWENT_SKILL_DIR` environment
variable is set, it wins. In the commands below, replace `$SK` with the resolved
absolute path of the main skill directory.

## Workflow (standard: 2 commands + 1 translation pass)

### 1. prepare --lite — save the content, get the lock table (one command)

The lock table is printed to stdout via `cat`; no separate pack read needed:

```bash
printf '%s\n' "content to translate" > /tmp/gwent-lite-src.md && \
python3 "$SK/scripts/translate.py" prepare /tmp/gwent-lite-src.md --lite && \
cat /tmp/gwent-lite-src.pack.md
```

For multi-line or quote-heavy content, save with a heredoc instead of `printf`,
then run the same prepare + cat. `--lite` builds the chat-length pack (article
grade sections dropped; term lock content identical). Focus on the **[COPY]**
sections in the output (locked term table, ambiguous names with context clues).
`lookup.py` remains available for one-off interactive queries:

```bash
python3 "$SK/scripts/lookup.py" "Geralt" --plain
python3 "$SK/scripts/lookup.py" "siege" --fuzzy --plain  # rough spelling
```

`--json` on any script follows the shared envelope `{success, exit_code, data, errors}`.

### 2. Translate

Translate per direction (EN→CN or CN→EN), no tool calls in this step:

- **EN→CN**: Bilibili-player register — short sentences, active voice, Arabic
  numerals (5点 / 12人口 / R3), Chinese brackets 「（）」
- **CN→EN**: native-player register — casual, not academic, English parens ()
- No dashes: never use 「——」 (or — in English output) to introduce or pad text;
  rewrite with commas, periods, or brackets, even when the source uses em-dashes
- Use official renderings from the lock table (`blue coin` → 蓝币,
  not "蓝色的硬币"; `provision` → 人口, not "费用")
- Preserve rhetoric / hyperbole / irony — translate intent, not literal
  (`loud design` → 存在感太强, not "too loud")
- Keep slang flavor (`bleed` → 逼牌, `brick` → 卡手, `tutor` → 检索)

### 3. finish --lite — save the translation + machine term gate (one command)

```bash
printf '%s\n' "your translation" > /tmp/gwent-lite-out.md && \
python3 "$SK/scripts/translate.py" finish /tmp/gwent-lite-out.md \
  --source /tmp/gwent-lite-src.md --lite
```

- **PASS** → deliver the translation to the user. Done.
- **BLOCKED** → every violation carries the official rendering
  (`「term」 -> official`); apply it to the translation file and re-run the same
  command. Up to 3 fix rounds; still BLOCKED, hand the violation list +
  translation to the user and say which terms have no official rendering.

`--lite` runs the terminology / residue / term-authority gates only (right-sized
for chat) and skips the article-grade Phase C style check, learn, and the
effect audit.

## Fast path (only when the source clearly has NO proper nouns)

Pure emotion / greeting / banter with **no suspected card names, keywords,
faction abbreviations, or mechanic terms** ("gg wp", "this patch is trash lol")
→ skip prepare, translate directly, then save both files and gate in ONE
command:

```bash
printf '%s\n' "source text" > /tmp/gwent-lite-fast-src.md && \
printf '%s\n' "your translation" > /tmp/gwent-lite-fast-out.md && \
python3 "$SK/scripts/translate.py" finish /tmp/gwent-lite-fast-out.md \
  --source /tmp/gwent-lite-fast-src.md --lite
```

finish rebuilds the term lock from the source on the fly and still blocks a
wrongly translated name (violations carry the official rendering). **When in
doubt, use the standard 3 steps.** (The fast path uses fixed `-fast-` filenames
so it cannot collide with a stale lock snapshot on the standard paths.)

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
  scripts of its own — everything is reused from the main skill (`$SK`, the
  sibling `gwent-translation-style` directory).
- If that sibling directory does not exist, the main skill is not installed;
  run `install.sh` first.
- All scripts' `--json` output follows the same envelope as the main skill
  (`{success, exit_code, data, errors}`), so lite composes cleanly into
  deterministic JSON tool pipelines. `finish --lite --json` reports the same
  `violations` shape as the main gate (each entry carries `expected_official`).
- For programmatic / cross-agent tool access (Cursor, Claude Desktop, remote
  agents without a local filesystem), an MCP server is planned but not yet
  built; until then, agents with a local filesystem use this file's
  `$GWENT_SKILL_DIR`-based commands.
