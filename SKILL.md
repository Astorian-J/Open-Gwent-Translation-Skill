---
name: gwent-translation-style
description: |
  Gwent (昆特牌) bidirectional article translation (EN↔CN) with community slang and Bilibili player tone.
  Triggered by: Gwent translation, 昆特牌翻译, 平衡委员会, meta report translation, 英文翻译.
  Enforces: short sentences, community slang, active voice, strict terminology.
agent_created: true
---

# Gwent Translation Style (昆特牌翻译风格)

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

> ⚠️ **MANDATORY**: Every translation **MUST** execute the full pipeline below.
> Do NOT skip steps. Do NOT manually call sub-scripts one by one.
> Use the single automation command provided at each phase.

### Phase A: Pre-Translation (Preprocessing)

**Run this command FIRST — before you start translating:**

```bash
python scripts/auto_pipeline.py pre source.md --date YYYY-MM --type general
```

This automatically performs Step 0~3 (context setup, reference loading,
context lock, and format skeleton extraction). Do NOT run these steps manually.

> **TRANSLATION DISCIPLINE**: When the pipeline outputs a **card name quick reference table**
> (a list of English card names and their Chinese translations found in the source),
> you **MUST** use this table as your sole reference for card names during translation.
> Do NOT rely on memory. Do NOT skip unfamiliar names. Every card name in the table
> must be translated using the provided Chinese term.

---

### Step 0: Context Setup

Before translating, determine the article context:

1. **Article date/version**: Check the article's publication date or expansion reference
   - Pre-2020: Base game cards only (11xxxx-16xxxx prefixes)
   - 2020-2021: Include 202xxx cards (Master Mirror, Witcher)
   - Post-2021: All cards including 203xxx (Black Sun onwards)
   - See `references/version_map.md` for full timeline

2. **Article type**: Meta report, BC proposal, card analysis, patch notes?
   - Meta reports: Casual tone, community slang OK
   - BC proposals: Semi-formal, precise terminology
   - Card analysis: Technical, detailed mechanics

3. **Load style fingerprint** (`references/style_fingerprint.md`):
   - Check user's term preferences (nerf → 削弱/来一刀)
   - Apply user's preferred oral verbs
   - Use user's consistent formatting choices

### Step 1: Load References

Read direction-specific references first:

**For EN → CN**: Load these references
1. `references/correction_guide.md` — Mandatory rules (must-fix items)
2. `references/style_reference.md` — Style examples and proven patterns
3. `references/terminology_map.md` — Term lookup table (EN → CN)
4. `references/keywords_map.md` — Game keyword translations
5. `references/card_names.md` — Card name mappings
6. `references/ambiguous_names.md` — Cards with multiple versions
7. `references/competitive_terms.md` — Competitive/community slang
8. `references/common_pitfalls.md` — Systematic error patterns
9. `references/category_map.md` — Card category translations
10. `references/version_map.md` — Expansion timeline for date-aware translation
11. `references/style_fingerprint.md` — User's personal preferences

**For CN → EN**: Load these references
1. `references/reverse_terminology_map.md` — Reverse term lookup (CN → EN)
2. `references/cn_fuzzy_fixes.md` — Chinese fuzzy word fixes (typos, homophones, deck abbreviations)
3. `references/card_names.md` — Card name mappings (Chinese name → English)
4. `references/keywords_map.md` — Game keyword translations (CN → EN)
5. `references/competitive_terms.md` — Community slang (CN → EN)
6. `references/version_map.md` — Expansion timeline
7. `references/ambiguous_names.md` — For card name verification

### Step 2: Build Context Lock (for long articles)

For articles longer than 5 paragraphs, build a terminology lock table:

```
1. Scan source text for proper nouns (card names, abilities, abbreviations)
2. For each term, look up in references and decide translation
3. Record in mental lock table: "Term" → "翻译" (locked for this article)
4. Subsequent mentions MUST use the same translation
```

**This is done automatically by `auto_pipeline.py pre`.**
If you need to manually edit the lock table:
```bash
python scripts/context_lock.py add "English Term" "中文翻译" --lock /tmp/lock.json
```

### Step 3: Extract Format Skeleton (for formatted articles)

If the source has Markdown/HTML formatting:

1. Extract the format skeleton (headings, lists, blockquotes, tables)
2. Translate only the text content, preserving all formatting
3. Restore the skeleton with translated content

**Format extraction is done automatically by `auto_pipeline.py pre`.**
If the user later provides translated chunks, restore with:
```bash
python scripts/format_skeleton.py restore /tmp/skeleton.json translated_chunks.txt --output result.md
```

### Step 4: Translate with Constraints

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

### Step 5: Terminology Check

**For EN → CN**: Check against correction_guide.md.

| Wrong | Right | Context |
|-------|-------|---------|
| 费/费用/消耗 (formal) | 人口 | provision in deck-building |
| 出场率 | 登场率 | play rate |
| 惩罚卡牌 | 解场卡 | removal card |
| 修血 | 蹭血 | ping damage |
| 站住/存活 | 撑过 | survive |
| 力量/强度 | 战力 | power |

**For CN → EN**: Check against reverse_terminology_map.md.

