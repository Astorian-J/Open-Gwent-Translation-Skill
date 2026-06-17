#!/usr/bin/env python3
"""
Back-Translation Validator.
Translates Chinese output back to English and compares with original.
Flags semantic drift and meaning loss.

Usage:
    python backtranslate.py <source_en.txt> <translated_cn.txt> [backtranslated_en.txt] [--json]
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import json_output


def semantic_comparison(original: str, backtranslated: str) -> list[dict]:
    """
    Compare original and back-translated text for semantic drift.
    Returns list of potential issues.

    Note: This is a heuristic check. A real implementation would use
    an LLM call for back-translation. This script provides the framework
    and reporting format.
    """
    issues = []

    # Check 1: Key numeric values preserved
    orig_nums = set(re.findall(r'\d+', original))
    back_nums = set(re.findall(r'\d+', backtranslated))
    missing_nums = orig_nums - back_nums
    if missing_nums:
        issues.append({
            "severity": "high",
            "type": "numeric_mismatch",
            "detail": f"Original numbers {missing_nums} not found in back-translation"
        })

    # Check 2: Key English terms appear in back-translation
    # Extract capitalized terms from original
    orig_terms = set(re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b', original))
    back_lower = backtranslated.lower()
    for term in orig_terms:
        if len(term) > 3 and term.lower() not in back_lower:
            issues.append({
                "severity": "medium",
                "type": "term_missing",
                "detail": f"Key term '{term}' may be missing in translation"
            })

    # Check 3: Sentence count similarity
    orig_sents = len([s for s in original.split('.') if s.strip()])
    back_sents = len([s for s in backtranslated.split('.') if s.strip()])
    if abs(orig_sents - back_sents) > orig_sents * 0.5:
        issues.append({
            "severity": "low",
            "type": "length_drift",
            "detail": f"Sentence count differs significantly: {orig_sents} vs {back_sents}"
        })

    return issues


def generate_report(original: str, translated: str, backtranslated: str | None = None) -> str:
    """Generate a back-translation comparison report."""
    issues = semantic_comparison(original, backtranslated) if backtranslated else []

    orig_sents = len([s for s in original.split('.') if s.strip()])
    translated_sents = len([s for s in translated.split('。') if s.strip()])

    lines = [
        "# Back-Translation Report",
        "",
        f"Original sentences: {orig_sents}",
        f"Translated sentences: {translated_sents}",
        f"Issues found: {len(issues)}",
        "",
        "## Semantic Comparison",
        "",
    ]

    if not issues:
        lines.append("No significant semantic drift detected.")
    else:
        for issue in issues:
            lines.append(f"**[{issue['severity'].upper()}]** {issue['type']}")
            lines.append(f"   {issue['detail']}")
            lines.append("")

    lines.extend([
        "",
        "## Excerpt Comparison",
        "",
        "Original (first 200 chars):",
        f"```",
        f"{original[:200]}",
        f"```",
        "",
        "Back-Translation (first 200 chars):",
        f"```",
        f"{backtranslated[:200] if backtranslated else 'N/A'}",
        f"```",
        "",
        "## Note",
        "",
        "Back-translation should capture the *meaning* of the original, not its wording.",
        "Some divergence is expected due to cultural/linguistic differences.",
        "Focus on: missing key information, wrong numbers, reversed causality.",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Back-Translation Validator")
    parser.add_argument("source", help="Original English source file")
    parser.add_argument("translated", help="Chinese translated file")
    parser.add_argument("backtranslated", nargs="?", help="Back-translated English file")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    args = parser.parse_args()

    source_path = Path(args.source)
    translated_path = Path(args.translated)

    if not source_path.exists():
        if args.json:
            json_output(None, errors=[f"source file not found: {args.source}"], exit_code=1)
        print(f"Error: source file not found: {args.source}")
        sys.exit(1)
    if not translated_path.exists():
        if args.json:
            json_output(None, errors=[f"translated file not found: {args.translated}"], exit_code=1)
        print(f"Error: translated file not found: {args.translated}")
        sys.exit(1)

    original = source_path.read_text(encoding="utf-8")
    translated = translated_path.read_text(encoding="utf-8")

    if args.backtranslated:
        back_path = Path(args.backtranslated)
        if not back_path.exists():
            if args.json:
                json_output(None, errors=[f"back-translated file not found: {args.backtranslated}"], exit_code=1)
            print(f"Error: back-translated file not found: {args.backtranslated}")
            sys.exit(1)
        backtranslated = back_path.read_text(encoding="utf-8")
        issues = semantic_comparison(original, backtranslated)
        if args.json:
            json_output({
                "original_sentences": len([s for s in original.split('.') if s.strip()]),
                "translated_sentences": len([s for s in translated.split('。') if s.strip()]),
                "backtranslated_sentences": len([s for s in backtranslated.split('.') if s.strip()]),
                "issue_count": len(issues),
                "issues": issues,
            }, exit_code=1 if issues else 0)
        report = generate_report(original, translated, backtranslated)
        print(report)
        return

    # No backtranslated file provided: print instructions.
    if args.json:
        json_output({
            "original_sentences": len([s for s in original.split('.') if s.strip()]),
            "translated_sentences": len([s for s in translated.split('。') if s.strip()]),
            "backtranslated_sentences": 0,
            "issue_count": 0,
            "issues": [],
            "note": "Back-translation file required for comparison. See printed instructions.",
        }, exit_code=0)

    print("=" * 60)
    print("BACK-TRANSLATION VALIDATION FRAMEWORK")
    print("=" * 60)
    print()
    print("Step 1: Original text loaded")
    print(f"  Length: {len(original)} chars")
    print()
    print("Step 2: Chinese translation loaded")
    print(f"  Length: {len(translated)} chars")
    print()
    print("Step 3: BACK-TRANSLATION REQUIRED")
    print()
    print("  To complete validation, run the Chinese text through an LLM with:")
    print('  Prompt: "Translate the following Chinese text back to English')
    print('          as literally as possible, preserving all details:"')
    print()
    print("  Save the result to backtranslated.txt, then run:")
    print("  python backtranslate.py source.txt translated.txt backtranslated.txt")
    print()


if __name__ == "__main__":
    main()
