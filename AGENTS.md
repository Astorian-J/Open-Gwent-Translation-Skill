# Agent Interface

This document describes how any AI agent can use the Gwent translation skill.
The interface is purely mechanical: commands, arguments, exit codes, and JSON
schemas. No Claude Code-specific knowledge is required.

## 你现在的任务 / Your Task Now

**本 skill 一被调用 = 你现在要做昆特牌（Gwent）翻译。**
不是聊天、不是分析、不是总结——是翻译。
**This skill being loaded means: TRANSLATE Gwent text now — not chat, not analyze, not summarize.**

立刻做三件事 / Do this right now:

1. **拿到要翻译的内容** — 用户已贴在对话里；若没有，主动问「把要翻译的昆特牌文章发给我」
2. **判断方向** — 英文→中文 (`encn`) 还是 中文→英文 (`cnen`)
3. **走流程** — `translate.py prepare` → 翻译 → `translate.py finish`（见下方 Quick Start）

> 只要用户贴了昆特牌相关的中文或英文，哪怕没明说「翻译」，默认就是要翻译，直接开干。
> If the user posts Gwent text in either language without explicit instruction, default to translating it.

## Quick Start

```bash
# 1. Prepare — build the translation pack (locked terms, official effects, style rules)
python scripts/translate.py prepare source.md --date 2026-05 --type general --direction encn

# 2. Translate using the generated source.pack.md (the only LLM step, performed by the agent)

# 3. Finish — hard gate; the translation is NOT final until this PASSes
python scripts/translate.py finish translated.txt --source source.md --direction encn
```

> `translate.py` is the ONLY entry point. `auto_pipeline.py`, `phase_c_check.py`,
> `term_enforcer.py`, and `completeness_guard.py` are now **internal steps** of
> `translate.py` — do NOT run them manually. Their JSON schemas are documented
> below only for programmatic / advanced inspection of intermediate output.

## Installation

No installation step is required beyond cloning the repository. All scripts
live in `scripts/` and read reference data from `references/`. Run them from
the project root.

Requirements:
- Python 3.10 or later
- No third-party dependencies (stdlib only)

## Translation Workflow

A complete translation goes through `translate.py` — a two-command deterministic
pipeline. The agent drives only the translation step in between; everything else
is deterministic code. Do NOT run `auto_pipeline`, `phase_c_check`, `term_enforcer`,
or `completeness_guard` manually — they are internal steps of `translate.py` now.

| Step | Command | Who runs it |
|------|---------|-------------|
| 1. Prepare | `translate.py prepare source.md --date YYYY-MM --type general --direction encn` | `translate.py` (deterministic; internally calls `auto_pipeline pre`) |
| 2. Translate | Agent reads `source.pack.md`, translates the full source, saves to `translated.txt` | Agent (the only LLM step) |
| 3. Finish | `translate.py finish translated.txt --source source.md --direction encn` | `translate.py` (deterministic gate; internally runs `completeness_guard` + `learn`) |

`finish` returns `PASS` (finalize) or `BLOCKED` (fix and re-run, up to 3 rounds,
never finalize while BLOCKED). See `SKILL.md` Step 3 for the agent-driven
re-translate loop on BLOCKED.

## Global Conventions

- All scripts accept an optional `--json` flag.
- Without `--json`, output is human-readable text for terminals and logs.
- With `--json`, output is a single JSON object to stdout.
- Exit codes: `0` = success, `1` = failure or blocked.
- The JSON envelope is always:

```json
{
  "success": true,
  "exit_code": 0,
  "data": { ... },
  "errors": []
}
```

- **Translation direction**: `scan`, `phase_c_check`, `check_translation`,
  and `completeness_guard` all accept `--direction {encn,cnen}`. Direction is
  auto-detected from the translated text when omitted, but the detection is a
  character-ratio heuristic that fails on poorly-translated or mixed text (e.g.
  a barely-started CN->EN translation reads as Chinese and is misclassified).
  Since the translation workflow always knows the real direction, pass
  `--direction` explicitly in automated pipelines rather than relying on the
  fallback. The detected/used direction is reported in each command's JSON
  output. In addition, `translate.py prepare` (source-based detection),
  `check_translation`, `completeness_guard`,
  `auto_pipeline scan`, `phase_c_check`, and `term_enforcer` report a
  `direction_auto_detected` boolean in their JSON output: `true` when the
  direction came from the auto-detection fallback described above, `false`
  when it was given explicitly via `--direction`. (`term_enforcer` has no
  `--direction` flag — it takes the direction from the lock's `direction`
  field, so for it `true` means the lock carried no direction and the
  heuristic fallback ran.)

## Script Reference

### `auto_pipeline.py`

Orchestrates pre-processing and residue scanning.

#### `pre`

```bash
python scripts/auto_pipeline.py pre source.md --date YYYY-MM --type general --json
```