| Wrong | Right | Context |
|-------|-------|---------|
| cost/fee (deck-building) | provision | 人口 → provision |
| appearance rate | play rate | 登场率 → play rate |
| penalty card | removal card | 解场卡 → removal card |
| health damage | ping damage | 蹭血 → ping damage |
| stand/survive | survive / last through | 撑过 → survive |
| strength | power | 战力 → power |

Exceptions:
- EN → CN: "synergy" → 协同配合 (technical), 康博 (card review), 配合 (general)
- CN → EN: "康博" → combo (casual), synergy (technical)

### Step 6: Number Format Check

**EN → CN**:
- "X for Y" format: X = power, Y = provision
- Output: "Y人口X战力" (e.g., "6 for 5" → "5人口6战力")
- Never mix: formal provision always 人口, never 费

**CN → EN**:
- "Y人口X战力" format: Y = provision, X = power
- Output: "X for Y" (e.g., "5人口6战力" → "6 for 5")
- Use "provision" in formal, "cost" only for SY Tribute context

### Step 7: Self-Check

Before output, verify based on direction:

**EN → CN checklist**:
- [ ] No "费/费用" in formal provision contexts
- [ ] "X for Y" translated as "Y人口X战力" (not reversed, not identical numbers)
- [ ] Parentheses terminology matches body text
- [ ] Passive voice converted to active
- [ ] Arabic numerals throughout
- [ ] Card names match card_names.md (confirmed section)
- [ ] **No English residue**: All card names from the quick reference table are translated to Chinese
- [ ] Ambiguous card names include full subtitle (check ambiguous_names.md)
- [ ] Abbreviations expanded on first use (BC, OP, CA, etc.)
- [ ] Chinese parentheses 「（）」used, not English ()
- [ ] Chinese colon "：" in card names
- [ ] Context lock terms used consistently throughout article
- [ ] Format preserved (headings, lists, tables match source structure)

**CN → EN checklist**:
- [ ] "人口" translated as "provision" (formal), "cost" only for SY Tribute
- [ ] "Y人口X战力" translated as "X for Y" (correct order)
- [ ] **No Chinese residue**: All Chinese card names are translated to English (verify with card_names.md reverse lookup)
- [ ] English parentheses () used, not Chinese 「（）」
- [ ] English colon ":" in card names (e.g., "Geralt: Igni")
- [ ] Community slang preserved: 气宗 → "no unit", 互口岛 → "armor abuse"
- [ ] Oral verbs mapped naturally: 赚翻 → "generates huge value", 撑过 → "survives"
- [ ] Tone: casual but not broken English. Reads like a native player wrote it
- [ ] Short Chinese sentences combined into flowing English prose
- [ ] Card names verified against card_names.md reverse lookup

### Step 8: Output

Present the final translation. If user provided their own translation,
first output analysis, then the corrected version.

Save the final translation to a file (e.g., `translated.txt`) before proceeding to post-processing.

---

### Phase B: Post-Translation (Verification & Learning)

**Run this command AFTER you have saved the translation:**

```bash
python scripts/auto_pipeline.py post source.md translated.txt
```

This automatically performs terminology check, consistency verification,
and records new terms to `pending_terms.md`. Do NOT skip this step.

### Step 9: Learn (Self-Evolution)

After delivering the translation, analyze the source text for terms not in
our reference database:

1. **Scan for unknown terms** in the English source:
   - Card names with colons (e.g., "New Card: Subtitle")
   - Capitalized multi-word phrases
   - All-caps abbreviations not in competitive_terms.md
   - Game keywords not in keywords_map.md

2. **Check against existing references**:
   - Search terminology_map.md, card_names.md, keywords_map.md, competitive_terms.md
   - If the term is already covered, skip
   - If the term is new, note it

3. **Record to pending buffer**:
   - Add new term + suggested translation to `references/pending_terms.md`
   - Format: see existing entries in that file
   - Mark confidence as `low` until verified

4. **Suggest to user** (brief, at end of response):
   - "本次翻译中发现 X 个新术语已记录到 pending_terms.md，请审核后移入正式库"

**Important**: Never write directly to the confirmed reference files.
Always use pending_terms.md as the buffer. Only move to confirmed files
after human verification against server data or official sources.

**Learning is done automatically by `auto_pipeline.py post`.**
Only run the learning script manually if the pipeline was skipped:
```bash
python scripts/learn.py source.txt translated.txt --auto
```

## Special Modes

### Diff Review Mode (审校差异模式)

When user provides their own translation for review:

1. Do NOT retranslate from scratch
2. Run a structured diff analysis:
   - Check terminology against correction_guide.md
   - Check numbers are preserved and not reversed
   - Check for omissions (key terms from source missing in translation)
   - Check for additions (information not in source)
   - Check tone consistency

To use the diff review script:
```bash
python scripts/diff_review.py source.txt user_translation.txt --output report.md
```

Output format: grouped by severity (high/medium/low), with specific suggestions.

### Back-Translation Validation (回译验证)

For critical translations (e.g., official announcements):

1. After finalizing Chinese translation, translate it back to English
2. Compare back-translation with original for semantic drift
3. Flag: missing key information, wrong numbers, reversed causality

To use the back-translation script:
```bash
# Step 1: Back-translate Chinese to English (via LLM)
# Step 2: Compare
python scripts/backtranslate.py source.txt translated.txt backtranslated.txt
```

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
