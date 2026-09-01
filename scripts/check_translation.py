#!/usr/bin/env python3
"""
Gwent translation terminology checker.
Detects common errors: provision mixing, number reversal, forbidden terms,
abbreviations, passive voice, Chinese numerals, English parentheses.

Usage:
    python check_translation.py <file> [--fix]

Rules are loaded from references/ directory to stay in sync.
"""

import argparse
import functools
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (
    SKIP_WORDS_MINIMAL,
    detect_direction,
    extract_card_names,
    extract_card_names_no_colon,
    extract_cn_variants,
    get_card_name_corrections,
    get_card_names_cn_index,
    get_card_names_index,
    get_term_authority,
    json_output,
    load_lock_file,
    parse_ta_envelope,
    run_utf8,
)

# --- Load rules from references ---


def _get_ref_path(filename: str) -> Path:
    return Path(__file__).parent.parent / "references" / filename


@functools.lru_cache(maxsize=1)
def load_forbidden_terms():
    """Load forbidden terms from correction_guide.md Section 1"""
    terms = {}
    guide = _get_ref_path("correction_guide.md")
    if not guide.exists():
        raise FileNotFoundError(
            f"Correction guide not found: {guide}. "
            "Run from the project root or verify the references directory."
        )

    text = guide.read_text(encoding="utf-8")
    in_section = False
    in_table = False
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("## 1.") and "Terminology" in line:
            in_section = True
            continue
        if in_section and line.startswith("## 2."):
            break
        if in_section and line.startswith("|") and "---" in line:
            in_table = True
            continue
        if in_table and line.startswith("|") and "---" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4 and parts[1] and parts[2]:
                wrong, right = parts[1], parts[2]
                if wrong and right and wrong != "Wrong":
                    for w in wrong.split("/"):
                        w = w.strip()
                        if w:
                            terms[w] = right
        if in_table and not line.startswith("|"):
            in_table = False

    return terms


@functools.lru_cache(maxsize=1)
def load_card_corrections():
    """Load outdated Chinese card names (wrong -> correct) from card_overrides.md."""
    return dict(get_card_name_corrections())


def load_locked_phrases_from_source(source_path: Path) -> set[str]:
    """Build a context lock from the source and return locked Chinese phrases.

    These phrases represent the official/community translations that the agent
    is required to use. An ambiguous base name counts as disambiguated only
    when one of these phrases is actually present in the translation (see the
    ambiguous-name guard in check_translation).
    """
    script = Path(__file__).parent / "context_lock.py"
    if not script.exists():
        return set()

    # Reserve a path only; context_lock.py writes the lock itself via --output.
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".json")
    tmp_path = Path(tmp_name)
    os.close(tmp_fd)

    try:
        result = run_utf8(
            [sys.executable, str(script), "build", str(source_path), "--output", str(tmp_path)],
            timeout=60,
        )
        if result.returncode != 0:
            return set()
        lock = json.loads(tmp_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError, subprocess.SubprocessError):
        return set()
    finally:
        tmp_path.unlink(missing_ok=True)

    return extract_cn_variants(lock)


def load_locked_phrases_from_lock(lock_path: Path) -> set[str]:
    """Read locked Chinese phrases directly from a pre-built lock file.

    Unlike load_locked_phrases_from_source this does not shell out to
    context_lock.py — the lock must already exist (built once by the caller,
    e.g. completeness_guard). Used by the --lock path to avoid rebuilding.
    """
    try:
        lock = load_lock_file(lock_path)
    except (json.JSONDecodeError, ValueError, OSError):
        return set()
    return extract_cn_variants(lock)


@functools.lru_cache(maxsize=1)
def load_abbreviations():
    """Load abbreviations that should be expanded on first use.
    Returns dict: abbreviation -> (full_form, english)
    """
    abbrevs = {}
    terms_file = _get_ref_path("competitive_terms.md")
    if not terms_file.exists():
        return abbrevs

    text = terms_file.read_text(encoding="utf-8")
    in_table = False
    headers = []
    for line in text.split("\n"):
        line = line.strip()
        # Detect table header row with English/Chinese/Abbreviations
        if line.startswith("|") and "English" in line and "Abbreviations" in line:
            headers = [p.strip() for p in line.split("|")]
            in_table = False  # Wait for separator
            continue
        if line.startswith("|") and "---" in line and headers:
            in_table = True
            continue
        if in_table and line.startswith("|") and "---" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 5:
                en = parts[1] if len(parts) > 1 else ""
                cn = parts[2] if len(parts) > 2 else ""
                abbr = parts[3] if len(parts) > 3 else ""
                if abbr and abbr not in ("Abbreviations", "—", ""):
                    for a in abbr.split(";"):
                        a = a.strip()
                        if a:
                            abbrevs[a] = (cn, en)
        # Table ended, but keep headers so next separator triggers new table
        if in_table and not line.startswith("|"):
            in_table = False
            # Don't clear headers — next separator starts new table

    return abbrevs