- `--date`: Article date in `YYYY-MM` format. Optional; used for metadata only.
- `--type`: Article type. Choices:
  - `meta` — meta report / tier list
  - `bc-proposal` — Balance Committee proposal
  - `card-analysis` — single card or small set analysis
  - `patch-notes` — official patch notes
  - `general` — default, catch-all
- `--verbose-terms`: emit the FULL `card_references` / `locked_terms` /
  `ambiguous_terms` / `pending_terms` lists. By default `--json` emits complete
  counts plus a top-5 sample of each big list (so a card-heavy article cannot
  flood agent context); if you need every locked term, pass this flag or read
  the lock file at `lock_path`.

JSON data:

```json
{
  "command": "pre",
  "source": "source.md",
  "date": "2026-05",
  "type": "general",
  "skeleton_extracted": true,
  "skeleton_path": "/tmp/skeleton.json",
  "lock_built": true,
  "lock_path": "/tmp/lock.json",
  "card_references_found": 12,
  "card_references": [
    {"english": "Geralt: Igni", "chinese": "杰洛特：伊格尼法印"}
  ],
  "slang_hints": [
    {"english": "on steroids", "intended_cn": "加强版/打了鸡血版", "literal_forbidden": "类固醇", "note": "hyperbole"}
  ],
  "slang_hints_total": 1,
  "term_authority": {
    "locked_count": 45,
    "ambiguous_count": 3,
    "pending_count": 2,
    "locked_terms": [
      {
        "canonical_en": "Off the Books",
        "chinese": "黑市买卖"
      }
    ],
    "ambiguous_terms": [
      {
        "extracted": "Geralt",
        "canonical_en": "Geralt",
        "type": "ambiguous",
        "source_ref": "ambiguous_names.md",
        "variants": [
          {"en": "Geralt: Igni", "cn": "杰洛特：伊格尼法印"}
        ]
      }
    ],
    "pending_terms": []
  }
}
```

The `term_authority` block is the **mandatory translation reference** for this
article. Agents must use the provided `chinese` values for all `locked_terms`
and must disambiguate all `ambiguous_terms` with a full subtitle variant.

#### `scan`

Direction-aware residue scan: reports English card names left in an EN->CN
translation, or Chinese card names left in a CN->EN translation. Direction is
auto-detected from the file, or set explicitly with `--direction`.

```bash
python scripts/auto_pipeline.py scan translated.txt --json
python scripts/auto_pipeline.py scan translated.txt --direction cnen --json
```

JSON data:

```json
{
  "command": "scan",
  "translated": "translated.txt",
  "direction": "encn",
  "direction_auto_detected": false,
  "residue_count": 0,
  "residues": []
}
```

### `check_translation.py`

Detailed terminology checker. Direction-aware: for EN->CN output it runs the
full terminology check set and reports English residue; for CN->EN output it
reports Chinese residue instead. Direction is auto-detected from the file, or
set explicitly with `--direction`. Optionally accepts a source file (or
pre-built lock) to run term authority enforcement, an EN->CN-only check.

```bash
python scripts/check_translation.py translated.txt --json
python scripts/check_translation.py translated.txt --source source.md --json
python scripts/check_translation.py translated.txt --direction cnen --json
```

JSON data:

```json
{
  "direction": "encn",
  "direction_auto_detected": false,
  "issue_count": 5,
  "warning_count": 1,
  "auto_fixable_count": 2,
  "auto_fixed_count": 0,
  "issues": [
    {
      "category": "provision_mix",
      "severity": "error",
      "message": "provision mix: 「12费换8战力」→ should be 「12人口换8战力」"
    }
  ],
  "warnings": [
    {
      "category": "slang_not_preserved",
      "severity": "warning",
      "message": "slang not preserved: source「on steroids」→ expected one of ['加强版', '打了鸡血版'] (avoid literal「类固醇」)"
    }
  ]
}
```

Issue categories include: `provision_mix`, `identical_numbers`,
`suspicious_order`, `forbidden_term`, `outdated_card_name`, `ambiguous_name`,
`chinese_numerals`, `passive_voice`, `english_parentheses`, `english_colon`,
`abbreviation`, `typo`, `homophone`, `deck_abbreviation`, `english_residue`,
`chinese_residue`, `term_authority_violation`.

### `phase_c_check.py`

Runs the structured Phase C self-check rules from
`references/phase_c_checklist.md`.

```bash
python scripts/phase_c_check.py translated.txt --direction encn --json
python scripts/phase_c_check.py translated.txt --source source.md --direction encn --json
```

Direction is auto-detected if omitted. Choices: `encn` (EN→CN), `cnen` (CN→EN).
The `--source` flag is required for the automated `encn-10` term authority check;
without it, the rule falls back to a manual warning.

JSON data:

```json
{
  "direction": "encn",
  "direction_auto_detected": false,
  "automated_failed": 2,
  "automated_issues": [
    {"rule_id": "encn-01", "message": "forbidden provision term: ..."}
  ],
  "manual_warning_count": 2,
  "manual_warnings": [
    {"rule_id": "encn-07", "description": "Abbreviations expanded on first use", "message": "..."}
  ],
  "ready": false
}
```

