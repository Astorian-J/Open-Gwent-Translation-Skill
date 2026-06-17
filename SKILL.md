---
name: gwent-translation-style
description: |
  Gwent (昆特牌) bidirectional article translation (EN↔CN) with community slang and Bilibili player tone.
  Triggered by: Gwent translation, 昆特牌翻译, 平衡委员会, meta report translation, 英文翻译.
  Enforces: short sentences, community slang, active voice, strict terminology.
agent_created: true
---

# Gwent Translation Style (昆特牌翻译风格)

> For non-Claude agents and programmatic usage, see [AGENTS.md](AGENTS.md).

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

> **IMPORTANT**: The full pipeline below is required for every translation.
> Skipping steps or calling sub-scripts manually may produce inconsistent results.
> Use the single automation command provided at each phase.

---

### Phase A: Pre-Translation (Preprocessing)

**Run this command FIRST — before you start translating:**

```bash
python scripts/auto_pipeline.py pre source.md --date YYYY-MM --type general
```

This automatically performs context setup, reference loading, context lock,
and format skeleton extraction. These steps should not be run manually.

> **TRANSLATION DISCIPLINE**: When the pipeline outputs a **card name quick reference table**
> (a list of English card names and their Chinese translations found in the source),
> use this table as your sole reference for card names during translation.
> Do not rely on memory or skip unfamiliar names. Every card name in the table
> should be translated using the provided Chinese term.

---

### Phase B: Translation

Translate the text according to the direction-specific constraints below.

**For EN → CN**:

| Dimension | Rule |
|-----------|------|
| Tone | Bilibili player community tone, concise, punchy, allow slang |
| Sentence length | Break long English sentences into 2-3 short Chinese sentences |
| Voice | Active voice. "对手不管她" not "未被解掉" |
| Numbers | Always Arabic numerals (5点, 12人口, R3, 4P) |
| Parentheses | Chinese brackets 「（中文括号）」, not English (parens) |
| Verbs | Oral Chinese: 塞进/拍下/骗出/处理掉/赚翻/撑过/不管她/改回去 |
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
| Style | Match the source's register (casual guide vs. formal analysis) |

For detailed step-by-step guidance, see `references/translation_workflow.md`.

---

### Phase C: Self-Check (Before Output)

**Run this checklist before finalizing the translation:**

**EN → CN**:
- [ ] No "费/费用" in formal provision contexts
- [ ] "X for Y" translated as "Y人口X战力" (not reversed, not identical numbers)
- [ ] Passive voice converted to active
- [ ] Arabic numerals throughout
- [ ] **No English residue**: All card names from the quick reference table are translated to Chinese
- [ ] Ambiguous card names include full subtitle (check ambiguous_names.md)
- [ ] Abbreviations expanded on first use (BC, OP, CA, etc.)
- [ ] Chinese parentheses 「（）」used, not English ()
- [ ] Chinese colon "：" in card names
- [ ] Context lock terms used consistently throughout article

**CN → EN**:
- [ ] "人口" translated as "provision" (formal), "cost" only for SY Tribute
- [ ] "Y人口X战力" translated as "X for Y" (correct order)
- [ ] **No Chinese residue**: All Chinese card names are translated to English
- [ ] English parentheses () used, not Chinese 「（）」
- [ ] English colon ":" in card names (e.g., "Geralt: Igni")
- [ ] Community slang preserved: 气宗 → "no unit", 互口岛 → "armor abuse"
- [ ] Oral verbs mapped naturally: 赚翻 → "generates huge value", 撑过 → "survives"
- [ ] Tone: casual but not broken English. Reads like a native player wrote it

The above checklist is also available in machine-checkable form in
`references/phase_c_checklist.md`. After saving your translation, run:

```bash
python scripts/phase_c_check.py translated.txt
```

This executes all automated rules and lists any manual items that still
require review. The final `completeness_guard.py` gate also runs
Phase C checks automatically.

---

### Phase D: Post-Translation (Verification & Learning)

**Run this command AFTER you have saved the translation:**

```bash
python scripts/auto_pipeline.py post source.md translated.txt
```

This automatically performs terminology check, consistency verification,
and records new terms to `pending_terms.md`. Skipping this step may leave
unrecorded terms.

If you need to re-scan a translated file for English residue only:
```bash
python scripts/auto_pipeline.py scan translated.txt
```

---

### Phase E: Completeness Guard (Final Gate)

**Before finalizing the translation, run:**

```bash
python scripts/completeness_guard.py translated.txt
```

If this script reports any missing steps, resolve them before
marking the translation complete. The guard output should not be ignored.

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
