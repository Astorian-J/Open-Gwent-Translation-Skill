# Gwent Translation Skill

**[English](README.md)** | [中文](README.zh-CN.md) | [Polski](README.pl.md) | [Русский](README.ru.md)

> Accurate bidirectional translation between English and Chinese for *Gwent: The Witcher Card Game* content — official card terminology, community deck names, slang, and a natural Bilibili-player tone. Works with any AI agent or human translator.
>
> **Unofficial fan work — not affiliated with or endorsed by CD PROJEKT RED.** Card ability text is fetched at build time from the public api.gwent.one and is NOT committed to this repo; see [NOTICE](NOTICE) for the full copyright / license boundary.

Machine translation of Gwent content breaks in predictable ways: official card names get translated literally, community deck nicknames become nonsense, English slang like "on steroids" or "sweet spot" turns into gibberish, and everything reads stiff. This toolkit fixes that with a three-layer pipeline that locks card data, guides rhetoric, and catches residue.

## Features

- **Bidirectional & direction-aware** — EN→CN with a Bilibili-player community tone (short punchy sentences, active voice); CN→EN into natural English that keeps community terms. Each direction has its own pipeline, so CN→EN won't false-flag English card names as untranslated residue.
- **1366 cards, locked verbatim** — Every card's official EN/CN name, category, attributes (rarity / faction), and ability text is loaded from CDPR's official data and enforced verbatim. Card info is never re-translated freely. Card data is fetched at install time (run `install.sh` or `scripts/build_effect_reference.py --fetch`); it is not committed to the repo — see NOTICE.
- **200+ community deck names** — The nicknames Chinese players actually use (大金北, 孽鬼跳松, 赤诚骑士北, 状态帝国...), not literal translations.
- **Slang & jargon injection** — English slang (op, brick, tutor, mulligan, on steroids, sweet spot...) is detected in the source and pre-injected with the intended translation, so it stops coming out as gibberish.
- **Rhetoric & tone preservation** — Metaphor, hyperbole, and sarcasm are translated by *intent*, not word-by-word. "Loud design" won't become "too loud".
- **Three-layer defense** — Hard layer enforces card data verbatim; soft layer guides rhetoric and style; detection layer catches residue and missed terms at the end.
- **Agent-agnostic** — Every script has a `--json` flag with a unified envelope `{success, exit_code, data, errors}`. Works with Claude Code, OpenClaw, Hermes, or any agent. Python 3.10+ stdlib only, zero dependencies.

## Before / After

| Source text | Plain machine translation | This skill |
|---|---|---|
| This build's sweet spot is at 8 provisions — loud design, on steroids. | 这个构建在8人口有甜点位置——大声的设计，在类固醇上。 | 这套的**甜点位**就在 8 人口——**存在感太强**，简直**打了鸡血**。 |
| Devotion Knights is the meta pick, but it bricks without a tutor. | 奉献骑士是元选择，但没有家庭教师它会变砖。 | **赤诚骑士北**是版本答案，没**检索**就会**卡手**。 |

## How it works

A two-command deterministic pipeline — `translate.py` — wraps every automated step around the single LLM translation step, so preprocessing and the final gate cannot be skipped:

| Step | What happens | Who runs it |
|---|---|---|
| 1. Prepare | Loads references, locks card terms, injects official effects + slang hints → writes a translation pack | `translate.py prepare` (deterministic) |
| 2. Translate | You or your agent translate, guided by the pack's locked term table | The only LLM step |
| 3. Finish | Hard gate: residue / term-authority / Phase C / completeness all re-verified; BLOCKED = do not finalize | `translate.py finish` (deterministic) |

`auto_pipeline.py`, `phase_c_check.py`, `term_enforcer.py`, and `completeness_guard.py` are now **internal steps** of `translate.py` — do not run them manually.

Card data is **locked, not suggested**: if a card name or official effect appears in the source, the translation must use the official Chinese form. New community terms go through a review buffer (`pending_terms.md`) before permanent adoption. The buffer is local user data: installing or updating the skill never resets it.

## Lite Version (Chat Translation)

For **short chat content** — group messages, Discord / QQ / Kook comments, single sentences — the full pipeline is overkill. The **lite** skill (`gwent-translation-lite`) runs the same pipeline in a chat-length form: **two commands around one translation pass**.

1. **`prepare --lite`** — save the source and build the chat-length pack (term locks plus ambiguity and slang guidance; article-grade sections dropped). The lock table prints straight to the command output.
2. **Translate** — same Bilibili-player / native-player tone, official card and term renderings.
3. **`finish --lite`** — save the translation and gate it: terminology / residue / term-authority checks only, and every violation carries the official rendering to apply.

A source with no suspected proper nouns ("gg wp") can skip prepare and go straight to `finish --lite`. Lite reuses the main skill's `scripts/` and `references/` (zero data duplication), so it works across Claude Code, opencode, and other agents.

| Content | Skill |
|---------|-------|
| Long articles (meta reports, BC proposals, card analysis) | `gwent-translation-style` (full pipeline) |
| Chat messages, comments, single sentences | `gwent-translation-lite` (chat-length gate) |
| Live chat at full speed — no result verification | `gwent-translation-flash` (table first; full-corpus lookup only for unknown names) |

All three tiers install together via `install.sh`. Lite agent interface: [`lite/AGENTS.md`](lite/AGENTS.md).

## A note on token usage

This skill injects a locked term table, official card effects, and slang hints to enforce accuracy. A typical full run (prepare → translate → finish) processes roughly **30–60K tokens** depending on article length — about **3× a bare translation** (measured ~31K on a medium BC article; the term table is ~6K, the bulk is the article + reference docs). Since most of the pipeline is mechanical (term locking, residue detection, format checks), it runs well on **cheaper or free-tier models** (Claude Haiku/Sonnet, GPT-4o-mini, DeepSeek, etc.) or any agent with a free quota — you don't need the most expensive model.