@functools.lru_cache(maxsize=1)
def load_ambiguous_names():
    """Load ambiguous card names (base name -> list of (en, cn) tuples)."""
    ambiguous: dict[str, list[tuple[str, str]]] = {}
    ambig_file = _get_ref_path("ambiguous_names.md")
    if not ambig_file.exists():
        return ambiguous

    text = ambig_file.read_text(encoding="utf-8")
    current_base = None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("## ") and "versions" in line:
            # e.g., "## 杰洛特 (Geralt) — 6 versions"
            match = re.search(r'##\s+(.+?)\s+\(', line)
            if match:
                current_base = match.group(1)
                ambiguous[current_base] = []
        elif current_base and line.startswith("|") and "---" not in line and "Full Name" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4 and parts[1] and parts[1] != "Full Name":
                en = parts[1]
                cn = parts[2] if len(parts) > 2 else ""
                if en:
                    ambiguous[current_base].append((en, cn))

    return ambiguous


@functools.lru_cache(maxsize=1)
def load_fuzzy_fixes():
    """Load Chinese fuzzy fixes: typos and homophones.

    §3 (deck-name abbreviations) is intentionally skipped — SKILL.md encourages
    those community short forms, so they must not be machine-enforced.
    """
    fixes = {
        "typos": {},      # wrong -> correct
        "homophones": {}, # wrong -> correct (with context)
    }

    fuzzy_file = _get_ref_path("cn_fuzzy_fixes.md")
    if not fuzzy_file.exists():
        return fixes

    text = fuzzy_file.read_text(encoding="utf-8")
    current_section = None

    for line in text.split("\n"):
        line = line.strip()

        # Detect section
        if "## 1. Typo" in line:
            current_section = "typos"
            continue
        elif "## 2. Homophone" in line:
            current_section = "homophones"
            continue
        elif "## 3. Deck Name" in line:
            current_section = None  # deck abbreviations not enforced; skip section
            continue
        elif line.startswith("## ") and current_section:
            # New section ends deck abbreviation section
            if "## 4." in line or "## 5." in line:
                current_section = None
            continue

        if not current_section:
            continue

        # Parse table row
        if line.startswith("|") and "---" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                wrong = parts[1]
                correct = parts[2]
                notes = parts[3] if len(parts) > 3 else ""

                # "✓" in the Type column (notes) marks "actually correct" rows
                # (气宗/毒奶/弃牌岛/...) — not corrections. Also skip wrong==correct.
                if (wrong and correct
                        and wrong not in ("Wrong", "Abbreviation")
                        and notes != "✓"
                        and wrong != correct):
                    fixes[current_section][wrong] = {
                        "correct": correct,
                        "notes": notes,
                    }

    return fixes


# --- Tunable thresholds ---

# Provision 顺序检查：人口高出战力超过此容差视为可疑「X for Y」反转
SUSPICIOUS_ORDER_MARGIN = 5
# 中文残留名最短长度，跳过单字避免「的/了」等误匹配
MIN_CN_RESIDUE_LEN = 2

# --- Patterns ---

# "X费换X点战力" / "X费X战力"
PROVISION_FEE_PATTERN = re.compile(r'(\d+)\s*费\s*换\s*(\d+)\s*点?\s*战力')
PROVISION_FEE_PARALLEL = re.compile(r'(\d+)\s*费\s*(\d+)\s*点?\s*战力')

# Identical numbers (likely reversed)
IDENTICAL_NUMBERS = re.compile(r'(\d+)\s*人口\s*\1\s*战力')

# Suspicious order: pop much higher than power
POWER_PROVISION_ORDER = re.compile(r'(\d+)\s*人口\s*(\d+)\s*战力')

# Chinese numerals
CHINESE_NUMERALS = re.compile(r'[一二三四五六七八九十]+点|[一二三四五六七八九十]+人口')

# Passive voice indicators
PASSIVE_INDICATORS = ["未被", "被解", "被削", "被增强", "被削弱", "被打出", "被移除"]

# English parentheses
ENGLISH_PARENS = re.compile(r'\([^）]*\)')