### `completeness_guard.py`

Final check. Combines terminology, residue, Phase C, and term authority checks.
Direction-aware: direction is auto-detected from the file or set with
`--direction`, and applied to every downstream check. The residue check looks
for English residue (EN→CN) or Chinese residue (CN→EN); term authority
enforcement runs in BOTH directions (the lock carries the official target each
way: EN→CN asserts the official Chinese appears in the Chinese translation,
CN→EN asserts the official English appears in the English translation). The
`term_authority` check carries a `status` field: `ran` (executed), `skipped`
(no `--source`/lock provided; not run), or `error` (the check itself raised).
(`not_applicable` is a reserved value that current code never emits.)

```bash
python scripts/completeness_guard.py translated.txt --json
python scripts/completeness_guard.py translated.txt --source source.md --json
python scripts/completeness_guard.py translated.txt --source source.md --direction cnen --json
```

The `--source` flag is required for the `term_authority` check; without it,
term authority enforcement is skipped.

JSON data:

```json
{
  "direction": "encn",
  "direction_auto_detected": false,
  "all_passed": false,
  "blocked": true,
  "checks": [
    {"name": "file_exists", "passed": true, "issue_count": 0, "message": "..."},
    {"name": "terminology", "passed": false, "issue_count": 3, "message": "..."},
    {"name": "residue_scan", "passed": true, "issue_count": 0, "message": "..."},
    {"name": "phase_c", "passed": false, "issue_count": 1, "message": "..."},
    {"name": "term_authority", "passed": false, "issue_count": 2, "status": "ran", "message": "..."}
  ]
}
```

### `term_enforcer.py`

Term authority enforcement. Validates that locked terms from the pre-translation
phase are correctly used in the translation. The JSON output also reports
`direction_auto_detected` (see Global Conventions above).

```bash
python scripts/term_enforcer.py translated.txt --lock lock.json --json
python scripts/term_enforcer.py translated.txt --source source.md --json
```

JSON data:

```json
{
  "violation_count": 2,
  "violations": [
    {
      "term": "Off the Books",
      "canonical_en": "Off the Books",
      "expected_cn": "黑市买卖",
      "found_in_translation": "OTB",
      "issue_type": "term_left_untranslated",
      "context": "...",
      "severity": "error"
    }
  ],
  "pass_count": 43,
  "locked_terms_checked": 45,
  "direction_auto_detected": false
}
```

Issue types:
- `term_left_untranslated`: English term, abbreviation, or alias left in the target text.
- `term_missing_or_literal`: Locked term is absent or possibly translated with an unrecognized phrase.
- `ambiguous_not_disambiguated`: Ambiguous base name used without specifying the variant.

### `health_check.py`

Verifies that the skill installation is complete and functional.

```bash
python scripts/health_check.py --json
```

JSON data:

```json
{
  "pass_count": 32,
  "fail_count": 0,
  "warn_count": 0,
  "info_count": 4,
  "results": [
    {"status": "PASS", "message": "Correction rules: correction_guide.md"}
  ]
}
```

## Utility Scripts

The following scripts also support `--json` and can be used independently:

- `scripts/lookup.py` — Search reference files for a term.
- `scripts/context_lock.py` — Build/check per-document terminology locks.
- `scripts/term_enforcer.py` — Enforce locked terms in a translation.
- `scripts/format_skeleton.py` — Extract/restore Markdown structure.
- `scripts/diff_review.py` — Compare source and translation.
- `scripts/learn.py` — Discover new terms from the source text.
- `scripts/backtranslate.py` — Heuristic back-translation validation.

## Reference Files

All translation rules and data live in `references/`:

- `phase_c_checklist.md` — Machine-checkable Phase C rules.
- `card_names_4lang.json` — Verified English↔Chinese card name mappings (build-time generated; see `card_overrides.md` for hand-maintained aliases/renamed).
- `terminology_map.md` — Core concept translations.
- `keywords_map.md` — Game keyword translations.
- `competitive_terms.md` — Community slang and deck names.
- `correction_guide.md` — Mandatory terminology swaps.
- `common_pitfalls.md` — Common error patterns.
- `cn_fuzzy_fixes.md` — Chinese typo/abbreviation fixes.

## Notes for Agent Implementers

- Do not finalize a translation while `completeness_guard.py` reports BLOCKED.
- Always pass `--source source.md` to `completeness_guard.py` and
  `phase_c_check.py` so that term authority enforcement runs automatically.
- Use the `term_authority.locked_terms` block from `auto_pipeline.py pre` as the
  mandatory translation reference; never translate those terms literally.
- `phase_c_check.py` returns `ready: true` when automated checks pass, but
  manual warnings may still require review.
- After a PASS, `translate.py finish` runs `learn.py --auto`, which may append
  new terms to `references/pending_terms.md`.
  These are intended for verification and should not be silently committed.
- The default (non-JSON) output is formatted for readability in terminals and
  logs; use `--json` when building deterministic tool pipelines.
