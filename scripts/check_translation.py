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
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (
    extract_card_names,
    extract_card_names_no_colon,
    json_output,
    SKIP_WORDS_MINIMAL,
)

# --- Load rules from references ---


def _get_ref_path(filename: str) -> Path:
    return Path(__file__).parent.parent / "references" / filename


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


def load_card_corrections():
    """Load outdated card names from card_names.md"""
    corrections = {}
    card_file = _get_ref_path("card_names.md")
    if not card_file.exists():
        return corrections

    text = card_file.read_text(encoding="utf-8")
    in_renamed = False
    for line in text.split("\n"):
        line = line.strip()
        if "Renamed / Corrected" in line:
            in_renamed = True
            continue
        if in_renamed and line.startswith("##"):
            break
        if in_renamed and line.startswith("|") and "---" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4 and parts[1] and parts[2]:
                old, new = parts[1], parts[2]
                if old and new and old != "Skill原版":
                    corrections[old] = new

    return corrections


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


def load_fuzzy_fixes():
    """Load Chinese fuzzy fixes: typos, homophones, deck abbreviations."""
    fixes = {
        "typos": {},      # wrong -> correct
        "homophones": {}, # wrong -> correct (with context)
        "deck_abbr": {},  # abbreviation -> full name
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
            current_section = "deck_abbr"
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

                if wrong and correct and wrong not in ("Wrong", "Abbreviation", "✓"):
                    fixes[current_section][wrong] = {
                        "correct": correct,
                        "notes": notes,
                    }

    return fixes


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


def check_translation(text: str) -> list[str]:
    """Check translation text, return list of issues."""
    issues = []
    forbidden_terms = load_forbidden_terms()
    card_corrections = load_card_corrections()
    abbreviations = load_abbreviations()
    ambiguous = load_ambiguous_names()

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
        if pop > pwr + 5:
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
        if base_name in text:
            # Check if any full version (EN or CN) is present in the text
            has_full = any(en in text or (cn and cn in text) for en, cn in versions)
            if not has_full:
                issues.append(
                    f"ambiguous name: 「{base_name}」has multiple versions ({len(versions)}). "
                    f"Specify full name. See ambiguous_names.md"
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
            issues.append(
                f"abbreviation: 「{abbrev}」— consider expanding on first use: "
                f"{cn} ({en})"
            )
        elif abbrev in ("R1", "R2", "R3"):
            pass

    # 12. Check Chinese fuzzy fixes (typos, homophones, deck abbreviations)
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

    # 12c. Deck abbreviations
    # Skip faction abbreviations (single-char meta rules like "北" = suffix marker)
    # Only detect actual deck names with >= 3 chars
    for abbr, info in fuzzy_fixes["deck_abbr"].items():
        if len(abbr) < 3:
            continue  # Skip faction abbreviation rules like "北", "岛", "怪"
        if abbr in text:
            idx = text.index(abbr)
            start = max(0, idx - 20)
            end = min(len(text), idx + len(abbr) + 20)
            ctx = text[start:end].replace('\n', ' ')
            issues.append(
                f"deck abbreviation: 「{abbr}」→ 「{info['correct']}」 "
                f"({info['notes']}) (context: ...{ctx}...)"
            )

    # 13. Check English residue (untranslated card names)
    residue_issues = check_english_residue(text)
    issues.extend(residue_issues)

    return issues


def check_english_residue(text: str) -> list[str]:
    """Scan translated text for untranslated English card names.

    Extracts English capitalized phrases from the Chinese translation,
    looks them up in card_names.md, and reports any matches as
    likely missed translations.
    """
    issues = []

    # Load card database
    card_file = _get_ref_path("card_names.md")
    if not card_file.exists():
        return issues

    card_map = {}
    card_text = card_file.read_text(encoding="utf-8")
    for line in card_text.split("\n"):
        line = line.strip()
        if line.startswith("|") and "---" not in line and "English" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4 and parts[1] and parts[2]:
                en = parts[1]
                cn = parts[2]
                if en not in ("English", "—", "") and cn not in ("Chinese", "—", ""):
                    card_map[en.lower()] = (en, cn)

    if not card_map:
        return issues

    # Extract English phrases using shared logic (supports function words)
    from _shared import (
        extract_card_names,
        extract_card_names_no_colon,
        SKIP_WORDS_MINIMAL,
    )

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
                    f"(found in card_names.md, may be untranslated)"
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


# Issue prefixes used to derive structured categories for --json output.
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
    "deck abbreviation:": "deck_abbreviation",
    "English residue:": "english_residue",
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
    parser.add_argument("--fix", action="store_true", help="Auto-fix provision-terminology errors only (费→人口)")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        if args.json:
            json_output(None, errors=[f"file not found: {args.file}"], exit_code=1)
        print(f"Error: file not found: {args.file}")
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    issues = check_translation(text)

    # Apply auto-fix before emitting any output so JSON reports accurate counts.
    auto_fixed_count = 0
    if args.fix:
        fixed_text, fix_count = auto_fix(text)
        auto_fixed_count = fix_count
        if fix_count > 0:
            path.write_text(fixed_text, encoding="utf-8")
            issues = check_translation(fixed_text)

    if args.json:
        structured = [categorize_issue(i) for i in issues]
        auto_fixable = sum(1 for i in structured if i["category"] == "provision_mix")
        data = {
            "issue_count": len(issues),
            "auto_fixable_count": auto_fixable,
            "auto_fixed_count": auto_fixed_count,
            "issues": structured,
        }
        json_output(data, exit_code=1 if issues else 0)

    if issues:
        print(f"Found {len(issues)} issue(s):")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("No issues found")

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
