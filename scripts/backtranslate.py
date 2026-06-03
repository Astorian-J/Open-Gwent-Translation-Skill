#!/usr/bin/env python3
"""
Back-Translation Validator.
Translates Chinese output back to English and compares with original.
Flags semantic drift and meaning loss.

Usage:
    python backtranslate.py <source_en.txt> <translated_cn.txt> [--detail]
"""

import sys
from pathlib import Path


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


def generate_report(original: str, translated: str, backtranslated: str) -> str:
    """Generate a back-translation comparison report."""
    issues = semantic_comparison(original, backtranslated)

    lines = [
        "# Back-Translation Report",
        "",
        f"Original sentences: {len([s for s in original.split('.') if s.strip()])}",
        f"Translated sentences: {len([s for s in translated.split('。') if s.strip()])}",
        f"Issues found: {len(issues)}",
        "",
        "## Semantic Comparison",
        "",
    ]

    if not issues:
        lines.append("No significant semantic drift detected.")
    else:
        for issue in issues:
            severity_icon = {"high": "", "medium": "", "low": ""}[issue["severity"]]
            lines.append(f"{severity_icon} **[{issue['severity'].upper()}]** {issue['type']}")
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
        f"{backtranslated[:200]}",
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
    if len(sys.argv) < 3:
        print("Usage: python backtranslate.py <source_en.txt> <translated_cn.txt> [--detail]")
        print("")
        print("This script generates a back-translation validation framework.")
        print("For actual back-translation, feed the Chinese text to an LLM with:")
        print('  "Translate this Chinese text back to English literally."')
        sys.exit(1)

    source_file = sys.argv[1]
    translated_file = sys.argv[2]
    detail = "--detail" in sys.argv

    original = Path(source_file).read_text(encoding="utf-8")
    translated = Path(translated_file).read_text(encoding="utf-8")

    # Placeholder: In practice, backtranslation would come from an LLM
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

    # Generate placeholder report with heuristics
    placeholder_back = f"[Back-translation not provided. Original length: {len(original)} chars]"
    report = generate_report(original, translated, placeholder_back)

    if detail:
        print(report)
    else:
        print("Run with --detail to see the full report template.")


if __name__ == "__main__":
    import re
    main()
