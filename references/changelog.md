# Changelog

## 2026-06-24 — Figurative Language & Tone Judgment

### Added
- `references/style_reference.md`: new section 《修辞与语气判断》 — rules + a
  real-example table for metaphor / hyperbole / sarcasm / mockery
  (译意图不译字面，保留"咬人味"). Grounded in an actual BC33 Reddit translation
  (on steroids / loud design / sweet spot / guess what / sink / toxic /
  dismissive tone).
- `SKILL.md` Phase B: added a "Rhetoric" row to both the EN→CN and CN→EN tables.
- `references/phase_c_checklist.md`: added manual checks encn-11 / cnen-09
  (figurative intent preserved, irony not flattened).

### Why
Translation notes from real BC content showed figurative / sarcastic lines were
handled inconsistently — some kept the bite (沉底 / 你猜怎么着), others got flattened
(sweet spot → 该去的位置) or translated too literally (loud design → 太大声). The
skill steered the overall tone but never told the agent to judge rhetoric on a
per-sentence basis.

## 2026-06-03 — Server Verification & Restructure

### Structural Changes
- Reorganized from flat files to `references/` subdirectory
- Eliminated redundancy between SKILL.md and reference files
- Added `keywords_map.md` (game keyword translations from server data)
- Added `card_names.md` with server-verified mappings
- Added `changelog.md` (this file)

### Corrections (from server card_data.json verification)
- `沙暴` → `沙尘暴` [202205]
- `伊魅柯` → `伊魅珂` [202370]
- `埃斯特·图尔赛赫` → `埃斯特·图尔赛克` [202883]
- `咯咯哒 艾伯伦特` → `"咯咯哒"艾伯伦特` (quote format)
- `布洛妮` → `布蕾恩` [142209]
- `雷吉斯的鸣镝动怒` → `雷吉斯：血欲化身` [202195] (原映射错误: 鸣镝动怒是领袖名)
- `怀柔` → `战术决策` [200164] (原映射错误: 怀柔是怀柔兼济的简称)
- `夜宴` → `女巫夜宴` [203054]

### Fixes to Incorrect Mappings
- `Tactical Decision` was incorrectly mapped to `怀柔`; corrected to `战术决策`
- `Regis: Bloodlust` was incorrectly mapped to `雷吉斯的鸣镝动怒`; corrected to `雷吉斯：血欲化身`
- Added note: "蟹蜘蛛" is community slang for deck/leader, not a single card

### Added
- 42 verified leader names
- 50+ game keywords with frequencies from server data
- Faction full names (English + Chinese)
- Self-check checklist in SKILL.md workflow

## 2026-06-03 — Supplemental References & Auto-Detection