# English colon in card-like contexts
ENGLISH_COLON = re.compile(r'[一-鿿][A-Za-z]+:')

# Abbreviations that should be expanded.
# Uses explicit lookaround because \b (word boundary) doesn't work reliably
# with CJK text — we only want to match these abbreviations when surrounded
# by non-ASCII letters or punctuation.
ABBREV_PATTERN = re.compile(r'(?<![A-Za-z])(BC|OP|UP|OTB|RSS|CA|GG|BM|PTS|R[123])(?![A-Za-z])')

# Gameplay-context words that, within a ±20 char window, indicate a slang term is
# used in its community sense (not literal). Filters literal "broken link" / "loud
# noise" false positives so the reverse-scan warns only on slang usage.
SLANG_CONTEXT_WORDS = {"card", "deck", "meta", "strong", "weak", "play",
                       "nerf", "buff", "build", "run", "tier", "win", "lose"}
# Half-window (chars each side of a slang hit) that must contain a gameplay
# context word to treat the occurrence as slang rather than literal.
SLANG_CONTEXT_WINDOW = 20


def _slang_in_context(source: str, slang: str) -> bool:
    """True if `slang` appears in a gameplay context (not a literal use).

    Slang words (broken / loud / nuts) have common literal meanings. Require a
    gameplay-context word within ±20 chars to treat the occurrence as slang.
    Lowers false positives; false negatives only miss a (non-blocking) warn.
    """
    low = source.lower()
    for m in re.finditer(rf"\b{re.escape(slang.lower())}s?\b", low):
        start = max(0, m.start() - SLANG_CONTEXT_WINDOW)
        end = min(len(low), m.end() + SLANG_CONTEXT_WINDOW)
        if any(w in low[start:end] for w in SLANG_CONTEXT_WORDS):
            return True
    return False


def _slang_warnings(source_text: str | None, translation: str) -> list[str]:
    """Warn (never block) when source slang lacks any intended CN form in translation."""
    if not source_text:
        return []
    authority = get_term_authority()
    warnings: list[str] = []
    for rec in authority.get_slang_for_text(source_text):
        if not _slang_in_context(source_text, rec["english"]):
            continue
        intended = [s.strip() for s in rec["intended_cn"].split("/") if s.strip()]
        if intended and not any(c in translation for c in intended):
            warnings.append(
                f"slang not preserved: source「{rec['english']}」→ "
                f"expected one of {intended} (avoid literal「{rec['literal_forbidden']}」)"
            )
    return warnings


