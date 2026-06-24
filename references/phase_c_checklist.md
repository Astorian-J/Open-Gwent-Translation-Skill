---
name: phase_c_checklist
description: |
  Machine-checkable rules derived from SKILL.md Phase C self-checklist.
  Loaded by scripts/phase_c_check.py and validated by health_check.py.
  Rules are grouped by translation direction. Each rule has a check_type
  indicating whether it can be verified automatically or requires manual review.
---

# Phase C Self-Check — Machine-Checkable Rules

Rules in this file mirror the human checklist in SKILL.md Phase C.
Automated rules are enforced by `scripts/phase_c_check.py`.
Manual rules are surfaced as warnings that a human must confirm.

## EN → CN Rules

| ID | Description | Check Type | Pattern | Issue Message | Notes |
|----|-------------|------------|---------------------|---------------|-------|
| encn-01 | No "费/费用" in formal provision contexts | regex_forbidden | `(?<![低高])费(?:用)?(?!(?:战士|铜卡|单位|核心))` | forbidden provision term: 「{match}」— use "人口" instead of "费/费用" in formal contexts | Allows casual "低费铜卡", "高费战士", "4费战士"; see correction_guide.md |
| encn-02 | "X for Y" has correct order and no identical numbers | regex_forbidden | `(\d+)\s*人口\s*\1\s*点?\s*战力` | identical numbers: 「{match}」— may indicate reversed or duplicated X for Y | Also catches "5人口5战力" mistakes |
| encn-03 | Passive voice converted to active | regex_forbidden | `(?:未被\|被解\|被削\|被增强\|被削弱\|被打出\|被移除)` | passive voice: convert "{match}" to active voice | Matches common passive indicators from correction_guide.md |
| encn-04 | Arabic numerals throughout | regex_forbidden | `[一二三四五六七八九十]+点\|[一二三四五六七八九十]+人口` | Chinese numerals: 「{match}」— use Arabic numerals | Covers 五点, 十二人口, etc. Parser unescapes \| to regex alternation |
| encn-05 | No English residue | reference | card_names.md | English residue: untranslated card name | Delegated to check_translation.py residue scanner |
| encn-06 | Ambiguous card names include full subtitle | reference | ambiguous_names.md | ambiguous name: specify full subtitle | Delegated to check_translation.py ambiguous-name scanner |
| encn-07 | Abbreviations expanded on first use | manual | competitive_terms.md | abbreviation used — confirm it is expanded on first use | Requires semantic/contextual judgment |
| encn-08 | Chinese parentheses used, not English () | regex_forbidden | `\([^）]*\)` | English parentheses: 「{match}」— use Chinese brackets 「（）」 | English parens in Chinese text |
| encn-09 | Chinese colon "：" in card names | regex_forbidden | `[一-鿿][A-Za-z]+:` | English colon after Chinese: 「{match}」— use Chinese colon "：" | e.g. "杰洛特:Igni" |
| encn-10 | Context lock terms used consistently | reference | context_lock.json | context lock violation: {issue} | Requires --source to run term_enforcer.py |
| encn-11 | Figurative language intent preserved | manual | style_reference.md | rhetoric — confirm metaphor/sarcasm/hyperbole was translated by intent, not literally (no flattened irony) | See 修辞与语气判断 section |
| encn-12 | Quoted card effects match official text | manual | effect_text.json | effect — when quoting a card's ability, confirm it matches the official CN ability verbatim (from pre-translation OFFICIAL EFFECT TEXT table) | Long sentences can't be term-locked; injection + manual |

## CN → EN Rules

| ID | Description | Check Type | Pattern | Issue Message | Notes |
|----|-------------|------------|---------------------|---------------|-------|
| cnen-01 | "人口" translated as "provision" (formal) | regex_forbidden | `人口` | Chinese residue: "人口" should be "provision" (or "cost" only for SY Tribute) | Exception for SY Tribute cost is not machine-distinguishable |
| cnen-02 | "Y人口X战力" translated as "X for Y" | manual | — | X for Y format — verify correct order and no Chinese residue | Requires source-aware verification |
| cnen-03 | No Chinese residue: all Chinese card names translated | reference | card_names.md (reverse) | Chinese residue: untranslated Chinese card name | Reverse lookup of card_names.md |
| cnen-04 | English parentheses () used, not Chinese 「（）」 | regex_forbidden | `[（）]` | Chinese parentheses: 「{match}」— use English parentheses () | Chinese brackets in English text |
| cnen-05 | English colon ":" in card names | regex_forbidden | `[一-鿿]：` | Chinese colon in card name: 「{match}」— use English colon ":" | e.g. "Geralt：Igni" |
| cnen-06 | Community slang preserved | manual | competitive_terms.md | community slang — verify English slang equivalents are preserved | Quality check; see quick reference table |
| cnen-07 | Oral verbs mapped naturally | manual | correction_guide.md | oral verbs — verify natural English mapping | Quality check; e.g. 赚翻 → generates huge value |
| cnen-08 | Tone: casual but not broken English | manual | style_reference.md | tone — confirm casual native-player register | Requires human stylistic judgment |
| cnen-09 | Figurative language & sarcasm preserved | manual | style_reference.md | rhetoric — confirm figurative intent and sarcasm survive in English, irony not flattened | See 修辞与语气判断 section |
| cnen-10 | Quoted card effects match official text | manual | effect_text.json | effect — when quoting a card's ability, confirm it matches the official EN ability from effect_text.json | Long sentences can't be term-locked; manual |

## Check Types

- **regex_forbidden**: Pattern must NOT appear in the translated text.
- **regex_required**: Pattern MUST appear at least once in the translated text.
- **regex**: Pattern is used to validate/confirm a format (informational or conditional).
- **reference**: Requires cross-referencing another reference file (card_names.md, ambiguous_names.md, etc.).
- **manual**: Cannot be machine-verified; surfaced as a warning for human confirmation.

## Validation

`scripts/health_check.py` ensures:

1. This file exists and is readable.
2. Every rule row has the required columns (ID, Description, Check Type, Pattern / Reference, Issue Message).
3. Every `regex_forbidden`, `regex_required`, and `regex` rule has a compilable regex pattern.
4. Rule IDs are unique across both directions.

`scripts/phase_c_check.py` uses these rules to scan a translation file and report
which automated checks pass or fail, plus which manual checks need review.
