#!/usr/bin/env python3
"""Term Authority Enforcer.

Validates that a translated text uses the official translations locked during
pre-processing. Catches terms left untranslated (including abbreviations and
aliases) and ambiguous names that were not disambiguated.

Usage:
    python term_enforcer.py translated.txt --lock lock.json
    python term_enforcer.py translated.txt --source source.md
    python term_enforcer.py translated.txt --lock lock.json --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import build_lock_from_source, extract_cn_variants, json_output


def load_lock(lock_file: Path) -> dict:
    """Load a context lock file."""
    return json.loads(lock_file.read_text(encoding="utf-8"))


def _contains_cjk(target: str) -> bool:
    """Return True if target contains any CJK character."""
    return bool(re.search(r"[一-鿿]", target))


def count_occurrences(text: str, targets: list[str]) -> int:
    """Count how many times any of the targets appears as a whole word/phrase.

    For CJK targets, word boundaries are unreliable because CJK characters are
    all considered word characters by \b. We therefore use substring matching
    for any target that contains CJK characters, and word-boundary matching for
    pure ASCII/alphabetic targets. Single-CJK-char targets are skipped because
    bare-substring matching would inflate the count across the whole text.
    """
    count = 0
    text_lower = text.lower()
    for target in targets:
        target = target.strip().lower()
        if not target:
            continue
        if _contains_cjk(target):
            if len(target) < 2:
                continue
            # Substring match for CJK; escape still needed for regex specials.
            pattern = rf"{re.escape(target)}"
        else:
            pattern = rf"\b{re.escape(target)}\b"
        count += len(re.findall(pattern, text_lower))
    return count


def get_context_snippet(text: str, target: str, radius: int = 30) -> str:
    """Return a short snippet around the first occurrence of target."""
    text_lower = text.lower()
    target_lower = target.lower()
    if _contains_cjk(target):
        if len(target_lower) < 2:
            return ""
        pattern = rf"{re.escape(target_lower)}"
    else:
        pattern = rf"\b{re.escape(target_lower)}\b"
    match = re.search(pattern, text_lower)
    if not match:
        return ""
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    snippet = text[start:end].replace("\n", " ")
    return snippet.strip()


def _longest_common_substring(variants: list[str]) -> str:
    """Find the longest substring present in every variant."""
    if not variants:
        return ""
    shortest = min(variants, key=len)
    best = ""
    for start in range(len(shortest)):
        for end in range(start + 1, len(shortest) + 1):
            candidate = shortest[start:end]
            if len(candidate) <= len(best):
                continue
            if all(candidate in v for v in variants):
                best = candidate
    return best


def _locked_phrase_disambiguates(
    ambiguous_variants: list[str],
    locked_phrases: set[str],
    translation: str = "",
) -> bool:
    """Return True if a disambiguating locked phrase is present in the translation.

    The ambiguous base is approximated as the longest substring common to all
    Chinese variants (e.g. for Arachas variants the common substring is '蟹蜘蛛').
    The base counts as disambiguated only when some locked phrase that contains
    it actually appears in the translation; a bare base used elsewhere is still
    flagged. ``translation`` defaults to "" so a forgotten caller never silently
    passes a term.
    """
    if not ambiguous_variants:
        return False
    base = _longest_common_substring(ambiguous_variants)
    if not base:
        return False
    return any(base in phrase and phrase in translation for phrase in locked_phrases)


def enforce_terms(translated_path: Path, lock: dict) -> dict:
    """Check translated text against the lock table.

    Returns:
        dict with violation_count, violations, pass_count, locked_terms_checked.
    """
    translation = translated_path.read_text(encoding="utf-8")
    violations: list[dict] = []
    passed = 0
    checked = 0

    # Locked Chinese phrases from the lock. An ambiguous base is treated as
    # disambiguated only when a locked phrase containing it appears in the
    # translation (see _locked_phrase_disambiguates).
    locked_cn_phrases = extract_cn_variants(lock)

    for term, info in lock.get("terms", {}).items():
        status = info.get("status", "pending")
        variants = info.get("variants", [])

        if status == "ambiguous" and variants:
            checked += 1
            variant_cns = [v["cn"] for v in variants if v.get("cn")]
            found = any(vcn in translation for vcn in variant_cns)
            if found or _locked_phrase_disambiguates(variant_cns, locked_cn_phrases, translation):
                passed += 1
            else:
                expected = " / ".join(variant_cns)
                violations.append({
                    "term": term,
                    "canonical_en": info.get("canonical_en", term),
                    "expected_cn": expected,
                    "found_in_translation": "",
                    "issue_type": "ambiguous_not_disambiguated",
                    "context": get_context_snippet(translation, term),
                    "severity": "error",
                })
            continue

        if status not in ("confirmed", "auto_locked"):
            continue

        cn_term = info.get("cn", "")
        if not cn_term:
            continue

        checked += 1
        canonical_en = info.get("canonical_en", term)
        cn_variants = [v.strip() for v in cn_term.split("/") if v.strip()]

        # Targets that should NOT appear in the target-language text.
        en_targets = [canonical_en, term]
        for abbrev in info.get("abbrevs", []):
            en_targets.append(abbrev.strip())
        for alias in info.get("aliases", []):
            en_targets.append(alias.strip())

        en_in_translation = count_occurrences(translation, en_targets)
        cn_in_translation = count_occurrences(translation, cn_variants)

        if cn_in_translation > 0:
            passed += 1
        elif en_in_translation > 0:
            # English/abbreviation/alias still present — untranslated.
            violations.append({
                "term": term,
                "canonical_en": canonical_en,
                "expected_cn": cn_term,
                "found_in_translation": ", ".join(
                    t for t in en_targets
                    if count_occurrences(translation, [t]) > 0
                ) or "(english term)",
                "issue_type": "term_left_untranslated",
                "context": get_context_snippet(translation, term),
                "severity": "error",
            })
        else:
            # Neither official CN nor EN/abbrev appears — term may be missing
            # or translated literally with an unrecognized phrase.
            violations.append({
                "term": term,
                "canonical_en": canonical_en,
                "expected_cn": cn_term,
                "found_in_translation": "",
                "issue_type": "term_missing_or_literal",
                "context": get_context_snippet(translation, term),
                "severity": "warning",
            })

    return {
        "violation_count": len(violations),
        "violations": violations,
        "pass_count": passed,
        "locked_terms_checked": checked,
    }


def main():
    parser = argparse.ArgumentParser(description="Term Authority Enforcer")
    parser.add_argument("translated", help="Translated file to check")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--lock", help="Context lock JSON file")
    group.add_argument("--source", help="Source file (auto-build lock)")
    parser.add_argument("--json", action="store_true", help="Output structured JSON")
    args = parser.parse_args()

    translated_path = Path(args.translated)
    if not translated_path.exists():
        if args.json:
            json_output(None, errors=[f"translated file not found: {args.translated}"], exit_code=1)
        print(f"Error: translated file not found: {args.translated}")
        sys.exit(1)

    if args.lock:
        lock_file = Path(args.lock)
        if not lock_file.exists():
            if args.json:
                json_output(None, errors=[f"lock file not found: {args.lock}"], exit_code=1)
            print(f"Error: lock file not found: {args.lock}")
            sys.exit(1)
    else:
        source_path = Path(args.source)
        if not source_path.exists():
            if args.json:
                json_output(None, errors=[f"source file not found: {args.source}"], exit_code=1)
            print(f"Error: source file not found: {args.source}")
            sys.exit(1)
        lock_file = build_lock_from_source(source_path)

    lock = load_lock(lock_file)
    result = enforce_terms(translated_path, lock)

    if args.json:
        json_output(result, exit_code=1 if result["violation_count"] > 0 else 0)

    print("=" * 60)
    print("TERM AUTHORITY ENFORCEMENT")
    print("=" * 60)
    print()
    print(f"Checked: {result['locked_terms_checked']} locked terms")
    print(f"Passed:  {result['pass_count']}")
    print(f"Issues:  {result['violation_count']}")
    print()

    if result["violations"]:
        print("VIOLATIONS")
        print("-" * 60)
        for v in result["violations"]:
            print(f"- {v['term']} ({v['issue_type']})")
            print(f"  Expected: 「{v['expected_cn']}」")
            if v["found_in_translation"]:
                print(f"  Found:    「{v['found_in_translation']}」")
            if v.get("context"):
                print(f"  Context:  ...{v['context']}...")
            print()
        print("[BLOCKED] Term authority violations must be resolved before finalizing.")
        sys.exit(1)

    print("[PASS] All locked terms correctly translated.")
    sys.exit(0)


if __name__ == "__main__":
    main()