def check_translation(
    text: str,
    locked_phrases: set[str] | None = None,
    direction: str | None = None,
    source_text: str | None = None,
) -> tuple[list[str], list[str]]:
    """Check translation text, return (issues, warnings).

    If `source_text` is given, slang terms in it are reverse-scanned and a
    non-blocking warning is emitted when the translation lacks any intended CN
    form for a slang term used in a gameplay context.

    Direction ("encn" or "cnen") selects which checks apply and is
    auto-detected from the text when omitted. The full terminology check
    set (provision mix, forbidden terms, fuzzy fixes, English residue, ...)
    targets a Chinese *output* and runs only for EN->CN. A CN->EN output is
    scanned for untranslated Chinese card names instead, because running
    the EN->CN checks against English text would flag the target language
    itself as residue.
    """
    direction = direction or detect_direction(text)

    issues = []
    # 空译文: 任何方向都不该出现 (guard 消费为 blocking issue)
    if not text.strip():
        issues.append("empty: 译文为空 — 没有任何可交付内容")

    # 格式门禁: 分割线 --- 数量必须与原文一致 (双向都要; AI 易丢末尾 --- 当元数据扔掉)
    if source_text:
        hr_src = sum(1 for l in source_text.split("\n") if l.strip() == "---")
        hr_txt = sum(1 for l in text.split("\n") if l.strip() == "---")
        if hr_txt < hr_src:
            issues.append(
                f"format: 分割线 --- 数量不一致 (原文 {hr_src} vs 译文 {hr_txt}), "
                f"必须按原文数量原样补回所有 --- 分割线, 不能删"
            )

        # 受保护 token (对照 Weblate/zotero 校验清单): 链接与行内代码是不翻译的
        # 原样保留物, 译文里必须逐字存在。格式规则本就要求代码内容不译。
        # 尾部标点剥离: 正则会把紧随 URL 的逗号/句号吃进 token, 而忠实译文里
        # URL 后接的是全角标点, 不剥会误判「链接丢失」。
        for raw_url in set(re.findall(r"https?://[^\s)\]>\"']+", source_text)):
            url = raw_url.rstrip(".,;:!?'\"，。；：！？、）」』")
            if url and url not in text:
                issues.append(
                    f"protected token: 链接丢失/被改动 — 译文必须原样保留 {url}"
                )
        src_code = re.findall(r"`[^`\n]+`", source_text)
        if src_code and not re.findall(r"`[^`\n]+`", text):
            issues.append(
                f"protected token: 行内代码全部丢失 (原文 {len(src_code)} 处, 译文 0 处) — "
                f"代码内容不译, 原样保留 `...` 标记"
            )

        # 标记全丢: 粗体/代码标记允许随译文重排, 但一处不剩说明格式被剥掉
        if source_text.count("**") >= 2 and text.count("**") == 0:
            issues.append("format: 粗体 ** 标记全部丢失 — 按原文在对应文字上保留 ** 标记")

        # 严重漏译: 非空行数骤减 (原文 >=4 行且译文不足一半)。行级 1:1 是格式
        # 规则的要求, 这里只拦"砍掉近半内容"级别的遗漏, 不做逐行计数误报。
        src_lines = sum(1 for l in source_text.split("\n") if l.strip())
        txt_lines = sum(1 for l in text.split("\n") if l.strip())
        if src_lines >= 4 and txt_lines < src_lines // 2:
            issues.append(
                f"completeness: 非空行数骤减 (原文 {src_lines} 行 vs 译文 {txt_lines} 行) — "
                f"疑似整段/整表漏译, 逐段核对"
            )

    # CN->EN output: the only term-level residue is Chinese card names that
    # were not translated to English. The EN->CN checks below all assume a
    # Chinese output and would false-positive on English text.
    if direction == "cnen":
        return check_chinese_residue(text) + issues, []

    forbidden_terms = load_forbidden_terms()
    card_corrections = load_card_corrections()
    abbreviations = load_abbreviations()
    ambiguous = load_ambiguous_names()
    locked_phrases = locked_phrases or set()

    # 1. Check "X费" patterns
    fee_matches = PROVISION_FEE_PATTERN.findall(text)
    for match in fee_matches:
        x, y = match
        issues.append(
            f"provision mix: 「{x}费换{y}战力」→ should be 「{x}人口换{y}战力」"
        )

    fee_par = PROVISION_FEE_PARALLEL.findall(text)
    for match in fee_par:
        x, y = match
        if f"{x}费换{y}战力" not in text:
            issues.append(
                f"provision mix: 「{x}费{y}战力」→ should be 「{x}人口{y}战力」"
            )

    # 2. Check identical numbers
    identical = IDENTICAL_NUMBERS.findall(text)
    for match in identical:
        issues.append(
            f"identical numbers: 「{match}人口{match}战力」— "
            f"check if 'X for Y' was reversed"
        )

    # 3. Check suspicious population/power order
    order_matches = POWER_PROVISION_ORDER.findall(text)
    for match in order_matches:
        pop, pwr = int(match[0]), int(match[1])
        if pop > pwr + SUSPICIOUS_ORDER_MARGIN:
            issues.append(
                f"suspicious order: 「{pop}人口{pwr}战力」— population much higher than power, "
                f"verify source 'X for Y' format"
            )

    # 4. Check forbidden terms
    for forbid, replace in forbidden_terms.items():
        for match in re.finditer(re.escape(forbid), text):
            idx = match.start()
            start = max(0, idx - 10)
            end = min(len(text), idx + len(forbid) + 10)
            ctx = text[start:end].replace('\n', ' ')
            issues.append(
                f"forbidden term: 「{forbid}」→ 「{replace}」 (context: ...{ctx}...)"
            )

    # 5. Check outdated card names
    for old_name, new_name in card_corrections.items():
        if old_name in text:
            issues.append(
                f"outdated card name: 「{old_name}」→ 「{new_name}」"
            )

    # 6. Check ambiguous card names (base name without subtitle)
    for base_name, versions in ambiguous.items():
        if base_name not in text:
            continue
        # Exempt only when a disambiguating locked phrase is actually present
        # in the text. Requiring `phrase in text` keeps the exemption local to
        # the disambiguating context (e.g. the locked deck name "蟹蜘蛛领袖破烂怪"
        # appears, so the bare base "蟹蜘蛛" inside it is treated as resolved)
        # instead of excusing every bare occurrence anywhere in the text.
        if any(phrase in text and base_name in phrase for phrase in locked_phrases):
            continue
        # Check if any full version (EN or CN) is present in the text
        has_full = any(en in text or (cn and cn in text) for en, cn in versions)
        if not has_full:
            cn_candidates = " / ".join(cn for _, cn in versions if cn)
            issues.append(
                f"ambiguous name: 「{base_name}」has multiple versions ({len(versions)}). "
                f"Pick ONE by source context and use its full name: {cn_candidates}. "
                f"See ambiguous_names.md"
            )

    # 7. Check Chinese numerals
    cn_nums = CHINESE_NUMERALS.findall(text)
    for match in set(cn_nums):
        issues.append(
            f"Chinese numerals: 「{match}」→ use Arabic numerals"
        )

    # 8. Check passive voice
    for indicator in PASSIVE_INDICATORS:
        start_idx = 0
        while True:
            idx = text.find(indicator, start_idx)
            if idx == -1:
                break
            start = max(0, idx - 15)
            end = min(len(text), idx + len(indicator) + 15)
            ctx = text[start:end].replace('\n', ' ')
            issues.append(
                f"passive voice: 「{indicator}」detected (context: ...{ctx}...) → use active voice"
            )
            start_idx = idx + len(indicator)

    # 9. Check English parentheses
    eng_parens = ENGLISH_PARENS.findall(text)
    for match in eng_parens[:3]:
        issues.append(
            f"English parentheses: 「{match}」→ use Chinese brackets 「（）」"
        )

    # 10. Check English colon after Chinese characters
    eng_colons = ENGLISH_COLON.findall(text)
    for match in eng_colons[:3]:
        issues.append(
            f"English colon: 「{match}」→ use Chinese colon "
        )

    # 11. Check abbreviations (warn if used without expansion)
    found_abbrevs = ABBREV_PATTERN.findall(text)
    for abbrev in set(found_abbrevs):
        if abbrev in abbreviations:
            cn, en = abbreviations[abbrev]
            # Full Chinese term already appears anywhere in the text (e.g.
            # 平衡委员会（BC）) — abbreviation is expanded, textbook-correct, do not flag.
            if cn and cn in text:
                continue
            issues.append(
                f"abbreviation: 「{abbrev}」— consider expanding on first use: "
                f"{cn} ({en})"
            )
        elif abbrev in ("R1", "R2", "R3"):
            pass

    # 12. Check Chinese fuzzy fixes (typos, homophones)
    fuzzy_fixes = load_fuzzy_fixes()

    # Collect already-detected terms to avoid duplicates
    already_detected = set()
    for issue in issues:
        # Extract the wrong term from existing issues
        if "outdated card name:" in issue:
            m = re.search(r'「(.+?)」', issue)
            if m:
                already_detected.add(m.group(1))

    # 12a. Typos
    for wrong, info in fuzzy_fixes["typos"].items():
        if wrong in already_detected:
            continue
        if wrong in text:
            idx = text.index(wrong)
            start = max(0, idx - 10)
            end = min(len(text), idx + len(wrong) + 10)
            ctx = text[start:end].replace('\n', ' ')
            issues.append(
                f"typo: 「{wrong}」→ 「{info['correct']}」({info['notes']}) "
                f"(context: ...{ctx}...)"
            )

    # 12b. Homophones
    for wrong, info in fuzzy_fixes["homophones"].items():
        if wrong in text:
            idx = text.index(wrong)
            start = max(0, idx - 15)
            end = min(len(text), idx + len(wrong) + 15)
            ctx = text[start:end].replace('\n', ' ')
            issues.append(
                f"homophone: 「{wrong}」→ 「{info['correct']}」({info['notes']}) "
                f"(context: ...{ctx}...)"
            )

    # 12c. Deck abbreviations — intentionally NOT enforced.
    # SKILL.md's Community Slang table encourages these short forms (骑士北/破烂怪/
    # 位移松/孽鬼店店/互口岛/...). Forcing them to expand to full deck names would
    # contradict the skill's style. The deck_abbr table in cn_fuzzy_fixes.md remains
    # as a human reference and CN->EN reverse lookup, just not a machine gate.

    # 13. Check English residue (untranslated card names)
    residue_issues = check_english_residue(text)
    issues.extend(residue_issues)

    # 14. Slang reverse-scan (WARN only, never blocks): if the source contained a
    # known slang term in a gameplay context, the translation should carry at
    # least one intended CN form. Misses become warnings, not issues.
    warnings = _slang_warnings(source_text, text)

    return issues, warnings


