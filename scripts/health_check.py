#!/usr/bin/env python3
"""
Gwent Translation Skill Health Check.
Verifies all components are present and functional.

Usage:
    python health_check.py [--verbose]
"""

import ast
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from _shared import json_output, parse_markdown_table


_no_color = False


def color(status: str) -> str:
    """Return color code for terminal output."""
    if _no_color or not sys.stdout.isatty():
        return ""
    colors = {
        "PASS": "\033[32m",   # Green
        "FAIL": "\033[31m",   # Red
        "WARN": "\033[33m",   # Yellow
        "INFO": "\033[36m",   # Cyan
        "RESET": "\033[0m",
    }
    return colors.get(status, "")


def check_file_exists(path: Path, desc: str) -> tuple[str, str]:
    """Check if a file exists."""
    if path.exists():
        return "PASS", f"{desc}: {path.name}"
    else:
        return "FAIL", f"{desc}: {path.name} (missing)"


def check_reference_files(ref_dir: Path) -> list[tuple[str, str]]:
    """Check all reference files."""
    results = []

    required_refs = [
        ("correction_guide.md", "Correction rules"),
        ("style_reference.md", "Style examples"),
        ("terminology_map.md", "Terminology map"),
        ("reverse_terminology_map.md", "Reverse terminology map (CN→EN)"),
        ("keywords_map.md", "Keyword translations"),
        ("card_names.md", "Card name mappings"),
        ("ambiguous_names.md", "Ambiguous names"),
        ("competitive_terms.md", "Competitive terms"),
        ("common_pitfalls.md", "Common pitfalls"),
        ("category_map.md", "Category map"),
        ("version_map.md", "Version map"),
        ("style_fingerprint.md", "Style fingerprint"),
        ("cn_fuzzy_fixes.md", "Chinese fuzzy fixes"),
        ("pending_terms.md", "Pending terms buffer"),
        ("changelog.md", "Changelog"),
        ("phase_c_checklist.md", "Phase C checklist"),
    ]

    for fname, desc in required_refs:
        status, msg = check_file_exists(ref_dir / fname, desc)
        results.append((status, msg))

    return results


def check_scripts(script_dir: Path) -> list[tuple[str, str]]:
    """Check all script files."""
    results = []

    required_scripts = [
        ("check_translation.py", "Terminology checker"),
        ("learn.py", "Learning system"),
        ("context_lock.py", "Context lock"),
        ("format_skeleton.py", "Format skeleton"),
        ("diff_review.py", "Diff review"),
        ("backtranslate.py", "Back-translation"),
        ("term_enforcer.py", "Term authority enforcer"),
        ("auto_pipeline.py", "Auto pipeline"),
        ("completeness_guard.py", "Completeness guard"),
        ("phase_c_check.py", "Phase C checker"),
    ]

    for fname, desc in required_scripts:
        fpath = script_dir / fname
        status, msg = check_file_exists(fpath, desc)

        if status == "PASS":
            # Check syntax without executing to avoid side effects
            try:
                ast.parse(fpath.read_text(encoding="utf-8"))
                results.append(("PASS", f"{desc}: {fname} (syntax OK)"))
            except SyntaxError as e:
                results.append(("FAIL", f"{desc}: {fname} (syntax error: {e})"))
        else:
            results.append((status, msg))

    return results


def check_skill_file(skill_path: Path) -> list[tuple[str, str]]:
    """Check SKILL.md structure."""
    results = []

    if not skill_path.exists():
        results.append(("FAIL", "SKILL.md: missing"))
        return results

    text = skill_path.read_text(encoding="utf-8")

    # Check required sections
    required_sections = [
        "## Overview",
        "## When to Use",
        "## Translation Workflow",
        "## Quick Reference",
    ]

    for section in required_sections:
        if section in text:
            results.append(("PASS", f"SKILL.md: Contains {section}"))
        else:
            results.append(("FAIL", f"SKILL.md: Missing {section}"))

    # Check for workflow phases (SKILL.md uses Phase A/B/C/D/E)
    phase_count = text.count("### Phase")
    results.append(("INFO", f"SKILL.md: {phase_count} workflow phases defined"))

    # Check for special modes
    if "Diff Review Mode" in text:
        results.append(("PASS", "SKILL.md: Diff Review Mode documented"))
    if "Back-Translation" in text:
        results.append(("PASS", "SKILL.md: Back-Translation documented"))

    return results


