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
from _shared import (
    build_lock_from_source,
    detect_direction,
    extract_cn_variants,
    get_term_authority,
    json_output,
)


def load_lock(lock_file: Path) -> dict:
    """Load a context lock file."""
    return json.loads(lock_file.read_text(encoding="utf-8"))


def _contains_cjk(target: str) -> bool:
    """Return True if target contains any CJK character."""
    return bool(re.search(r"[一-鿿]", target))


# Quote normalization: official card names carry Chinese quotes ("" U+201C/U+201D,
# '' U+2018/U+2019), but translations often use ASCII quotes. Normalize to ASCII
# before matching, or "残翼" (CN quotes) vs "残翼" (ASCII) mismatch and term_authority
# reports a false negative (card treated as missing from the translation).
_QUOTE_NORM = str.maketrans({
    "“": '"', "”": '"',
    "‘": "'", "’": "'",
})


def count_occurrences(text: str, targets: list[str], cjk_suppress: set[str] | None = None) -> int:
    """Count how many times any of the targets appears as a whole word/phrase.

    For CJK targets, word boundaries are unreliable (CJK has no delimiters and
    ``\b`` treats every Hanzi as a word char), so a bare substring match is used
    — but with one guard against false positives: an occurrence does NOT count
    when it is part of a longer KNOWN name. Otherwise the official name 希里
    would falsely match inside a different card like 冒牌希里 / 希里：冲刺 and the
    enforcer would report a false pass. ``cjk_suppress`` is the set of lowercased
    known CJK names; any occurrence of ``target`` fully covered by an occurrence
    of a longer suppress-name is absorbed. A structural two-sided boundary is
    deliberately NOT used: Chinese card names are normally glued to verbs /
    particles with no delimiter, so that would drop ~a third of real matches.

    Without ``cjk_suppress`` (other callers) behavior is unchanged bare-substring
    matching. Pure-ASCII/alphabetic targets keep ``\b`` word-boundary matching.
    Single-CJK-char targets are skipped (too noisy).
    """
    count = 0
    text_lower = text.lower().translate(_QUOTE_NORM)
    suppress_norm = {n.lower().translate(_QUOTE_NORM) for n in (cjk_suppress or ())}
    for target in targets:
        target = target.strip().lower().translate(_QUOTE_NORM)
        if not target:
            continue
        if _contains_cjk(target):
            if len(target) < 2:
                continue
            longer = [
                n for n in suppress_norm
                if len(n) > len(target) and target in n
            ]
            if not longer:
                count += len(re.findall(re.escape(target), text_lower))
                continue
            # Spans of every longer known name actually present in the text.
            spans: list[tuple[int, int]] = []
            for n in longer:
                if n in text_lower:
                    for m in re.finditer(re.escape(n), text_lower):
                        spans.append((m.start(), m.end()))
            spans.sort()
            for m in re.finditer(re.escape(target), text_lower):
                s, e = m.start(), m.end()
                # Covered by some longer-name span [p, q) with p <= s and q >= e.
                # spans are sorted by start; once p > s no earlier span remains.
                absorbed = False
                for p, q in spans:
                    if p > s:
                        break
                    if q >= e:
                        absorbed = True
                        break
                if not absorbed:
                    count += 1
        else:
            pattern = rf"\b{re.escape(target)}\b"
            count += len(re.findall(pattern, text_lower))
    return count


def get_context_snippet(text: str, target: str, radius: int = 30) -> str:
    """Return a short snippet around the first occurrence of target."""
    text_lower = text.lower().translate(_QUOTE_NORM)
    target_lower = target.lower().translate(_QUOTE_NORM)
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