*Token figure based on measuring pre-phase injection on a real BC article; actual usage varies with article length.*

## Quick Install

```bash
curl -fsSL https://raw.githubusercontent.com/Astorian-J/Open-Gwent-Translation-Skill/main/install.sh | bash
```

Or clone manually — you MUST run `install.sh` afterwards. The card database (`card_names_4lang.json`, `effect_text.json`) is CDPR-copyright data and is **not in the repo**; `install.sh` builds it locally. Without it the skill cannot lock card names:

```bash
git clone --depth 1 https://github.com/Astorian-J/Open-Gwent-Translation-Skill.git
cd Open-Gwent-Translation-Skill
bash install.sh
```

Requires Python 3.10+. No third-party dependencies.

## Usage

```bash
# 1. Prepare — build the translation pack (locked terms, official effects, style rules)
python scripts/translate.py prepare source.md --date 2026-07 --type general --direction encn

# 2. Translate using the generated source.pack.md (the only LLM step), save to translated.txt

# 3. Finish — hard gate; the translation is NOT final until this PASSes
python scripts/translate.py finish translated.txt --source source.md --direction encn
```

Add `--json` to any command for machine-readable output. Full agent interface: [AGENTS.md](AGENTS.md).

## File Structure

```
gwent-translation-style/
├── SKILL.md                 # Claude Code workflow + constraints
├── AGENTS.md                # Agent-agnostic interface (commands / JSON / exit codes)
├── agent.json               # Machine-readable command manifest
├── install.sh               # One-line installer
├── references/              # 20 reference files
│   ├── card_overrides.md       # Hand-maintained card aliases / renamed (committed)
│   ├── card_names_4lang.json   # Card names EN<->CN (build-time, gitignored)
│   ├── terminology_map.md       # EN->CN terminology
│   ├── reverse_terminology_map.md  # CN->EN terminology
│   ├── keywords_map.md          # Keyword translations
│   ├── category_map.md          # Card categories (relict, construct...)
│   ├── card_attributes_map.md   # Rarity + faction names / aliases
│   ├── competitive_terms.md     # 200+ deck names + community slang
│   ├── slang_map.md             # Slang / jargon hints (op, brick, tutor...)
│   ├── effect_text.json         # official ability text (build-time, fetched by build_effect_reference.py; see NOTICE)
│   ├── cn_fuzzy_fixes.md        # Chinese typo / abbreviation fixes
│   ├── correction_guide.md      # Translation rules
│   ├── common_pitfalls.md       # Common mistakes
│   ├── style_reference.md       # Style + rhetoric guidelines
│   ├── style_fingerprint.md     # Author style markers
│   ├── ambiguous_names.md       # Disambiguation
│   ├── version_map.md           # Version-specific terms
│   ├── phase_c_checklist.md     # Self-check rules
│   ├── translation_workflow.md  # Workflow reference
│   ├── pending_terms.md         # Terms awaiting review (runtime data, gitignored)
│   ├── pending_terms.template.md # Tracked template; installs seed the buffer from it
│   └── changelog.md             # Update history
├── scripts/                 # 15 Python scripts
│   ├── translate.py             # Main entry: prepare→translate→finish pipeline
│   ├── auto_pipeline.py         # Pre-processing + residue scan (internal to translate.py)
│   ├── check_translation.py     # Residue + slang detection
│   ├── completeness_guard.py    # Final gate
│   ├── phase_c_check.py         # Self-check
│   ├── term_enforcer.py         # Card data verification
│   ├── context_lock.py          # Context / abbreviation lock
│   ├── effect_verifier.py       # Official effect text check
│   ├── build_effect_reference.py  # Build effect_text.json (fetch-at-build: online/offline)
│   ├── format_skeleton.py       # Format preservation
│   ├── diff_review.py           # Diff review
│   ├── backtranslate.py         # Back-translation check
│   ├── lookup.py                # Term lookup
│   ├── learn.py                 # Learn new terms
│   ├── health_check.py          # Integrity check (63 PASS)
│   └── _shared.py               # Shared logic (TermAuthority)
└── lite/                    # Lite skill — chat translation (3-step)
    ├── SKILL.md                  # Lite skill workflow
    └── AGENTS.md                 # Agent-agnostic interface (chat / short content)
```

## Terminology Highlights

A small sample — the full set lives in `references/`.

**Deck names** (community-recognized):

| English | Chinese |
|---|---|
| Devotion Knights | 赤诚骑士北 |
| GN Movement | 孽鬼跳松 |
| Aristocrats | 状态帝国 |
| Lined Pockets Crimes | 宝箱罪行迪迦 |
| Blaze of Glory Eist Warriors | 荣耀圣焰征战 |

**Faction aliases**: Northern Realms → 北, Skellige → 岛, Monsters → 怪, Nilfgaard → 帝, Scoia'tael → 松, Syndicate → 迪迦.

## Claude Code Users

Install to `~/.claude/skills/gwent-translation-style/` and restart Claude Code. The `install.sh` script installs **both** the main skill (`gwent-translation-style`) and the lite skill (`gwent-translation-lite`) together. Triggers: `/gwent-translation-style`, "translate Gwent article", "Gwent translation"; for the lite skill — "翻一下这句" / chat translation triggers.

## Contributing

1. Fork the repository
2. Add or update terms in `references/`
3. New community terms must pass through `pending_terms.md`
4. Run `python scripts/health_check.py` before submitting
5. Open a pull request

## License

See [LICENSE](LICENSE).