def check_data_integrity(ref_dir: Path) -> list[tuple[str, str]]:
    """Check data integrity in reference files."""
    results = []

    # Check card_names.md has verified section
    card_file = ref_dir / "card_names.md"
    if card_file.exists():
        text = card_file.read_text(encoding="utf-8")
        verified_count = sum(
            1 for line in text.split("\n")
            if line.strip().startswith("|")
            and "---" not in line
            and "English" not in line
            and len([p for p in line.split("|") if p.strip()]) >= 2
        )
        if "Verified" in text:
            results.append(("PASS", f"card_names.md: Has verified section ({verified_count} entries)"))
        else:
            results.append(("WARN", "card_names.md: No verified section header"))

    # Check terminology_map.md has tables
    term_file = ref_dir / "terminology_map.md"
    if term_file.exists():
        text = term_file.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=2)
        table_count = len(rows)
        results.append(("PASS", f"terminology_map.md: {table_count} rows found"))

    # Check pending_terms.md is not too large
    pending_file = ref_dir / "pending_terms.md"
    if pending_file.exists():
        lines = pending_file.read_text(encoding="utf-8").split("\n")
        pending_count = sum(1 for l in lines if l.startswith("### "))
        results.append(("INFO", f"pending_terms.md: {pending_count} terms pending review"))

    # Check changelog has entries
    changelog = ref_dir / "changelog.md"
    if changelog.exists():
        text = changelog.read_text(encoding="utf-8")
        version_count = text.count("## ")
        results.append(("INFO", f"changelog.md: {version_count} versions recorded"))

    return results


def check_phase_c_checklist(ref_dir: Path) -> list[tuple[str, str]]:
    """Validate phase_c_checklist.md structure and regex patterns."""
    results = []
    checklist = ref_dir / "phase_c_checklist.md"
    if not checklist.exists():
        results.append(("FAIL", "phase_c_checklist.md: missing"))
        return results

    text = checklist.read_text(encoding="utf-8")
    rows = parse_markdown_table(text, min_columns=5)
    if not rows:
        results.append(("WARN", "phase_c_checklist.md: no rule rows parsed"))
        return results

    required_keys = {"id", "description", "check_type", "pattern", "issue_message"}
    regex_types = {"regex", "regex_forbidden", "regex_required"}
    seen_ids: set[str] = set()
    regex_ok_count = 0
    regex_fail_count = 0

    for idx, row in enumerate(rows, start=1):
        missing = required_keys - set(row.keys())
        if missing:
            results.append((
                "FAIL",
                f"phase_c_checklist.md row {idx}: missing columns {', '.join(sorted(missing))}",
            ))
            continue

        rid = row.get("id", "").strip()
        if not rid:
            results.append(("FAIL", f"phase_c_checklist.md row {idx}: empty rule ID"))
            continue
        if rid in seen_ids:
            results.append(("FAIL", f"phase_c_checklist.md: duplicate rule ID '{rid}'"))
        seen_ids.add(rid)

        check_type = row.get("check_type", "").strip().lower()
        if check_type not in {
            "regex",
            "regex_forbidden",
            "regex_required",
            "reference",
            "manual",
        }:
            results.append((
                "WARN",
                f"phase_c_checklist.md: rule '{rid}' has unknown check_type '{check_type}'",
            ))

        pattern = row.get("pattern", "").strip()
        if check_type in regex_types:
            raw = pattern.strip("`")
            raw = raw.replace("\\|", "|")
            if not raw:
                results.append((
                    "FAIL",
                    f"phase_c_checklist.md: rule '{rid}' has empty regex pattern",
                ))
                regex_fail_count += 1
                continue
            try:
                re.compile(raw)
                regex_ok_count += 1
            except re.error as e:
                results.append((
                    "FAIL",
                    f"phase_c_checklist.md: rule '{rid}' invalid regex: {e}",
                ))
                regex_fail_count += 1

    results.append((
        "INFO",
        f"phase_c_checklist.md: {len(rows)} rules, {regex_ok_count} valid regex patterns",
    ))
    if regex_fail_count == 0 and len(seen_ids) == len(rows):
        results.append(("PASS", "phase_c_checklist.md: structure and regex patterns valid"))

    return results