def _build_cjk_suppress(lock: dict) -> tuple[set[str], list[str]]:
    """Set of lowercased known CJK names for count_occurrences absorption.

    Draws from the full TermAuthority CN index (so 希里 is absorbed by ANY known
    longer name like 冒牌希里, even one absent from this article's lock) plus this
    lock's own CN / variant phrases. Stops a short official CN from falsely
    matching inside a different, longer known name (false positive -> false pass).

    Returns ``(suppress, degraded)``: ``degraded`` lists human-readable warnings
    when the suppress set could not be built completely (TermAuthority load
    failure). Degradation can flip a BLOCKED into a false PASS, so callers must
    surface it as an issue, not a hint.
    """
    suppress: set[str] = set()
    degraded: list[str] = []
    try:
        ta = get_term_authority()
        suppress.update(cn.lower() for cn in ta.cn_entries)
    except Exception as e:
        # A failed TermAuthority load leaves the suppress set incomplete, so a
        # short official CN may be falsely counted inside a longer known name
        # (false positive -> false pass) — surface it instead of hiding it.
        msg = (f"TermAuthority failed to load ({e}); CJK suppress list "
               f"incomplete — results may contain false positives.")
        degraded.append(msg)
        print(f"[WARN] {msg}", file=sys.stderr)
    for info in lock.get("terms", {}).values():
        cn = info.get("cn", "")
        if cn:
            for v in cn.split("/"):
                v = v.strip()
                if v:
                    suppress.add(v.lower())
        for var in info.get("variants", []):
            vcn = var.get("cn", "")
            if vcn:
                suppress.add(vcn.lower())
    return suppress, degraded


