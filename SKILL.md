---
name: gwent-translation-style
description: |
  Gwent (昆特牌) bidirectional article translation (EN↔CN) with community slang and Bilibili player tone.
  Triggered by: Gwent translation, 昆特牌翻译, 平衡委员会, meta report translation, 昆特牌英文翻译.
  Enforces: short sentences, community slang, active voice, strict terminology.
agent_created: true
---

# Gwent Translation Style (昆特牌翻译风格)

> For non-Claude agents and programmatic usage, see [AGENTS.md](AGENTS.md).

## 你现在的任务 / Your Task Now

**本 skill 一被调用 = 你现在要做昆特牌（Gwent）翻译。**
不是聊天、不是分析、不是总结——是翻译。
**This skill being loaded means: TRANSLATE Gwent text now — not chat, not analyze, not summarize.**

立刻做三件事 / Do this right now:

1. **拿到要翻译的内容** — 用户已贴在对话里；若没有，主动问「把要翻译的昆特牌文章发给我」
2. **判断方向** — 英文→中文 (`encn`) 还是 中文→英文 (`cnen`)
3. **走流程** — `prepare` → 翻译 → `finish`（见下方 Translation Workflow）

> 只要用户贴了昆特牌相关的中文或英文，哪怕没明说「翻译」，默认就是要翻译，直接开干。
> If the user posts Gwent text in either language without explicit instruction, default to translating it.

## Overview

Bidirectional translation for Gwent articles between English and Chinese.

**EN → CN**: English articles into Chinese using a Bilibili player community tone:
short punchy sentences, community slang, active voice, and precise terminology.
Output should sound like a native Chinese Gwent player wrote it.

**CN → EN**: Chinese articles into natural English that preserves community terminology
and reads like a native Gwent player wrote it. Casual but not stiff.

## When to Use

- Translating English Gwent text into Chinese (meta reports, BC proposals, card analysis)
- Translating Chinese Gwent text into English (community posts, strategy guides)
- User asks for "翻译这篇昆特牌文章" or similar
- User provides source text + their own translation for comparison/correction
- User asks for "把这段中文翻译成英文" or similar

## Translation Workflow

> **IMPORTANT**: Every translation MUST go through `translate.py` — a two-command
> deterministic pipeline. Skipping either command produces UNVERIFIED output that
> MUST NOT be finalized. Do NOT run `auto_pipeline`, `phase_c_check`,
> `term_enforcer`, or `completeness_guard` manually — they are now internal steps
> of `translate.py`. The pipeline is the only entry point:
>
> ```bash
> # 1. Prepare — build the translation pack (locked terms, official effects, style rules)
> python scripts/translate.py prepare source.md --date YYYY-MM --type general --direction encn
> # 2. Translate using the generated source.pack.md  (the only LLM step)
> # 3. Finish — hard gate; the translation is NOT final until this PASSes
> python scripts/translate.py finish translated.txt --source source.md --direction encn
> ```

Step 2 (translate) is the only place judgment is applied. Steps 1 and 3 are
deterministic code — they run the same way every time and cannot be skipped, which
is the whole reason this pipeline exists: it removes the option to "forget" preprocessing
or the final gate.

---

### Step 1: Prepare (备料)

**Run this FIRST, before translating:**

```bash
python scripts/translate.py prepare source.md --date YYYY-MM --type general --direction encn
```

This runs all preprocessing and writes **`source.pack.md`** — READ IT before translating.
It is your single source of truth for this article and contains:

- **MANDATORY Term Lock Table** — card names, terminology, resolved abbreviations/aliases
  (e.g. "OTB" → "Off the Books" → "黑市买卖"). Use these exact Chinese translations.
  **DO NOT translate locked terms literally.**
- **Ambiguous names** — must use the full subtitle form (e.g. "Geralt: Igni", not just "Geralt").
- **Pending terms** — not in the reference database; translate by judgment, record if recurring.
- **Official card effect text** — copy verbatim; do not paraphrase.
- **Slang hints** — translate by intended register (e.g. "on steroids" → 加强版), not literally.
  These are advisory; `finish` will warn if a detected slang was translated literally.
- **Style rules + Phase C acceptance checklist** for your direction.

If `prepare` reports the context lock failed (empty lock table), translate cautiously and
re-run `prepare` — the lock is what lets `finish` verify terminology.

---

### Step 2: Translate (翻译)

Open `source.pack.md` from Step 1. Translate the **full source** following the pack's
locked terms and style rules, then save to a file (e.g. `translated.txt`).

Direction-specific style reference (also embedded in the pack):

**For EN → CN**:

| Dimension | Rule |
|-----------|------|
| Tone | Bilibili player community tone, concise, punchy, allow slang |
| Sentence length | Break long English sentences into 2-3 short Chinese sentences |
| Voice | Active voice. "对手不管她" not "未被解掉" |
| Numbers | Always Arabic numerals (5点, 12人口, R3, 4P) |
| Parentheses | Chinese brackets 「（中文括号）」, not English (parens) |
| Verbs | Oral Chinese: 塞进/拍下/骗出/处理掉/赚翻/撑过/不管她/改回去 |
| Rhetoric | 比喻/夸张/反讽/嘲讽：先识别，译意图不译字面，留住"咬人味"。见 style_reference.md《修辞与语气判断》 |
| Style | Apply user's style fingerprint preferences when available |

**For CN → EN**:

