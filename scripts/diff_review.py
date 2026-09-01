#!/usr/bin/env python3
"""
Diff Review Mode (审校差异模式).
Compares a translation against source to find issues without retranslating.

Usage:
    python diff_review.py <source_en.txt> <translation.txt> [--output report.md] [--json]
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (
    extract_abbreviations,
    extract_capitalized_phrases,
    extract_card_names,
    json_output,
    run_utf8,
)
from check_translation import load_forbidden_terms

# Module-level constants
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}



def extract_proper_nouns(text: str) -> set[str]:
    """Extract likely Gwent proper nouns (card names, abilities, etc.)."""
    nouns = set()

    for name in extract_card_names(text):
        nouns.add(name)

    for name in extract_capitalized_phrases(text, max_words=3, min_length=4):
        nouns.add(name)

    for abbrev in extract_abbreviations(text):
        nouns.add(abbrev)

    return nouns


def check_terminology(source: str, translation: str) -> list[dict]:
    """Check if key terms are correctly translated."""
    issues = []

    # 复用 check_translation 的正式 loader（按 section header 解析 correction_guide.md §1）。
    # 原手写解析的触发条件「同一行同时含 --- 和 Wrong」永不成立，禁译词检测从未工作过。
    known_swaps = load_forbidden_terms()

    # Check for forbidden terms in translation
    for wrong, right in known_swaps.items():
        if wrong in translation:
            issues.append({
                "severity": "high",
                "type": "forbidden_term",
                "detail": f"「{wrong}」→ should be 「{right}」",
                "suggestion": f"Replace 「{wrong}」 with 「{right}」"
            })

    return issues


def check_numerics(source: str, translation: str) -> list[dict]:
    """Check if numbers are preserved and not reversed."""
    issues = []

    # Check provision/power format
    for match in re.finditer(r'(\d+)\s*人口\s*(\d+)\s*战力', translation):
        pop, pwr = int(match.group(1)), int(match.group(2))
        if pop == pwr:
            issues.append({
                "severity": "high",
                "type": "identical_numbers",
                "detail": f"「{pop}人口{pwr}战力」— numbers are identical, likely reversed",
                "suggestion": "Check original 'X for Y' format: X=power, Y=provision"
            })

    # Check for Chinese numerals
    if re.search(r'[一二三四五六七八九十]+(?:点|人口)', translation):
        issues.append({
            "severity": "medium",
            "type": "chinese_numerals",
            "detail": "Chinese numerals detected—use Arabic numerals",
            "suggestion": "Replace 一二三四 with 1234"
        })

    return issues


def check_completeness(source: str, translation: str) -> list[dict]:
    """Check for omissions or additions."""
    issues = []

    source_nouns = extract_proper_nouns(source)
    translation_lower = translation.lower()

    # Check for missing card names
    for noun in source_nouns:
        # Simple check: if the noun isn't in the translation
        # (This is heuristic—card names may be translated)
        noun_lower = noun.lower()
        if len(noun) > 5 and noun_lower not in translation_lower:
            # Skip common words
            if noun.split()[0] not in {"The", "This", "That", "These", "When", "What", "Where", "Which", "While"}:
                issues.append({
                    "severity": "low",
                    "type": "possible_omission",
                    "detail": f"'{noun}' from source not found in translation",
                    "suggestion": f"Verify if '{noun}' was intentionally omitted or translated differently"
                })

    return issues


def run_full_checker(translation_file: str) -> list[dict]:
    """Run the standalone terminology checker and return structured issues.

    Always parses check_translation's --json envelope (success/exit_code/
    data/issues) — the plain-text output format is not a stable contract.
    Exit code 1 from found issues is the normal path, not a crash. A missing
    or malformed envelope means the checker itself failed; that is reported
    as a high-severity checker_error issue (fail-closed) instead of silently
    returning an empty list.
    """
    script = Path(__file__).parent / "check_translation.py"
    if not script.exists():
        return [{
            "severity": "high",
            "type": "checker_error",
            "detail": "[checker error] scripts/check_translation.py missing",
            "suggestion": "Restore scripts/check_translation.py and re-run",
        }]

    cmd = [sys.executable, str(script), translation_file, "--json"]
    result = run_utf8(cmd, timeout=60)

    try:
        parsed = json.loads(result.stdout)
        if not isinstance(parsed, dict) or "success" not in parsed:
            raise ValueError("not a JSON envelope")
        raw_issues = parsed["data"]["issues"]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return [{
            "severity": "high",
            "type": "checker_error",
            "detail": (f"[checker error] check_translation.py produced no valid "
                       f"JSON envelope (exit {result.returncode})"),
            "suggestion": "Run check_translation.py directly to see the underlying error",
        }]

    # check_translation severities are error/warning; map onto this report's
    # high/medium/low scale so the issues actually surface in the human report.
    severity_map = {"error": "high", "warning": "medium"}
    return [
        {
            "severity": severity_map.get(issue.get("severity", ""), "medium"),
            "type": issue.get("category", "terminology_checker"),
            "detail": issue.get("message", ""),
            "suggestion": "See check_translation.py output for details",
        }
        for issue in raw_issues
    ]


def generate_report(source: str, translation: str, translation_file: str | None = None, json_mode: bool = False) -> tuple[str | dict, int]:
    """Generate a comprehensive diff review report.

    Returns (report, issue_count); the caller decides the exit code from
    issue_count so JSON and human modes share the same semantics.
    """
    terminology_issues = check_terminology(source, translation)
    numeric_issues = check_numerics(source, translation)
    completeness_issues = check_completeness(source, translation)

    all_issues = terminology_issues + numeric_issues + completeness_issues

    if translation_file:
        all_issues.extend(run_full_checker(translation_file))

    # Sort by severity
    all_issues.sort(key=lambda x: _SEVERITY_ORDER.get(x["severity"], 3))

    source_sentences = len([s for s in source.split('.') if s.strip()])
    translation_sentences = len([s for s in translation.split('。') if s.strip()])

    if json_mode:
        return {
            "source_length": len(source),
            "source_sentences": source_sentences,
            "translation_length": len(translation),
            "translation_sentences": translation_sentences,
            "issue_count": len(all_issues),
            "issues": all_issues,
        }, len(all_issues)

    lines = [
        "# Diff Review Report (审校差异报告)",
        "",
        f"Source length: {len(source)} chars | {source_sentences} sentences",
        f"Translation length: {len(translation)} chars | {translation_sentences} sentences",
        f"Issues found: {len(all_issues)}",
        "",
    ]

    # Group by severity
    for sev in ["high", "medium", "low"]:
        sev_issues = [i for i in all_issues if i["severity"] == sev]
        if sev_issues:
            sev_label = {"high": "严重", "medium": "中等", "low": "轻微"}[sev]
            lines.append(f"## {sev_label} ({sev.upper()}) — {len(sev_issues)} 项")
            lines.append("")
            for i, issue in enumerate(sev_issues, 1):
                lines.append(f"{i}. **{issue['type']}**")
                lines.append(f"   {issue['detail']}")
                if "suggestion" in issue:
                    lines.append(f"   → {issue['suggestion']}")
                lines.append("")

    if not all_issues:
        lines.append("No issues detected.")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## Review Checklist",
        "",
        "- [ ] All card names correctly translated",
        "- [ ] Numbers preserved and not reversed",
        "- [ ] Provision always '人口' in formal contexts",
        "- [ ] Passive voice converted to active",
        "- [ ] Arabic numerals throughout",
        "- [ ] No significant omissions from source",
        "- [ ] Tone matches article context (formal vs. casual)",
        "",
    ])

    return "\n".join(lines), len(all_issues)


def main():
    parser = argparse.ArgumentParser(description="Diff Review Mode")
    parser.add_argument("source", help="English source file")
    parser.add_argument("translation", help="Translated file")
    parser.add_argument("--output", help="Write report to file")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    args = parser.parse_args()

    source_path = Path(args.source)
    translation_path = Path(args.translation)

    if not source_path.exists():
        if args.json:
            json_output(None, errors=[f"source file not found: {args.source}"], exit_code=1)
        print(f"Error: source file not found: {args.source}")
        sys.exit(1)
    if not translation_path.exists():
        if args.json:
            json_output(None, errors=[f"translation file not found: {args.translation}"], exit_code=1)
        print(f"Error: translation file not found: {args.translation}")
        sys.exit(1)

    source = source_path.read_text(encoding="utf-8")
    translation = translation_path.read_text(encoding="utf-8")

    report, issue_count = generate_report(source, translation, translation_file=args.translation, json_mode=args.json)

    if args.json:
        json_output(report, exit_code=1 if issue_count > 0 else 0)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(report)

    # Same exit-code contract as the other checkers: any issue -> non-zero.
    sys.exit(1 if issue_count > 0 else 0)


if __name__ == "__main__":
    main()
