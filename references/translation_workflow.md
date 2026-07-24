# Translation Workflow Detail (翻译流程详解)

> This file contains the detailed step-by-step translation workflow.
> The main SKILL.md references this file for agents who need in-depth guidance.
> Most agents only need the two commands in SKILL.md.

---

## Step 0: Context Setup

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

## Step 1: Load References

Read direction-specific references first:

**For EN → CN**: Load these references
1. `references/correction_guide.md` — Mandatory rules (must-fix items)
2. `references/style_reference.md` — Style examples and proven patterns
3. `references/terminology_map.md` — Term lookup table (EN → CN)
4. `references/keywords_map.md` — Game keyword translations
5. `references/card_names_4lang.json` — Card name mappings (EN↔CN; build-time generated, not in git)
6. `references/ambiguous_names.md` — Cards with multiple versions
7. `references/competitive_terms.md` — Competitive/community slang
8. `references/common_pitfalls.md` — Systematic error patterns
9. `references/category_map.md` — Card category translations
10. `references/version_map.md` — Expansion timeline for date-aware translation
11. `references/style_fingerprint.md` — User's personal preferences

**For CN → EN**: Load these references
1. `references/reverse_terminology_map.md` — Reverse term lookup (CN → EN)
2. `references/cn_fuzzy_fixes.md` — Chinese fuzzy word fixes (typos, homophones, deck abbreviations)
3. `references/card_names_4lang.json` — Card name mappings (Chinese name → English; build-time generated)
4. `references/keywords_map.md` — Game keyword translations (CN → EN)
5. `references/competitive_terms.md` — Community slang (CN → EN)
6. `references/version_map.md` — Expansion timeline
7. `references/ambiguous_names.md` — For card name verification

## Step 2: Build Context Lock (for long articles)

For articles longer than 5 paragraphs, build a terminology lock table:

1. Scan source text for proper nouns (card names, abilities, abbreviations)
2. For each term, look up in references and decide translation
3. Record in mental lock table: "Term" → "翻译" (locked for this article)
4. Subsequent mentions MUST use the same translation

**This is done automatically by `auto_pipeline.py pre`.**
If you need to manually edit the lock table:
```bash
python scripts/context_lock.py add "English Term" "中文翻译" --lock /tmp/lock.json
```

## Step 3: Extract Format Skeleton (for formatted articles)

If the source has Markdown/HTML formatting:

1. Extract the format skeleton (headings, lists, blockquotes, tables)
2. Translate only the text content, preserving all formatting
3. Restore the skeleton with translated content

**Format extraction is done automatically by `auto_pipeline.py pre`.**
If the user later provides translated chunks, restore with:
```bash
python scripts/format_skeleton.py restore /tmp/skeleton.json translated_chunks.txt --output result.md
```

## Step 5: Terminology Check

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

## Step 6: Number Format Check

**EN → CN**:
- "X for Y" format: X = power, Y = provision
- Output: "Y人口X战力" (e.g., "6 for 5" → "5人口6战力")
- Never mix: formal provision always 人口, never 费

**CN → EN**:
- "Y人口X战力" format: Y = provision, X = power
- Output: "X for Y" (e.g., "5人口6战力" → "6 for 5")
- Use "provision" in formal, "cost" only for SY Tribute context

## Step 8: Output

Present the final translation. If user provided their own translation,
first output analysis, then the corrected version.

Save the final translation to a file (e.g., `translated.txt`) before proceeding to post-processing.

## Step 9: Learn (Self-Evolution)

After delivering the translation, analyze the source text for terms not in
our reference database:

1. **Scan for unknown terms** in the English source:
   - Card names with colons (e.g., "New Card: Subtitle")
   - Capitalized multi-word phrases
   - All-caps abbreviations not in competitive_terms.md
   - Game keywords not in keywords_map.md

2. **Check against existing references**:
   - Search terminology_map.md, card_names_4lang.json, keywords_map.md, competitive_terms.md
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