def check_english_residue(text: str) -> list[str]:
    """Scan translated text for untranslated English card names.

    Extracts English capitalized phrases from the Chinese translation,
    looks them up in card_names.md, and reports any matches as
    likely missed translations.
    """
    issues = []

    # Load card database (cards-only, from the 4lang table + card_overrides.md —
    # NOT the mixed TermAuthority entries, which would false-flag common words
    # like 'leader'/'mage' as untranslated card residue).
    card_map = get_card_names_index()
    if not card_map:
        return issues

    # Extract English phrases using shared logic (supports function words).
    # extract_card_names / extract_card_names_no_colon / SKIP_WORDS_MINIMAL are
    # imported from _shared at module level.
    candidates = set()

    # 1. Card names WITH colons (e.g., "Saskia: Commander")
    for name in extract_card_names(text):
        candidates.add(name.strip())

    # 2. Card names WITHOUT colons, multi-word (e.g., "Paulie Dahlberg")
    for name in extract_card_names_no_colon(text, max_words=5, min_length=4):
        candidates.add(name.strip())

    # 3. Simple 2-4 capitalized-word sequences (fallback)
    pattern = re.compile(
        r'\b([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*){1,3})\b'
    )
    for match in pattern.finditer(text):
        candidates.add(match.group(1).strip())

    # 4. Single capitalized words (e.g., "Geralt", "Ciri", "Schirru")
    #    Must be length >= 4 and not a common skip word
    single_word_pattern = re.compile(r'\b([A-Z][a-zA-Z]{3,})\b')
    for match in single_word_pattern.finditer(text):
        word = match.group(1)
        if word not in SKIP_WORDS_MINIMAL:
            candidates.add(word)

    # Non-card-name filters
    skip_patterns = [
        re.compile(r'^\d+$'),                    # Pure numbers
        re.compile(r'[@#]'),                     # Player IDs / tags
        re.compile(r'https?://|www\.|\.com'),   # URLs
        re.compile(r'^v?\d+\.\d+'),             # Version numbers like v12.8
        re.compile(r'^[A-Z]$'),                  # Single letter
        re.compile(r'^(BC|OP|UP|OTB|RSS|CA|GG|BM|PTS|R[123]|MO|NR|NG|SK|ST|SY|NE)$'),
                                                  # Known abbreviations
    ]

    found = set()
    for phrase in candidates:
        # Apply filters
        if any(p.match(phrase) for p in skip_patterns):
            continue

        # Check against card database
        key = phrase.lower()
        if key in card_map:
            en, cn = card_map[key]
            if phrase not in found:
                found.add(phrase)
                issues.append(
                    f"English residue: 「{phrase}」→ 「{cn}」 "
                    f"(found in card database, may be untranslated)"
                )
        else:
            # Try partial match for colon-style card names
            # e.g., "Geralt" might match multiple "Geralt: ..." variants.
            # Collect all matches so the user sees every possible translation.
            partial_hits = [
                (db_en, db_cn)
                for db_key, (db_en, db_cn) in card_map.items()
                if key in db_key or db_key in key
            ]
            if partial_hits:
                # Report once per phrase, listing all matching variants.
                variants = ", ".join(f"{db_en} → {db_cn}" for db_en, db_cn in partial_hits[:5])
                if len(partial_hits) > 5:
                    variants += f", ... ({len(partial_hits) - 5} more)"
                if phrase not in found:
                    found.add(phrase)
                    issues.append(
                        f"English residue: 「{phrase}」may be untranslated. "
                        f"Matches: {variants}"
                    )

    return issues


