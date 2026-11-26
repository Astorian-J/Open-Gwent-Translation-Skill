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
2. **判断方向** — 英文→中文 (`encn`) 还是 中文→英文 (`cnen`)，并作为 `--direction` 传给 `prepare` 和 `finish`
3. **走流程** — `translate.py prepare` → 翻译 → `translate.py finish`（见下方 Quick Start）

> 只要用户贴了昆特牌相关的中文或英文，哪怕没明说「翻译」，默认就是要翻译，直接开干。
> If the user posts Gwent text in either language without explicit instruction, default to translating it.
>
> The agent decides the direction and states it with `--direction`; the scripts never
> infer it (see Global Conventions). The user's stated target language wins; otherwise
> translate into the other language.

## Quick Start

```bash
# 1. Prepare — build the translation pack (locked terms, official effects, style rules)
python scripts/translate.py prepare source.md --date 2026-05 --type general --direction encn

# 2. Translate using the generated source.pack.md (the only LLM step, performed by the agent)

# 3. Finish — hard gate; the translation is NOT final until this PASSes
python scripts/translate.py finish translated.txt --source source.md --direction encn

# One-shot wrappers:
#   run = prepare + prints the exact finish command (paths pre-resolved);
#   with --translated it gates the file right after prepare
python scripts/translate.py run source.md --direction encn
#   finish --lite = chat-length content gate (skips Phase C style check,
#   learn, effect audit; terminology/residue/term-authority still gate)
python scripts/translate.py finish translated.txt --source source.md --direction encn --lite
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
| 3. Finish | `translate.py finish translated.txt --source source.md --direction encn` | `translate.py` (deterministic gate; internally runs `completeness_guard` + `learn`; add `--lite` for chat-length content) |
| 0. (optional) Run | `translate.py run source.md --direction encn [--translated out.txt]` | `translate.py` (prepare + exact finish command; with `--translated`, prepare + finish in one shot) |

### Finish extras (repair-loop tracking)

Each BLOCKED round is fingerprinted to `<source>.gate.json`; the next BLOCKED
round against the same source reports `repair_tracking` (`fixed_count` /
`regressed_count` + the regressed entries). A `[REGRESS]` section means the edit
introduced violations absent last round — fix or revert those first. `--fresh`
starts a new baseline (use after a full rewrite). PASS clears the baseline.
Baseline tracking keys on the source and the gate mode (`full` vs `lite`), so
renamed outputs and mixed modes never compare against the wrong round.

`prepare` snapshots its term lock as `<source>.lock.json` next to the pack;
`finish` reuses that snapshot (`lock_reused` in the JSON) and BLOCKS if the
source changed since `prepare` (`--allow-source-changed` rebuilds instead) or if
the snapshot was not prepared for this direction — another direction, or no
direction recorded (it predates explicit directions, or was built by hand).
Neither case can be bypassed: re-run `prepare` with the same `--direction`.
The finish JSON also carries `effect_check` — an INFORMATIONAL count of
source-mentioned cards whose official ability text was not copied verbatim
(never affects the exit code).

`finish` also blocks an output that is not a translation (`untranslated`
violations, in both `--lite` and full mode). Preserved spans — fenced and inline
code, links, e-mail addresses, hashtags and mentions, Markdown link targets —
are excluded, and with the source at hand only when they occur in it verbatim:
the format rules keep them as the source has them, so a span the translator
wrapped around leftover text is judged like any other text.

- CN→EN: every run of Chinese left in the output is one violation, however
  many English card names surround it — so Chinese player IDs are romanized
  (pinyin or their usual Latin form), not kept. One violation per run keeps the
  messages stable while the others are fixed, so the repair loop shows progress
  instead of regressions. Beyond 30 runs only the first 30 are listed and the
  rest are summed up in one count-free entry, so a whole untranslated article
  does not flood the context.
- EN→CN: no Chinese at all plus English prose — a lowercase word of 4+
  letters, or in a sentence a common reply opener (`Thanks.` / `Cheers.`) or a
  short function word (`My bad.` / `How are you.`); abbreviations, bare names
  and short slang like `gg wp` may stay — or English dominating a long output.
  A name, event, version or score followed by a full stop (`Krentabol.` /
  `Gwent Masters.` / `Season 12.` / `Lerio2 vs Krentabol.`) is not prose and
  passes.
- Either direction: a verbatim copy of the source, unless the source is nothing
  but IDs, numbers or kept slang.

Known gaps of this rule on EN→CN. Not caught: a reply made only of capitalized
or very short words that neither starts with a common reply opener nor holds a
short function word — with or without a full stop (`Nice try`, `BRACE YOURSELVES`,
`Disconnected.`, `Crashed.`) — and an output with a little Chinese around
untranslated English. Falsely caught in an output without any Chinese: bare
lowercase names (`kappa pride`), bare domains with neither a scheme nor `www.`
(`playgwent.com/decks`), names built from common reply words (`Nice Guy.`), and
a name, expansion or date that holds a short function word once a full stop
follows (`Way of the Witcher.` / `Price of Power.` / `May 5.` / `Best of 3.`).

`finish` returns `PASS` (finalize) or `BLOCKED` (fix and re-run, up to 3 rounds,
never finalize while BLOCKED). See `SKILL.md` Step 3 for the agent-driven
re-translate loop on BLOCKED.

## Global Conventions

- All scripts accept an optional `--json` flag.
- Without `--json`, output is human-readable text for terminals and logs.
- With `--json`, output is a single JSON object to stdout.
- Exit codes: `0` = success, `1` = failure or blocked — both emit the JSON
  envelope with `--json`; `2` = invalid arguments (argparse, e.g. a missing
  `--direction`) — reported on stderr, with no JSON envelope.
- For exit codes 0 and 1, the envelope emitted with `--json` is always:

```json
{
  "success": true,
  "exit_code": 0,
  "data": { ... },
  "errors": []
}
```

- **Translation direction**: `--direction {encn,cnen}` is a REQUIRED argument on
  every command that extracts, checks or reviews terms — `translate.py prepare /
  finish / run`, `auto_pipeline pre / scan`, `context_lock build / check`,
  `term_enforcer`, `check_translation`, `phase_c_check`, `completeness_guard`,
  `diff_review`. `encn` = EN→CN, `cnen` = CN→EN. It is the task's own direction,
  decided by the agent from the request, and is never inferred from the text:
  mixed Chinese/English Gwent text defeats any heuristic, and a wrong direction
  makes the pack, the lock and the gate all push the translation toward the wrong
  language. Omitting it is an argument error (exit code 2). Pass the same value
  to `prepare` and `finish`; `finish` refuses a snapshot prepared for another
  direction, and one that records no direction (made before directions were
  recorded, or built by hand) — re-run `prepare`. The direction used is reported
  in each command's JSON output (`direction`).

## Script Reference

### `auto_pipeline.py`

Orchestrates pre-processing and residue scanning.

#### `pre`

```bash
python scripts/auto_pipeline.py pre source.md --date YYYY-MM --type general --direction encn --json
```

- `--direction`: REQUIRED. Translation direction, `encn` (EN→CN) or `cnen`
  (CN→EN). Selects how the source is extracted for the lock: English card
  names/terms for `encn`, Chinese ones for `cnen`. Never inferred from the text.
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
  "direction": "encn",
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
translation, or Chinese card names left in a CN->EN translation, and surfaces
the checker's `untranslated` findings (output still in the source language). The
direction is the task's own, passed with the required `--direction`. `scan` has
no source, so a verbatim copy is caught only by the language rules above.

```bash
python scripts/auto_pipeline.py scan translated.txt --direction encn --json
python scripts/auto_pipeline.py scan translated.txt --direction cnen --json
```

JSON data:

```json
{
  "command": "scan",
  "translated": "translated.txt",
  "direction": "encn",
  "residue_count": 0,
  "residues": [],
  "untranslated_count": 0,
  "untranslated": []
}
```

### `check_translation.py`

Detailed terminology checker. Direction-aware: for EN->CN output it runs the
full terminology check set and reports English residue; for CN->EN output it
reports Chinese residue instead. The direction is the task's own, passed with
the required `--direction`. Optionally accepts a source file (or pre-built
lock) to run term authority enforcement — the inline pass here is EN→CN only;
the guard-level `term_authority` check enforces BOTH directions.

```bash
python scripts/check_translation.py translated.txt --direction encn --json
python scripts/check_translation.py translated.txt --source source.md --direction encn --json
python scripts/check_translation.py translated.txt --direction cnen --json
```

JSON data:

```json
{
  "direction": "encn",
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
`chinese_residue`, `term_authority_violation`, `untranslated`.

`untranslated` fires in both directions (and under `finish --lite`) when the
output is not a translation — the reverse check of `--direction`: given the
direction, does the output actually read as the target language? The exact
rules are listed under "Finish extras" above.

### `phase_c_check.py`

Runs the structured Phase C self-check rules from
`references/phase_c_checklist.md`.

```bash
python scripts/phase_c_check.py translated.txt --direction encn --json
python scripts/phase_c_check.py translated.txt --source source.md --direction encn --json
```

`--direction` is required. Choices: `encn` (EN→CN), `cnen` (CN→EN).
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
Direction-aware: the required `--direction` is the task's own and is passed
unchanged to every downstream check, so the gate can never verify one language
here and another elsewhere. The residue check looks for English residue (EN→CN)
or Chinese residue (CN→EN); term authority enforcement runs in BOTH directions
(EN→CN asserts the official Chinese appears in the Chinese translation, CN→EN
asserts the official English appears in the English translation). The
`term_authority` check carries a `status` field: `ran` (executed), `skipped`
(no `--source`/lock provided; not run), or `error` (the check itself raised).

```bash
python scripts/completeness_guard.py translated.txt --direction encn --json
python scripts/completeness_guard.py translated.txt --source source.md --direction encn --json
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
    {"name": "term_authority", "passed": false, "issue_count": 2, "status": "ran", "message": "..."}
  ]
}
```

### `term_enforcer.py`

Term authority enforcement. Validates that locked terms from the pre-translation
phase are correctly used in the translation. The required `--direction` selects
which side is enforced — the official Chinese for `encn`, the official English
for `cnen` — and is the same value the rest of the run received. With `--source`
it also selects how the lock is built.

```bash
python scripts/term_enforcer.py translated.txt --lock lock.json --direction encn --json
python scripts/term_enforcer.py translated.txt --source source.md --direction cnen --json
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
  "direction": "encn"
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
- `scripts/format_skeleton.py` — Standalone Markdown structure extract/restore
  tool (not part of the prepare/finish pipeline).
- `scripts/diff_review.py` — Compare source and translation (review mode).
  Requires `--direction`, forwarded to the terminology checker; its own
  built-in checks and closing checklist are written for EN→CN.
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
- Decide the direction from the request and pass the same
  `--direction {encn,cnen}` to every command. It is required and never
  inferred: a missing direction is an argument error, not a guess.
- Using the scripts as a library: the direction is a required argument there
  too — `check_translation(text, *, direction, ...)` takes it keyword-only, and
  `term_enforcer.enforce_terms(translated_path, lock, direction)`,
  `context_lock.build_lock(source_file, lock_file, direction)` and
  `_shared.build_lock_from_source(source, direction)` require it positionally.
  A value other than `encn` / `cnen` raises `ValueError`.
- Always pass `--source source.md` to `completeness_guard.py` and
  `phase_c_check.py` so that term authority enforcement runs automatically.
- Use the `term_authority.locked_terms` block from `auto_pipeline.py pre` as the
  mandatory translation reference; never translate those terms literally.
- `phase_c_check.py` returns `ready: true` when automated checks pass, but
  manual warnings may still require review.
- After a PASS, `translate.py finish` runs `learn.py --auto` (with
  `--from-lock <lock>` when the prepare snapshot was reused), which appends
  new terms — source-scan discoveries plus the lock's status=pending machine
  candidates (`from_lock_candidates`) — to the gitignored auto buffer
  `references/pending_terms.auto.md`.
  `learn.py --commit` merges the buffer into the local
  `references/pending_terms.md` review inbox (gitignored runtime data);
  committed entries are intended
  for verification and should not be silently promoted to reference files.
- The default (non-JSON) output is formatted for readability in terminals and
  logs; use `--json` when building deterministic tool pipelines.