def run_test_cases(script_dir: Path) -> list[tuple[str, str]]:
    """Run basic test cases on scripts."""
    results = []

    # Test check_translation.py with sample text
    check_script = script_dir / "check_translation.py"
    if check_script.exists():
        try:
            # Create test file
            test_content = "这张卡要12费用，出场率很高。"
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", encoding="utf-8", delete=False
            ) as tf:
                tf.write(test_content)
                test_file = Path(tf.name)
            try:
                result = subprocess.run(
                    [sys.executable, str(check_script), str(test_file)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0 and "forbidden term" in result.stdout:
                    results.append(("PASS", "check_translation.py: Detects errors correctly"))
                else:
                    results.append(("WARN", "check_translation.py: Unexpected test result"))
            finally:
                test_file.unlink(missing_ok=True)
        except Exception as e:
            results.append(("WARN", f"check_translation.py: Test failed ({e})"))

    # Test learn.py with sample text
    learn_script = script_dir / "learn.py"
    if learn_script.exists():
        try:
            # Syntax check via ast.parse (no execution, avoids side effects)
            ast.parse(learn_script.read_text(encoding="utf-8"))
            results.append(("PASS", "learn.py: Syntax OK"))
        except SyntaxError as e:
            results.append(("FAIL", f"learn.py: Syntax error ({e})"))
        except Exception as e:
            results.append(("WARN", f"learn.py: Test failed ({e})"))

    # Test English residue detection
    check_script = script_dir / "check_translation.py"
    if check_script.exists():
        try:
            test_content = "这张卡很强。Geralt 和 Ciri 都可以带。"
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", encoding="utf-8", delete=False
            ) as tf:
                tf.write(test_content)
                test_file = Path(tf.name)
            try:
                result = subprocess.run(
                    [sys.executable, str(check_script), str(test_file)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if "English residue" in result.stdout:
                    results.append(("PASS", "check_translation.py: English residue detection works"))
                else:
                    results.append(("WARN", "check_translation.py: English residue not detected in test"))
            finally:
                test_file.unlink(missing_ok=True)
        except Exception as e:
            results.append(("WARN", f"check_translation.py: Residue test failed ({e})"))

    return results


def main():
    parser = argparse.ArgumentParser(description="Gwent Translation Skill Health Check")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color codes in output")
    args = parser.parse_args()

    global _no_color
    _no_color = args.no_color or os.environ.get("NO_COLOR", "").strip() != ""

    base_dir = Path(__file__).parent.parent
    ref_dir = base_dir / "references"
    script_dir = base_dir / "scripts"
    skill_file = base_dir / "SKILL.md"

    all_results = []

    def run_section(name: str, func) -> list[tuple[str, str]]:
        results = func()
        all_results.extend(results)
        return results

    ref_results = run_section("Reference Files", lambda: check_reference_files(ref_dir))
    script_results = run_section("Scripts", lambda: check_scripts(script_dir))
    skill_results = run_section("SKILL.md Structure", lambda: check_skill_file(skill_file))
    data_results = run_section("Data Integrity", lambda: check_data_integrity(ref_dir))
    phase_c_results = run_section("Phase C Checklist", lambda: check_phase_c_checklist(ref_dir))
    test_results = run_section("Functional Tests", lambda: run_test_cases(script_dir))

    pass_count = sum(1 for s, _ in all_results if s == "PASS")
    fail_count = sum(1 for s, _ in all_results if s == "FAIL")
    warn_count = sum(1 for s, _ in all_results if s == "WARN")
    info_count = sum(1 for s, _ in all_results if s == "INFO")

    if args.json:
        data = {
            "pass_count": pass_count,
            "fail_count": fail_count,
            "warn_count": warn_count,
            "info_count": info_count,
            "results": [
                {"status": status, "message": msg}
                for status, msg in all_results
            ],
        }
        json_output(data, exit_code=1 if fail_count > 0 else 0)

    print(f"Gwent Translation Skill Health Check")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base dir: {base_dir}")
    print()

    sections = [
        ("Reference Files", ref_results),
        ("Scripts", script_results),
        ("SKILL.md Structure", skill_results),
        ("Data Integrity", data_results),
        ("Phase C Checklist", phase_c_results),
        ("Functional Tests", test_results),
    ]

    for name, results in sections:
        print("=" * 50)
        print(name)
        print("=" * 50)
        for status, msg in results:
            print(f"  [{color(status)}{status}{color('RESET')}] {msg}")
        print()

    # Summary
    print("=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"  PASS: {pass_count}")
    if fail_count:
        print(f"  {color('FAIL')}FAIL{color('RESET')}: {fail_count}")
    if warn_count:
        print(f"  {color('WARN')}WARN{color('RESET')}: {warn_count}")
    if info_count:
        print(f"  INFO: {info_count}")
    print()

    if fail_count == 0:
        print(f"  {color('PASS')}All checks passed!{color('RESET')}")
    else:
        print(f"  {color('FAIL')}{fail_count} critical issue(s) found{color('RESET')}")

    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    main()
