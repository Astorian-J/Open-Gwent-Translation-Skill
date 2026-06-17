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

# 4. Run Phase C self-check
python scripts/phase_c_check.py translated.txt --json

# 5. Final check
python scripts/completeness_guard.py translated.txt --json
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
| C. Self-check | `phase_c_check.py` | Agent |
| D. Post-translation | `auto_pipeline.py post` | Agent |
| E. Completeness guard | `completeness_guard.py` | Agent |

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
  ]
}
```

#### `post`

```bash
python scripts/auto_pipeline.py post source.md translated.txt --json
```

JSON data:

```json
{
  "command": "post",
  "source": "source.md",
  "translated": "translated.txt",
  "terminology_issue_count": 3,
  "new_terms_learned": 2,
  "health_check_passed": true
}
```

#### `scan`

```bash
python scripts/auto_pipeline.py scan translated.txt --json
```

JSON data:

```json
{
  "command": "scan",
  "translated": "translated.txt",
  "english_residue_count": 0,
  "residues": []
}
```

### `check_translation.py`

Detailed terminology checker.

```bash
python scripts/check_translation.py translated.txt --json
```

JSON data:

```json
{
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
`abbreviation`, `typo`, `homophone`, `deck_abbreviation`, `english_residue`.

### `phase_c_check.py`

Runs the structured Phase C self-check rules from
`references/phase_c_checklist.md`.

```bash
python scripts/phase_c_check.py translated.txt --direction encn --json
```

Direction is auto-detected if omitted. Choices: `encn` (EN→CN), `cnen` (CN→EN).

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

Final check. Combines terminology, residue, and Phase C checks.

```bash
python scripts/completeness_guard.py translated.txt --json
```

JSON data:

```json
{
  "all_passed": false,
  "blocked": true,
  "checks": [
    {"name": "file_exists", "passed": true, "issue_count": 0, "message": "..."},
    {"name": "terminology", "passed": false, "issue_count": 3, "message": "..."},
    {"name": "residue_scan", "passed": true, "issue_count": 0, "message": "..."},
    {"name": "phase_c", "passed": false, "issue_count": 1, "message": "..."}
  ]
}
```

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
- `phase_c_check.py` returns `ready: true` when automated checks pass, but
  manual warnings may still require review.
- `auto_pipeline.py post` may add new terms to `references/pending_terms.md`.
  These are intended for verification and should not be silently committed.
- The default (non-JSON) output is formatted for readability in terminals and
  logs; use `--json` when building deterministic tool pipelines.