@functools.lru_cache(maxsize=1)
def load_chinese_card_names() -> dict[str, str]:
    """Build a Chinese card name -> English map (cards-only, from 4lang table).

    The mirror of the English card map used by check_english_residue, keyed
    by the Chinese name so a CN->EN translation can be scanned for Chinese
    card names that were not translated to English.
    """
    return dict(get_card_names_cn_index())


def check_chinese_residue(text: str) -> list[str]:
    """Scan CN->EN output for untranslated Chinese card names.

    The direction-aware counterpart of check_english_residue: where that
    flags English card names left in a Chinese translation, this flags
    Chinese card names left in an English translation. Longer names are
    matched first so a full name is reported before any of its substrings.
    """
    mapping = load_chinese_card_names()
    if not mapping:
        return []

    names = sorted(mapping.keys(), key=len, reverse=True)
    issues: list[str] = []
    reported: set[str] = set()

    for cn in names:
        if len(cn) < MIN_CN_RESIDUE_LEN:
            continue
        if cn in reported:
            continue
        if cn in text:
            issues.append(f"Chinese residue: 「{cn}」→ 「{mapping[cn]}」")
            reported.add(cn)

    return issues


def auto_fix(text: str) -> tuple[str, int]:
    """Auto-fix deterministic provision-terminology errors.

    Currently handles:
      - "X费换Y战力" -> "X人口换Y战力"
      - "X费Y战力"   -> "X人口Y战力"

    Other issues (forbidden terms, outdated names, Chinese numerals, etc.)
    require manual review and are not auto-fixed.
    """
    fixed = text
    count = 0

    fixed, n = PROVISION_FEE_PATTERN.subn(r'\1人口换\2战力', fixed)
    count += n

    fixed, n = PROVISION_FEE_PARALLEL.subn(r'\1人口\2战力', fixed)
    count += n

    return fixed, count


