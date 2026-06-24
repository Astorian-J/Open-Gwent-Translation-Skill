# Agent Interface

This document describes how any AI agent can use the Gwent translation skill.
The interface is purely mechanical: commands, arguments, exit codes, and JSON
schemas. No Claude Code-specific knowledge is required.

## Quick Start

```bash
# 1. Pre-process a source article
python scripts/auto_pipeline.py pre source.md --date 2026-05 --type general --json

# 2. Translate the article (performed by the agent)

# 3. Post-process and verify
python scripts/auto_pipeline.py post source.md translated.txt --json

# 4. Run Phase C self-check (requires --source for term authority)
python scripts/phase_c_check.py translated.txt --source source.md --json

# 5. Final check (requires --source for term authority)
python scripts/completeness_guard.py translated.txt --source source.md --json
```

## Installation

No installation step is required beyond cloning the repository. All scripts
live in `scripts/` and read reference data from `references/`. Run them from
the project root.

Requirements:
- Python 3.10 or later
- No third-party dependencies (stdlib only)

## Translation Workflow

A complete translation consists of five phases. Agents should execute the
automated phases and use the returned data to guide any manual work.

| Phase | Command | Who runs it |
|-------|---------|-------------|
| A. Pre-translation | `auto_pipeline.py pre` | Agent |
| B. Translation | Agent's own translation step | Agent |
| C. Self-check | `phase_c_check.py --source source.md` | Agent |
| D. Term authority | `term_enforcer.py --source source.md` | Agent (also run by guard) |
| E. Post-translation | `auto_pipeline.py post` | Agent |
| F. Completeness guard | `completeness_guard.py --source source.md` | Agent |

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

- **Translation direction**: `post`, `scan`, `phase_c_check`, `check_translation`,
  and `completeness_guard` all accept `--direction {encn,cnen}`. Direction is
  auto-detected from the translated text when omitted, but the detection is a
  character-ratio heuristic that fails on poorly-translated or mixed text (e.g.
  a barely-started CN->EN translation reads as Chinese and is misclassified).
  Since the translation workflow always knows the real direction, pass
  `--direction` explicitly in automated pipelines rather than relying on the
  fallback. The detected/used direction is reported in each command's JSON
  output.

## Script Reference

### `auto_pipeline.py`

Orchestrates pre-processing, post-processing, and residue scanning.

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
  "term_authority": {
    "locked_count": 45,
    "ambiguous_count": 3,
    "pending_count": 2,
    "locked_terms": [
      {
        "extracted": "OTB",
        "canonical_en": "Off the Books",
        "chinese": "黑市买卖",
        "type": "abbreviation",
        "source_ref": "competitive_terms.md",
        "aliases": [],
        "abbrevs": ["OTB"]
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

#### `post`

Runs terminology check, learns new terms, and a skill health check on the
translated file. Direction-aware: direction is auto-detected from the
translated file or set with `--direction`, and forwarded to the terminology
checker.

```bash
python scripts/auto_pipeline.py post source.md translated.txt --json
python scripts/auto_pipeline.py post source.md translated.txt --direction cnen --json
```

JSON data:

```json
{
  "command": "post",
  "source": "source.md",
  "translated": "translated.txt",
  "direction": "encn",
  "terminology_issue_count": 3,
  "new_terms_learned": 2,
  "health_check_passed": true
}
```

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
  "issue_count": 5,
  "auto_fixable_count": 2,
  "auto_fixed_count": 0,
  "issues": [
    {
      "category": "provision_mix",
      "severity": "error",
      "message": "provision mix: 「12费换8战力」→ should be 「12人口换8战力」"
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
enforcement applies to EN→CN only and is skipped for CN→EN.

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
  "all_passed": false,
  "blocked": true,
  "checks": [
    {"name": "file_exists", "passed": true, "issue_count": 0, "message": "..."},
    {"name": "terminology", "passed": false, "issue_count": 3, "message": "..."},
    {"name": "residue_scan", "passed": true, "issue_count": 0, "message": "..."},
    {"name": "phase_c", "passed": false, "issue_count": 1, "message": "..."},
    {"name": "term_authority", "passed": false, "issue_count": 2, "message": "..."}
  ]
}
```

### `term_enforcer.py`

Term authority enforcement. Validates that locked terms from the pre-translation
phase are correctly used in the translation.

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
  "locked_terms_checked": 45
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
- `scripts/learn.py` — Discover new terms from source+translation pairs.
- `scripts/backtranslate.py` — Heuristic back-translation validation.

## Reference Files

All translation rules and data live in `references/`:

- `phase_c_checklist.md` — Machine-checkable Phase C rules.
- `card_names.md` — Verified English↔Chinese card name mappings.
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
- `auto_pipeline.py post` may add new terms to `references/pending_terms.md`.
  These are intended for verification and should not be silently committed.
- The default (non-JSON) output is formatted for readability in terminals and
  logs; use `--json` when building deterministic tool pipelines.
