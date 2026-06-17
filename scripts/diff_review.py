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
import subprocess
import sys
from pathlib import Path
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (
    extract_abbreviations,
    extract_capitalized_phrases,
    extract_card_names,
    json_output,
)

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

    # Load known terms
    ref_dir = Path(__file__).parent.parent / "references"
    known_swaps = {}

    correction_guide = ref_dir / "correction_guide.md"
    if correction_guide.exists():
        text = correction_guide.read_text(encoding="utf-8")
        in_table = False
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("|") and "---" in line and "Wrong" in line:
                in_table = True
                continue
            if in_table and line.startswith("|") and "---" not in line:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3 and parts[1] and parts[2]:
                    wrong = parts[1]
                    right = parts[2]
                    if wrong != "Wrong" and "provision" not in wrong.lower():
                        known_swaps[wrong] = right
            if in_table and not line.startswith("|"):
                in_table = False

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

    # Extract numbers from source
    source_nums = re.findall(r'\b(\d+)\s*(?:for|power|provision|p|P)\b', source, re.IGNORECASE)
    source_plain_nums = re.findall(r'\b\d+\b', source)

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


def run_full_checker(translation_file: str, json_mode: bool = False) -> list[dict]:
    """Run the standalone terminology checker and return structured issues."""
    issues = []
    script = Path(__file__).parent / "check_translation.py"
    if not script.exists():
        return issues

    cmd = [sys.executable, str(script), translation_file]
    if json_mode:
        cmd.append("--json")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if json_mode:
        try:
            parsed = json.loads(result.stdout)
            for issue in parsed.get("data", {}).get("issues", []):
                issues.append({
                    "severity": issue.get("severity", "medium"),
                    "type": issue.get("category", "terminology_checker"),
                    "detail": issue.get("message", ""),
                    "suggestion": "See check_translation.py output for details",
                })
        except (json.JSONDecodeError, ValueError):
            pass
        return issues

    for line in result.stdout.split("\n"):
        if line.strip().startswith("-"):
            # Heuristic: treat any checker output line as a medium-severity issue.
            issues.append({
                "severity": "medium",
                "type": "terminology_checker",
                "detail": line.strip()[2:].strip(),
                "suggestion": "See check_translation.py output for details",
            })
    return issues


def generate_report(source: str, translation: str, translation_file: str | None = None, json_mode: bool = False) -> str | dict:
    """Generate a comprehensive diff review report."""
    terminology_issues = check_terminology(source, translation)
    numeric_issues = check_numerics(source, translation)
    completeness_issues = check_completeness(source, translation)

    all_issues = terminology_issues + numeric_issues + completeness_issues

    if translation_file:
        all_issues.extend(run_full_checker(translation_file, json_mode=json_mode))

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
        }

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

    return "\n".join(lines)


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

    report = generate_report(source, translation, translation_file=args.translation, json_mode=args.json)

    if args.json:
        json_output(report, exit_code=1 if report["issue_count"] > 0 else 0)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