def check_term_authority_violations(
    translated_path: Path,
    source_path: Path | None = None,
    lock_path: Path | None = None,
) -> list[str]:
    """Run term_enforcer.py and return formatted issue strings.

    Pass lock_path to reuse a pre-built lock (--lock); otherwise pass
    source_path and let term_enforcer build it (--source).
    """
    script = Path(__file__).parent / "term_enforcer.py"
    if not script.exists():
        # Fail-closed, same semantics as the crash guard below: a missing
        # sibling checker must NOT read as "no violations".
        return ["[checker error] scripts/term_enforcer.py missing — term authority check cannot run"]

    if lock_path:
        flag, ref = "--lock", str(lock_path)
    else:
        flag, ref = "--source", str(source_path)
    result = run_utf8(
        [sys.executable, str(script), str(translated_path), flag, ref, "--json"],
        timeout=60,
    )
    # No early-return on returncode==0: a rc-0 run can still carry degraded
    # warnings. Single-point envelope interpretation (fail-closed rules live
    # in parse_ta_envelope: value-not-key data check, degraded warnings count
    # as violations).
    try:
        parsed = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        parsed = None
    _ok, _count, violations, err = parse_ta_envelope(parsed)
    if err is not None:
        detail = err
        if not (isinstance(parsed, dict) and parsed.get("errors")):
            detail = (result.stderr or "").strip()[-200:] or err
        return [f"[checker error] term_enforcer crashed (exit {result.returncode}): {detail}"]

    issues: list[str] = []
    for v in violations:
        if v.get("term") == "[checker warning]":
            issues.append(f"[checker warning] term_enforcer degraded: {v.get('offending_quote', '')}")
        else:
            msg = f"term authority: 「{v['term']}」expected 「{v['expected_cn']}」"
            if v.get("found_in_translation"):
                msg += f", found 「{v['found_in_translation']}」"
            issues.append(msg)
    return issues


# Issue prefixes used to derive structured categories for --json output.
# Category taxonomy aligns with MQM (GEMBA-MQM): terminology/accuracy classes
# (provision_mix, forbidden_term, residue, term_authority, ...) map to MQM
# terminology-accuracy; format/protected_token/completeness map to MQM style/
# omission. Severity stays the binary error/warning contract — see AGENTS.md.
ISSUE_CATEGORIES = {
    "provision mix:": "provision_mix",
    "identical numbers:": "identical_numbers",
    "suspicious order:": "suspicious_order",
    "forbidden term:": "forbidden_term",
    "outdated card name:": "outdated_card_name",
    "ambiguous name:": "ambiguous_name",
    "Chinese numerals:": "chinese_numerals",
    "passive voice:": "passive_voice",
    "English parentheses:": "english_parentheses",
    "English colon:": "english_colon",
    "abbreviation:": "abbreviation",
    "typo:": "typo",
    "homophone:": "homophone",
    "English residue:": "english_residue",
    "Chinese residue:": "chinese_residue",
    "term authority:": "term_authority_violation",
    "slang not preserved:": "slang_not_preserved",
    "format:": "format",
    "protected token:": "protected_token",
    "empty:": "empty_translation",
    "completeness:": "completeness",
}


def categorize_issue(issue: str) -> dict[str, str]:
    """Map a human-readable issue string to a structured category."""
    for prefix, category in ISSUE_CATEGORIES.items():
        if issue.startswith(prefix):
            return {"category": category, "severity": "error", "message": issue}
    return {"category": "unknown", "severity": "error", "message": issue}


