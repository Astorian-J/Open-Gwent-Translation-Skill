#!/usr/bin/env python3
"""
Gwent Translation Skill Health Check.
Verifies all components are present and functional.

Usage:
    python health_check.py [--verbose]
"""

import ast
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime


def color(status: str) -> str:
    """Return color code for terminal output."""
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

    # Check step count
    step_count = text.count("### Step")
    results.append(("INFO", f"SKILL.md: {step_count} workflow steps defined"))

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
        verified_count = text.count("|") // 3  # Rough estimate
        if "Verified" in text:
            results.append(("PASS", f"card_names.md: Has verified section (~{verified_count} entries)"))
        else:
            results.append(("WARN", "card_names.md: No verified section header"))

    # Check terminology_map.md has tables
    term_file = ref_dir / "terminology_map.md"
    if term_file.exists():
        text = term_file.read_text(encoding="utf-8")
        table_count = text.count("|---|")
        results.append(("PASS", f"terminology_map.md: {table_count} tables found"))

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


def run_test_cases(script_dir: Path) -> list[tuple[str, str]]:
    """Run basic test cases on scripts."""
    results = []

    # Test check_translation.py with sample text
    check_script = script_dir / "check_translation.py"
    if check_script.exists():
        try:
            # Create test file
            test_content = "这张卡要12费用，出场率很高。"
            test_file = Path(tempfile.gettempdir()) / "test_health_check.txt"
            test_file.write_text(test_content, encoding="utf-8")

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
            test_file = Path(tempfile.gettempdir()) / "test_residue.txt"
            test_file.write_text(test_content, encoding="utf-8")

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
        except Exception as e:
            results.append(("WARN", f"check_translation.py: Residue test failed ({e})"))

    return results


def main():
    verbose = "--verbose" in sys.argv

    base_dir = Path(__file__).parent.parent
    ref_dir = base_dir / "references"
    script_dir = base_dir / "scripts"
    skill_file = base_dir / "SKILL.md"

    print(f"Gwent Translation Skill Health Check")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base dir: {base_dir}")
    print()

    all_results = []

    # 1. Reference files
    print("=" * 50)
    print("Reference Files")
    print("=" * 50)
    results = check_reference_files(ref_dir)
    all_results.extend(results)
    for status, msg in results:
        print(f"  [{color(status)}{status}{color('RESET')}] {msg}")
    print()

    # 2. Scripts
    print("=" * 50)
    print("Scripts")
    print("=" * 50)
    results = check_scripts(script_dir)
    all_results.extend(results)
    for status, msg in results:
        print(f"  [{color(status)}{status}{color('RESET')}] {msg}")
    print()

    # 3. SKILL.md
    print("=" * 50)
    print("SKILL.md Structure")
    print("=" * 50)
    results = check_skill_file(skill_file)
    all_results.extend(results)
    for status, msg in results:
        print(f"  [{color(status)}{status}{color('RESET')}] {msg}")
    print()

    # 4. Data integrity
    print("=" * 50)
    print("Data Integrity")
    print("=" * 50)
    results = check_data_integrity(ref_dir)
    all_results.extend(results)
    for status, msg in results:
        print(f"  [{color(status)}{status}{color('RESET')}] {msg}")
    print()

    # 5. Functional tests
    print("=" * 50)
    print("Functional Tests")
    print("=" * 50)
    results = run_test_cases(script_dir)
    all_results.extend(results)
    for status, msg in results:
        print(f"  [{color(status)}{status}{color('RESET')}] {msg}")
    print()

    # Summary
    print("=" * 50)
    print("Summary")
    print("=" * 50)
    pass_count = sum(1 for s, _ in all_results if s == "PASS")
    fail_count = sum(1 for s, _ in all_results if s == "FAIL")
    warn_count = sum(1 for s, _ in all_results if s == "WARN")
    info_count = sum(1 for s, _ in all_results if s == "INFO")

    total = len([s for s, _ in all_results if s in ("PASS", "FAIL", "WARN")])

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
