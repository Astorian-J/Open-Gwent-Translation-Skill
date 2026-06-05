#!/usr/bin/env python3
"""
Completeness Guard — Final gate before translation delivery.

Runs a subset of critical checks on the translated file.
If any check fails, outputs a BLOCKED message that MUST be
resolved before the translation can be delivered to the user.

Usage:
    python completeness_guard.py translated.txt

Exit code:
    0 = PASS (translation ready)
    1 = BLOCKED (issues found, do not deliver)
"""

import subprocess
import sys
from pathlib import Path


def run_check_translation(file_path: Path) -> tuple[bool, str, int]:
    """Run check_translation.py and return (pass, output, issue_count)."""
    script = Path(__file__).parent / "check_translation.py"
    result = subprocess.run(
        [sys.executable, str(script), str(file_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout.strip()
    if result.stderr:
        output += "\n[stderr] " + result.stderr.strip()

    # Parse issue count from output
    issue_count = 0
    if "Found" in output and "issue(s)" in output:
        try:
            issue_count = int(output.split("Found ")[1].split(" issue(s)")[0])
        except (IndexError, ValueError):
            pass

    passed = issue_count == 0 and result.returncode == 0
    return passed, output, issue_count


def run_residue_scan(file_path: Path) -> tuple[bool, str, int]:
    """Run auto_pipeline.py scan and return (pass, output, issue_count)."""
    script = Path(__file__).parent / "auto_pipeline.py"
    result = subprocess.run(
        [sys.executable, str(script), "scan", str(file_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout.strip()
    if result.stderr:
        output += "\n[stderr] " + result.stderr.strip()

    # Count English residue lines
    issue_count = output.count("English residue:")
    passed = issue_count == 0
    return passed, output, issue_count


def print_banner(text: str, char: str = "=") -> None:
    """Print a centered banner."""
    width = 60
    padding = (width - len(text) - 2) // 2
    line = char * padding + " " + text + " " + char * padding
    if len(line) < width:
        line += char
    print(line)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python completeness_guard.py <translated_file>")
        print("")
        print("This script is the FINAL GATE before translation delivery.")
        print("Run it AFTER auto_pipeline.py post.")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print("=" * 60)
        print("COMPLETENESS GUARD")
        print("=" * 60)
        print("")
        print(f"❌ BLOCKED: File not found: {file_path}")
        print("")
        print("Save your translation to a file first, then re-run.")
        sys.exit(1)

    print("=" * 60)
    print("COMPLETENESS GUARD — FINAL DELIVERY CHECK")
    print("=" * 60)
    print("")
    print(f"File: {file_path}")
    print("")

    checks = []

    # Check 1: File exists
    print("[1/3] Checking file exists...           ", end="", flush=True)
    if file_path.exists() and file_path.stat().st_size > 0:
        print("✅")
        checks.append((True, "File exists and is non-empty"))
    else:
        print("❌")
        checks.append((False, "File missing or empty"))

    # Check 2: Terminology check
    print("[2/3] Running terminology check...      ", end="", flush=True)
    try:
        passed, out, count = run_check_translation(file_path)
        if passed:
            print("✅")
            checks.append((True, "No terminology issues"))
        else:
            print(f"⚠️  {count} issue(s)")
            checks.append((False, f"Terminology: {count} issue(s)"))
    except Exception as e:
        print(f"❌ Error ({e})")
        checks.append((False, f"Terminology check failed: {e}"))

    # Check 3: English residue scan
    print("[3/3] Running English residue scan...   ", end="", flush=True)
    try:
        passed, out, count = run_residue_scan(file_path)
        if passed:
            print("✅")
            checks.append((True, "No English residue"))
        else:
            print(f"⚠️  {count} residue(s)")
            checks.append((False, f"Residue: {count} untranslated card name(s)"))
    except Exception as e:
        print(f"❌ Error ({e})")
        checks.append((False, f"Residue scan failed: {e}"))

    # Determine overall status
    all_pass = all(passed for passed, _ in checks)

    print("")
    print("=" * 60)

    if all_pass:
        print("✅ PASS — TRANSLATION READY FOR DELIVERY")
        print("=" * 60)
        print("")
        print("All critical checks passed. You may present the translation to the user.")
        sys.exit(0)
    else:
        print("❌ BLOCKED — DO NOT DELIVER TRANSLATION")
        print("=" * 60)
        print("")
        print("Issues found:")
        for passed, msg in checks:
            if not passed:
                print(f"  • {msg}")
        print("")
        print("Fix all issues above, then re-run:")
        print(f"  python scripts/completeness_guard.py {file_path}")
        print("")
        print("🔴 Do NOT deliver the translation to the user while BLOCKED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