def main():
    parser = argparse.ArgumentParser(description="Gwent translation terminology checker")
    parser.add_argument("file", help="File to check")
    parser.add_argument("--source", help="Source file for term authority enforcement")
    parser.add_argument("--lock", help="Pre-built context lock JSON (reuse, do not rebuild)")
    parser.add_argument("--fix", action="store_true", help="Auto-fix provision-terminology errors only (费→人口)")
    parser.add_argument("--direction", choices=["encn", "cnen"], help="Translation direction (auto-detected if omitted)")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    parser.add_argument("--quiet", action="store_true", help="Suppress stderr notes (e.g. --fix no-op on CN->EN)")
    parser.add_argument("--skip-ta", action="store_true",
                        help="Skip the inline term-authority pass (for callers that run "
                             "term_enforcer separately, e.g. completeness_guard's single "
                             "check-5 execution)")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        if args.json:
            json_output(None, errors=[f"file not found: {args.file}"], exit_code=1)
        print(f"Error: file not found: {args.file}")
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    direction = args.direction or detect_direction(text)

    locked_phrases: set[str] = set()
    source_text: str | None = None
    if args.lock:
        lock_path = Path(args.lock)
        if lock_path.exists():
            locked_phrases = load_locked_phrases_from_lock(lock_path)
    # Independent of --lock: the guard passes BOTH (lock for the enforced term
    # set, source for the structural checks). Only when no lock exists does the
    # source backfill locked_phrases.
    if args.source:
        source_path = Path(args.source)
        if source_path.exists():
            source_text = source_path.read_text(encoding="utf-8")
            if not locked_phrases:
                locked_phrases = load_locked_phrases_from_source(source_path)

    issues, warnings = check_translation(text, locked_phrases, direction, source_text=source_text)

    # Term authority enforces that locked source terms appear with their
    # official translation. This inline pass covers EN->CN only (English
    # terms -> official Chinese); CN->EN enforcement is NOT lost — the
    # guard's term_enforcer check runs for BOTH directions against the same
    # lock, so running it here too would only duplicate work.
    # Collected separately so a --fix re-check (which reassigns `issues`
    # wholesale) cannot drop TA violations from the report; auto_fix only
    # rewrites provision phrasing (费→人口), so it cannot add/remove TA hits.
    ta_issues: list[str] = []
    if direction == "encn" and not args.skip_ta:
        if args.lock:
            lock_path = Path(args.lock)
            if lock_path.exists():
                ta_issues.extend(check_term_authority_violations(path, lock_path=lock_path))
            else:
                ta_issues.append(f"term authority: lock file not found: {args.lock}")
        elif args.source:
            source_path = Path(args.source)
            if source_path.exists():
                ta_issues.extend(check_term_authority_violations(path, source_path=source_path))
            else:
                ta_issues.append(f"term authority: source file not found: {args.source}")

    # Apply auto-fix before emitting any output so JSON reports accurate counts.
    auto_fixed_count = 0
    if args.fix:
        if direction == "cnen":
            # auto_fix corrects EN->CN provision terms (Chinese 「费→人口」);
            # a CN->EN output is English and would never match — explicit no-op.
            if not args.quiet:
                print("note: --fix applies to EN->CN provision terms only; ignored for CN->EN", file=sys.stderr)
        else:
            fixed_text, fix_count = auto_fix(text)
            auto_fixed_count = fix_count
            if fix_count > 0:
                path.write_text(fixed_text, encoding="utf-8")
                issues, warnings = check_translation(fixed_text, locked_phrases, direction, source_text=source_text)

    issues.extend(ta_issues)

    if args.json:
        structured = [categorize_issue(i) for i in issues]
        auto_fixable = sum(1 for i in structured if i["category"] == "provision_mix")
        structured_warnings = [
            {"category": "slang_not_preserved", "severity": "warning", "message": w}
            for w in warnings
        ]
        data = {
            "direction": direction,
            "direction_auto_detected": args.direction is None,
            "issue_count": len(issues),
            "warning_count": len(warnings),
            "auto_fixable_count": auto_fixable,
            "auto_fixed_count": auto_fixed_count,
            "issues": structured,
            "warnings": structured_warnings,
        }
        json_output(data, exit_code=1 if issues else 0)

    if issues:
        print(f"Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("No issues found")

    if warnings:
        print(f"\nFound {len(warnings)} warning(s) (non-blocking):")
        for warning in warnings:
            print(f"  {warning}")

    if args.fix:
        if auto_fixed_count > 0:
            print(f"\nAuto-fixed {auto_fixed_count} provision issue(s) (费→人口)")
            print("Written back to file")
            if issues:
                print(f"\nRemaining issues after fix: {len(issues)}")
            else:
                print("\nAll issues resolved after fix")
        else:
            print("\nNo auto-fixable provision issues")

    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
