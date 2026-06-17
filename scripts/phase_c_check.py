#!/usr/bin/env python3
"""
Phase C Self-Check Runner.

Loads the structured Phase C checklist from references/phase_c_checklist.md
and runs the machine-checkable rules against a translated file.

Usage:
    python phase_c_check.py <translated_file> [--direction encn|cnen]

Exit code:
    0 = all automated checks passed (manual checks may still need review)
    1 = one or more automated checks failed
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import json_output, parse_markdown_table


def load_rules(ref_dir: Path) -> list[dict[str, str]]:
    """Load Phase C rules from references/phase_c_checklist.md."""
    checklist = ref_dir / "phase_c_checklist.md"
    if not checklist.exists():
        raise FileNotFoundError(f"Phase C checklist not found: {checklist}")

    text = checklist.read_text(encoding="utf-8")
    rows = parse_markdown_table(text, min_columns=5)

    rules = []
    for row in rows:
        rid = row.get("id", "").strip()
        check_type = row.get("check_type", "").strip().lower()
        pattern = row.get("pattern", "").strip()
        issue_message = row.get("issue_message", "").strip()
        description = row.get("description", "").strip()

        if not rid or not check_type:
            continue

        # Unescape pipes inside backtick-wrapped regex patterns.
        if pattern.startswith("`") and pattern.endswith("`"):
            pattern = pattern[1:-1]
        pattern = pattern.replace("\\|", "|")

        rules.append({
            "id": rid,
            "description": description,
            "check_type": check_type,
            "pattern": pattern,
            "issue_message": issue_message,
        })

    return rules


def detect_direction(text: str) -> str:
    """Heuristically detect translation direction from output text."""
    chinese_chars = len(re.findall(r"[一-鿿]", text))
    english_words = len(re.findall(r"[A-Za-z]{2,}", text))

    # If substantial Chinese and limited English, assume EN->CN output.
    if chinese_chars > english_words * 2 and chinese_chars > 20:
        return "encn"
    # If substantial English and limited Chinese, assume CN->EN output.
    if english_words > chinese_chars / 2 and english_words > 20:
        return "cnen"
    # Fallback: more Chinese than English -> encn, else cnen.
    return "encn" if chinese_chars >= english_words else "cnen"


def check_regex_forbidden(text: str, pattern: str) -> list[str]:
    """Return issues for each match of a forbidden regex pattern."""
    issues = []
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        return [f"[checker error] invalid regex '{pattern}': {e}"]

    for match in compiled.finditer(text):
        matched = match.group(0)
        issues.append(matched)
    return issues


def check_regex_required(text: str, pattern: str) -> bool:
    """Return True if required pattern is found."""
    try:
        return bool(re.search(pattern, text))
    except re.error as e:
        print(f"[checker error] invalid regex '{pattern}': {e}", file=sys.stderr)
        return False


def check_english_residue(text: str, ref_dir: Path) -> list[str]:
    """Delegate English residue detection to check_translation.py."""
    check_script = Path(__file__).parent / "check_translation.py"
    if not check_script.exists():
        return []

    # Import directly to avoid subprocess overhead and preserve types.
    sys.path.insert(0, str(Path(__file__).parent))
    from check_translation import check_english_residue as residue_checker
    return residue_checker(text)


def check_ambiguous_names(text: str, ref_dir: Path) -> list[str]:
    """Delegate ambiguous-name detection to check_translation.py."""
    sys.path.insert(0, str(Path(__file__).parent))
    from check_translation import check_translation
    all_issues = check_translation(text)
    return [issue for issue in all_issues if "ambiguous name:" in issue]


def load_chinese_card_names(ref_dir: Path) -> dict[str, str]:
    """Build Chinese card name -> English mapping from card_names.md."""
    card_file = ref_dir / "card_names.md"
    if not card_file.exists():
        return {}

    mapping: dict[str, str] = {}
    text = card_file.read_text(encoding="utf-8")
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("|") and "---" not in line and "English" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4 and parts[1] and parts[2]:
                en, cn = parts[1], parts[2]
                if en not in ("English", "—", "") and cn not in ("Chinese", "—", ""):
                    mapping[cn] = en
    return mapping


def check_chinese_residue(text: str, ref_dir: Path) -> list[str]:
    """Detect untranslated Chinese card names in CN->EN output."""
    mapping = load_chinese_card_names(ref_dir)
    if not mapping:
        return []

    # Sort by length descending so longer names match before their substrings.
    names = sorted(mapping.keys(), key=len, reverse=True)
    issues = []
    reported: set[str] = set()

    for cn in names:
        if len(cn) < 2:
            continue
        if cn in reported:
            continue
        if cn in text:
            en = mapping[cn]
            issues.append(f"Chinese residue: 「{cn}」→ 「{en}」")
            reported.add(cn)

    return issues


def check_context_lock_terms(translated_path: Path, source_path: Path | None) -> list[str]:
    """Delegate context-lock term enforcement to term_enforcer.py.

    If no source file is provided, the check cannot run automatically.
    """
    if source_path is None:
        return []

    script = Path(__file__).parent / "term_enforcer.py"
    if not script.exists():
        return []

    result = subprocess.run(
        [sys.executable, str(script), str(translated_path), "--source", str(source_path), "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode == 0:
        return []

    try:
        parsed = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return []

    data = parsed.get("data", {})
    issues: list[str] = []
    for v in data.get("violations", []):
        msg = f"{v['issue_type']}: 「{v['term']}」expected 「{v['expected_cn']}」"
        if v.get("found_in_translation"):
            msg += f", found 「{v['found_in_translation']}」"
        issues.append(msg)
    return issues


def run_phase_c_check(
    text: str,
    direction: str,
    ref_dir: Path,
    translated_path: Path | None = None,
    source_path: Path | None = None,
) -> tuple[list[str], list[str]]:
    """Run Phase C rules against text.

    Args:
        text: Translated text content.
        direction: "encn" or "cnen".
        ref_dir: References directory.
        translated_path: Path to translated file (needed for term_enforcer).
        source_path: Path to source file (needed for term_enforcer).

    Returns:
        (automated_issues, manual_warnings)
    """
    rules = load_rules(ref_dir)
    automated_issues: list[str] = []
    manual_warnings: list[str] = []

    for rule in rules:
        rid = rule["id"]
        check_type = rule["check_type"]
        pattern = rule["pattern"]
        message = rule["issue_message"]

        # Filter by direction prefix.
        if direction == "encn" and not rid.startswith("encn-"):
            continue
        if direction == "cnen" and not rid.startswith("cnen-"):
            continue

        if check_type == "manual":
            manual_warnings.append(f"[{rid}] {rule['description']} — {message}")
            continue

        if check_type == "regex_forbidden":
            matches = check_regex_forbidden(text, pattern)
            for match in matches:
                issue = message.replace("{match}", match)
                automated_issues.append(f"[{rid}] {issue}")
            continue

        if check_type == "regex_required":
            if not check_regex_required(text, pattern):
                automated_issues.append(f"[{rid}] {message}")
            continue

        if check_type == "regex":
            # Informational / conditional checks are not treated as failures here.
            continue

        if check_type == "reference":
            if rid == "encn-05":
                for issue in check_english_residue(text, ref_dir):
                    automated_issues.append(f"[{rid}] {issue}")
            elif rid == "encn-06":
                for issue in check_ambiguous_names(text, ref_dir):
                    automated_issues.append(f"[{rid}] {issue}")
            elif rid == "encn-10":
                if translated_path and source_path:
                    for issue in check_context_lock_terms(translated_path, source_path):
                        automated_issues.append(f"[{rid}] {issue}")
                else:
                    manual_warnings.append(f"[{rid}] {rule['description']} — {message}")
            elif rid == "cnen-03":
                for issue in check_chinese_residue(text, ref_dir):
                    automated_issues.append(f"[{rid}] {issue}")
            continue

    return automated_issues, manual_warnings


def parse_issue(issue: str) -> dict[str, str]:
    """Parse an issue string like '[encn-01] message' into structured fields."""
    if issue.startswith("[") and "]" in issue:
        rule_id, message = issue.split("]", 1)
        return {"rule_id": rule_id[1:], "message": message.strip()}
    return {"rule_id": "unknown", "message": issue}


def parse_warning(warning: str) -> dict[str, str]:
    """Parse a warning string like '[encn-07] description — message'."""
    if warning.startswith("[") and "]" in warning:
        rule_id, rest = warning.split("]", 1)
        parts = rest.split("—", 1)
        return {
            "rule_id": rule_id[1:],
            "description": parts[0].strip(),
            "message": parts[1].strip() if len(parts) > 1 else "",
        }
    return {"rule_id": "unknown", "description": "", "message": warning}


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase C self-check runner")
    parser.add_argument("file", help="Translated file to check")
    parser.add_argument(
        "--direction",
        choices=["encn", "cnen"],
        help="Translation direction (auto-detected if omitted)",
    )
    parser.add_argument("--source", help="Source file for term authority check")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    args = parser.parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        if args.json:
            json_output(None, errors=[f"file not found: {args.file}"], exit_code=1)
        print(f"Error: file not found: {args.file}")
        sys.exit(1)

    text = file_path.read_text(encoding="utf-8")
    direction = args.direction or detect_direction(text)
    ref_dir = Path(__file__).parent.parent / "references"
    source_path = Path(args.source) if args.source else None

    automated_issues, manual_warnings = run_phase_c_check(
        text, direction, ref_dir, translated_path=file_path, source_path=source_path
    )

    if args.json:
        data = {
            "direction": direction,
            "automated_failed": len(automated_issues),
            "automated_issues": [parse_issue(i) for i in automated_issues],
            "manual_warning_count": len(manual_warnings),
            "manual_warnings": [parse_warning(w) for w in manual_warnings],
            "ready": len(automated_issues) == 0,
        }
        json_output(data, exit_code=1 if automated_issues else 0)

    print("=" * 60)
    print("PHASE C SELF-CHECK")
    print("=" * 60)
    print(f"File:      {file_path}")
    print(f"Direction: {'EN→CN' if direction == 'encn' else 'CN→EN'}")
    print()

    if automated_issues:
        print(f"[FAIL] {len(automated_issues)} automated check(s) failed:")
        print()
        for issue in automated_issues:
            print(f"  • {issue}")
        print()
    else:
        print("[PASS] All automated checks passed.")
        print()

    if manual_warnings:
        print(f"[INFO] {len(manual_warnings)} manual check(s) need review:")
        print()
        for warning in manual_warnings:
            print(f"  • {warning}")
        print()

    print("=" * 60)
    if automated_issues:
        print("[BLOCKED] Fix automated failures before finalizing.")
        sys.exit(1)
    else:
        print("[READY] Automated checks passed. Confirm manual items before finalizing.")
        sys.exit(0)


if __name__ == "__main__":
    main()