def enforce_terms(translated_path: Path, lock: dict) -> dict:
    """Check translated text against the lock table (direction-aware).

    EN->CN (encn): each locked term's official Chinese must appear in the Chinese
    translation; an English/abbrev/alias left behind is untranslated; neither is
    missing-or-literal.

    CN->EN (cnen): the mirror — each locked term's official English must appear in
    the English translation; the Chinese source form left behind is untranslated;
    neither is missing-or-literal. A collision (one Chinese name -> several
    English cards) passes when ANY candidate English is present.

    Direction is taken from the lock's ``direction`` field (set by context_lock
    build_lock) and falls back to detect_direction on the translation.

    Returns:
        dict with violation_count, violations, pass_count, locked_terms_checked,
        warnings (degradation notices, e.g. CJK suppress built incompletely —
        these can flip a BLOCKED into a false PASS and must block finalization).
    """
    translation = translated_path.read_text(encoding="utf-8")
    direction = lock.get("direction") or detect_direction(translation)
    is_cnen = direction == "cnen"
    violations: list[dict] = []
    passed = 0
    checked = 0

    # Locked Chinese phrases from the lock. An ambiguous base is treated as
    # disambiguated only when a locked phrase containing it appears in the
    # translation (see _locked_phrase_disambiguates).
    locked_cn_phrases = extract_cn_variants(lock)
    # Known CJK names used to absorb false-positive substring matches.
    suppress, degraded_warnings = _build_cjk_suppress(lock)

    for term, info in lock.get("terms", {}).items():
        status = info.get("status", "pending")
        variants = info.get("variants", [])

        if status == "ambiguous" and variants:
            checked += 1
            if is_cnen:
                # Collision: one Chinese name -> several official English cards.
                # Any candidate English present in the (English) translation passes.
                candidate_ens = [v["en"] for v in variants if v.get("en")]
                found = count_occurrences(translation, candidate_ens) > 0
                expected = " / ".join(candidate_ens)
            else:
                variant_cns = [v["cn"] for v in variants if v.get("cn")]
                found = any(vcn in translation for vcn in variant_cns) or \
                    _locked_phrase_disambiguates(variant_cns, locked_cn_phrases, translation)
                expected = " / ".join(variant_cns)
            if found:
                passed += 1
            else:
                v = {
                    "term": term,
                    "canonical_en": info.get("canonical_en", term),
                    "expected_cn": "" if is_cnen else expected,
                    "found_in_translation": "",
                    "issue_type": "ambiguous_not_disambiguated",
                    "context": get_context_snippet(translation, term),
                    "severity": "error",
                }
                if is_cnen:
                    v["expected_en"] = expected
                violations.append(v)
            continue

        if status not in ("confirmed", "auto_locked"):
            continue

        if is_cnen:
            canonical_en = info.get("canonical_en", "")
            if not canonical_en:
                continue
            checked += 1
            cn_source = info.get("cn", "") or term
            en_targets = [canonical_en]
            for alias in info.get("aliases", []):
                en_targets.append(alias.strip())
            for abbrev in info.get("abbrevs", []):
                en_targets.append(abbrev.strip())
            en_in_translation = count_occurrences(translation, en_targets)
            cn_in_translation = (
                count_occurrences(translation, [cn_source], cjk_suppress=suppress)
                if cn_source else 0
            )
            if en_in_translation > 0:
                passed += 1
            elif cn_in_translation > 0:
                # Chinese source form left in the English output — untranslated.
                violations.append({
                    "term": term,
                    "canonical_en": canonical_en,
                    "expected_cn": "",
                    "expected_en": canonical_en,
                    "found_in_translation": cn_source,
                    "issue_type": "term_left_untranslated",
                    "context": get_context_snippet(translation, cn_source),
                    "severity": "error",
                })
            else:
                # Neither official English nor the CN source form appears — the
                # term may be missing or rendered with an unrecognized phrase.
                violations.append({
                    "term": term,
                    "canonical_en": canonical_en,
                    "expected_cn": "",
                    "expected_en": canonical_en,
                    "found_in_translation": "",
                    "issue_type": "term_missing_or_literal",
                    "context": get_context_snippet(translation, canonical_en),
                    "severity": "warning",
                })
            continue

        # --- EN->CN (existing) ---
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
        cn_in_translation = count_occurrences(translation, cn_variants, cjk_suppress=suppress)

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
                    if count_occurrences(translation, [t], cjk_suppress=suppress) > 0
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

    # Additive: precise, agent-actionable fields so a BLOCKED report tells the
    # agent exactly what to fix. expected_official is the official rendering to
    # use (CN for EN->CN, EN for CN->EN; a " / "-joined option list for a
    # collision / ambiguous name). offending_quote is the locatable snippet in
    # the translation (empty when the term is simply absent -> nothing to point
    # at). existing fields (expected_cn / expected_en / found_in_translation /
    # context) are preserved for back-compat.
    for v in violations:
        v["expected_official"] = v.get("expected_en") or v.get("expected_cn", "")
        v["offending_quote"] = v.get("context", "")

    return {
        "violation_count": len(violations),
        "violations": violations,
        "pass_count": passed,
        "locked_terms_checked": checked,
        "direction": direction,
        "warnings": degraded_warnings,
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

    # Degradation (e.g. CJK suppress built incompletely) can flip a BLOCKED
    # into a false PASS, so it counts as an issue everywhere: JSON exit code,
    # the plain "Issues:" total (the guard parses it), and the final verdict.
    issue_total = result["violation_count"] + len(result["warnings"])

    if args.json:
        json_output(result, exit_code=1 if issue_total > 0 else 0)

    print("=" * 60)
    print("TERM AUTHORITY ENFORCEMENT")
    print("=" * 60)
    print()
    print(f"Checked: {result['locked_terms_checked']} locked terms")
    print(f"Passed:  {result['pass_count']}")
    print(f"Issues:  {issue_total}")
    print()

    if result["violations"]:
        print("VIOLATIONS")
        print("-" * 60)
        for v in result["violations"]:
            print(f"- {v['term']} ({v['issue_type']})")
            expected = v.get("expected_en") or v.get("expected_cn", "")
            print(f"  Expected: 「{expected}」")
            if v["found_in_translation"]:
                print(f"  Found:    「{v['found_in_translation']}」")
            if v.get("context"):
                print(f"  Context:  ...{v['context']}...")
            print()

    if result["warnings"]:
        print("DEGRADED")
        print("-" * 60)
        for w in result["warnings"]:
            print(f"- {w}")
        print()

    if issue_total > 0:
        print("[BLOCKED] Term authority violations must be resolved before finalizing.")
        sys.exit(1)

    print("[PASS] All locked terms correctly translated.")
    sys.exit(0)


if __name__ == "__main__":
    main()