### New Reference Files
- `ambiguous_names.md` — 40+ cards with multiple versions (e.g., 杰洛特 x6, 雷吉斯 x4, 特莉丝 x4)
- `competitive_terms.md` — 150+ competitive/community terms, including blog glossary data (16 terms from https://cngwentbd.top/glossary/)
- `common_pitfalls.md` — 7 categories of systematic errors with severity levels
- `category_map.md` — 60+ card category translations (人类, 猎魔人, 吸血鬼, 构造体, etc.)

### Script Enhancements (check_translation.py)
- Auto-detects ambiguous card names (flags "杰洛特" without subtitle)
- Auto-detects abbreviations (BC, OP, CA, etc.) and suggests expansion
- Auto-detects English parentheses and English colons
- Auto-detects Chinese numerals
- Rules loaded dynamically from references/ (no hardcoded duplication)
- Fixed word-boundary regex for CJK+Latin mixed text

## 2026-06-03 — Self-Evolution (Learn Mode)

### New: Learning System
- `scripts/learn.py` — Scans source+translated text to discover unknown terms
  - Detects card names with colons, capitalized phrases, all-caps abbreviations
  - Compares against all reference files to find gaps
  - Outputs preview or auto-writes to pending_terms.md
- `references/pending_terms.md` — Buffer for unverified terms
  - Human-reviewed before moving to confirmed references
  - Prevents pollution of verified data with uncertain translations
- SKILL.md Step 7: Learn — Post-translation self-evolution workflow
  - Scan → Compare → Record → Suggest
  - Never writes directly to confirmed files without human verification

### Self-Evolution Design
```
Translation ──► Detect Unknown Terms ──► pending_terms.md
                                            │
                         Human Review ◄─────┘
                                            │
                         Confirmed ──► terminology_map.md / card_names.md
```

## 2026-06-03 — Advanced Features (6 New Capabilities)

### 1. Version-Aware Translation (版本感知)
- `references/version_map.md` — Expansion timeline with card ID prefixes
- Date-based lookup rules for pre-2020 / 2020-2021 / post-2021 articles
- Resolves ambiguous card names by article date (e.g., Regis base vs. Regis: Rebirth)

### 2. Context Lock (上下文一致性锁)
- `scripts/context_lock.py` — Per-document terminology lock table
- Build lock from source → Lock translations → Enforce consistency across article
- Prevents "蟹蜘蛛" in paragraph 3 and "蛛群" in paragraph 15

### 3. Format Skeleton Preservation (格式骨架保留)
- `scripts/format_skeleton.py` — Extract/restore Markdown structure
- Preserves headings, lists, blockquotes, tables while translating content only
- Separates format from content for clean translation workflow

### 4. Diff Review Mode (审校差异模式)
- `scripts/diff_review.py` — Structured comparison of source vs. user translation
- Detects: terminology errors, numeric mismatches, omissions, additions
- Output grouped by severity (high/medium/low) with specific fix suggestions
- Does NOT retranslate—only analyzes and reports issues

### 5. Back-Translation Validation (回译验证)
- `scripts/backtranslate.py` — Framework for semantic drift detection
- Compares original English with back-translated English from Chinese output
- Flags: missing key information, wrong numbers, reversed causality
- Requires LLM for actual back-translation step

### 6. Style Fingerprint (个性化风格指纹)
- `references/style_fingerprint.md` — User's personal translation preferences
- Records term choice distribution (e.g., nerf → 削弱 80% / 来一刀 20%)
- Tracks preferred oral verbs, sentence split ratio, formatting choices
- Updated after each user correction session

### SKILL.md Workflow Restructure
- Added Step 0: Context Setup (date, type, style fingerprint)
- Added Step 2: Context Lock (for long articles)
- Added Step 3: Format Skeleton (for formatted articles)
- Renumbered subsequent steps
- Added "Special Modes" section for Diff Review and Back-Translation

## 2026-06-03 — Workflow Tools (3 New Scripts)

### 1. lookup.py — Terminology Quick Search
- One-command search across all 13 reference files
- Exact match + fuzzy matching support
- Groups results by source file with formatted output
- Usage: `python scripts/lookup.py "部署"`

### 2. translate.py — Workflow Orchestrator
- Chains all 6 workflow steps into a single command
- Auto-detects article context (date → version range)
- Outputs step-by-step translation guide with next actions
- Supports `--check-only` mode for post-translation verification
- Usage: `python scripts/translate.py article.md --date 2026-05`

### 3. health_check.py — Skill Health Check
- Verifies all 13 reference files and 7 scripts are present
- Checks SKILL.md structure and required sections
- Tests script syntax and basic functionality
- Data integrity checks (card count, pending terms, version history)
- Outputs color-coded PASS/FAIL/WARN/INFO summary
- Usage: `python scripts/health_check.py`

## 2026-06-03 — Bidirectional Translation Support

### CN → EN Translation
- `references/reverse_terminology_map.md` — Reverse term lookup (中文 → 英文)
- Covers: core terms, number formulas, slang reverse mappings, oral verbs
- Style notes for preserving Bilibili tone in natural English

### Updated Components
- SKILL.md: Split workflow into EN→CN and CN→EN variants
- Added direction-specific reference loading instructions
- Added CN→EN self-check checklist
- lookup.py: Searches both terminology_map.md and reverse_terminology_map.md
- health_check.py: Verifies reverse_terminology_map.md exists

## 2026-05-30 — Initial Release

### Based On
- 4 rounds of manual correction by 进
- Triangulation: program translation vs manual correction vs source
- Shinmiri-Lerio three-way comparison

### Key Rules Established
- provision → 人口 (formal), "5P"/"4费" (casual)
- "X for Y" → "Y人口X战力" format
- Active voice mandate
- Community slang standardization (气宗, 孽鬼店店, 互口岛, etc.)