| Dimension | Rule |
|-----------|------|
| Tone | Casual but natural English. Not stiff or academic. Like a native player talking |
| Sentence length | Combine short Chinese sentences into flowing English prose |
| Voice | Maintain active voice. "If left unanswered" not "If not dealt with by opponent" |
| Numbers | Arabic numerals. "5 power, 12 provision", "R3", not "Round Three" |
| Parentheses | English parentheses (), not Chinese 「（）」 |
| Slang | Preserve community slang: "nerf sponge", "abusive combo", "braindead deck" |
| Rhetoric | Preserve figurative intent & sarcasm; don't flatten irony or drain hyperbole. See style_reference.md |
| Style | Match the source's register (casual guide vs. formal analysis) |

For detailed step-by-step guidance, see `references/translation_workflow.md`.

---

### Step 3: Finish (定稿门禁)

**Run AFTER saving your translation — this is the ONLY finalization gate:**

```bash
python scripts/translate.py finish translated.txt --source source.md --direction encn
```

- **`PASS`** = all checks passed (terminology, residue, Phase C, term authority); new terms
  recorded to the auto buffer (`pending_terms.auto.md`). You may finalize.
- **`BLOCKED`** = **DO NOT FINALIZE**. Fix the reported issues and re-run until PASS.

`finish` runs every check through `completeness_guard` and additionally refuses to pass if
the context lock could not be built from the source — so terminology is never silently
skipped. Always pass `--source` and `--direction` explicitly for a trustworthy gate.

The machine-checkable rules behind `finish` live in `references/phase_c_checklist.md`.

#### If `finish` is BLOCKED — the re-translate loop (agent-driven)

`finish` calls **no LLM** and never touches your translation file. (After a
genuine PASS it runs `learn.py --auto`, which appends newly discovered terms to
the gitignored auto buffer `references/pending_terms.auto.md` — nothing else is
written; `learn.py --commit` later merges the buffer into the tracked
`pending_terms.md` review inbox.) When it reports `BLOCKED`, the agent
drives the fix loop from the violation list. Each violation carries `term`,
`expected_official`, `severity`, and `offending_quote` (the locatable snippet in the
translation; empty for "missing" — the term was dropped, so add it):

1. Read `violations` from the `finish` JSON (or the `[BLOCKED]` lines).
2. For each violation, open the translation, jump to `offending_quote`, and re-render
   that segment using `expected_official`.
3. Save the file and re-run `finish`.
4. Repeat until `all_passed`, **up to 3 rounds**. If still `BLOCKED` after 3 rounds,
   stop and hand the translation to a human — **never finalize while `BLOCKED`**.

`translate.py` is deterministic glue; all re-translation is done by the agent / human.

---

## Quick Reference

### Community Slang (Most Common)

| English | Chinese |
|---------|---------|
| no unit archetype | 气宗 |
| GN Shupe | 孽鬼店店 |
| GN Deathwish | 孽鬼吞怪 |
| Armor abuse (SK) | 互口岛 |
| Rain deck | 下雨岛 |
| Fruits / Fruits midrange | 蛆妈 / 破烂怪 |
| Arachas Swarm | 蟹蜘蛛 |
| enemy boost (NG) | 毒奶 |
| point slam | 打出大点数单位 |
| nerf sponge | 凑数的削弱 |
| abusive combo | 赖皮的组合技 |
| revert | 改回去 |

### Coin & Turn Order

昆特先后手用「硬币」术语表达，中文里「硬币」与「先手/后手」两套说法互通：

| English | Chinese | Note |
|---------|---------|------|
| blue coin | 蓝币 | = 先手 |
| red coin | 红币 | = 后手 |
| coin flip | 先后手 / 硬币 | 开局先后手归属 |

> blue coin / red coin 在 TermAuthority 已锁定为「蓝币 / 红币」（译错会被 term_enforcer 拦）。此处补充语义：**蓝币 = 先手、红币 = 后手**。原文 "going first" 或 "on blue coin" 这类表达，中文可据语境选用「先手」（叙述更自然）或「蓝币」（机制讨论）。

### Faction Names

| Abbr | Full (EN) | Full (CN) |
|------|-----------|-----------|
| MO | Monsters | 怪兽 |
| NR | Northern Realms | 北方领域 |
| NG | Nilfgaard | 尼弗迦德 |
| SK | Skellige | 史凯利格 |
| ST | Scoia'tael | 松鼠党 |
| SY | Syndicate | 辛迪加 |
| NE | Neutral | 中立 |

### Key Keyword Translations

| English | Chinese | Notes |
|---------|---------|-------|
| deploy | 部署 | Most common keyword |
| order | 指令 | Second most common |
| zeal | 狂热 | |
| doomed | 佚亡 | |
| resilience | 坚韧 | |
| veil | 遮蔽 | |
| devotion | 赤诚 | |
| formation | 列阵 | |
| disloyal | 不忠 | |
| echo | 回响 | |
| immune | 免疫 | |
| harmony | 和谐 | ST mechanic |
| thrive | 成长 | MO mechanic |
| shield | 护盾 | |
| armor | 破甲 | |
| dominance | 统御 | |
| inspire | 激励 | |
| seize | 操控 | |
| ambush | 伏击 | |
| initiative | 先机 | |
| conspiracy | 共谋 | SY mechanic |
| sabbath | 夜宴 | Yaga's token |
| deathwish | 遗愿 | MO keyword |
| defender | 卫士 | |
| purify | 净化 | |
| bloodthirst | 战狂效果 | |
