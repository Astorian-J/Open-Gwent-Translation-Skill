#!/usr/bin/env python3
"""
Completeness Guard — Final gate before translation finalization.

Runs a subset of critical checks on the translated file.
If any check fails, outputs a BLOCKED message that MUST be
resolved before the translation can be finalized.

Usage:
    python completeness_guard.py translated.txt

Exit code:
    0 = PASS (translation ready)
    1 = BLOCKED (issues found, do not finalize)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import build_lock_from_source, detect_direction, json_output


def run_script_json(script_name: str, args: list[str]) -> tuple[bool, dict | None, str]:
    """Run a sub-script with --json and return (ok, parsed, raw_output)."""
    script = Path(__file__).parent / script_name
    if not script.exists():
        return False, None, f"{script_name} not found"

    result = subprocess.run(
        [sys.executable, str(script), *args, "--json"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout.strip()
    if result.stderr:
        output += "\n[stderr] " + result.stderr.strip()

    parsed = None
    if result.returncode in (0, 1):
        try:
            parsed = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            pass

    return result.returncode == 0, parsed, output


def run_check_translation(file_path: Path, lock_path: Path | None, direction: str, json_mode: bool) -> tuple[bool, int]:
    """Run check_translation.py and return (pass, issue_count)."""
    args = [str(file_path), "--direction", direction]
    if lock_path:
        args.extend(["--lock", str(lock_path)])

    if json_mode:
        ok, parsed, _ = run_script_json("check_translation.py", args)
        if parsed and "data" in parsed:
            return ok, parsed["data"].get("issue_count", 0)
        return ok, 0

    script = Path(__file__).parent / "check_translation.py"
    result = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout.strip()
    issue_count = 0
    if "Found" in output and "issue(s)" in output:
        try:
            issue_count = int(output.split("Found ")[1].split(" issue(s)")[0])
        except (IndexError, ValueError):
            pass
    return issue_count == 0 and result.returncode == 0, issue_count


def run_residue_scan(file_path: Path, direction: str, json_mode: bool) -> tuple[bool, int]:
    """Run auto_pipeline.py scan and return (pass, issue_count)."""
    if json_mode:
        ok, parsed, _ = run_script_json("auto_pipeline.py", ["scan", str(file_path), "--direction", direction])
        if parsed and "data" in parsed:
            return ok, parsed["data"].get("residue_count", 0)
        return ok, 0

    script = Path(__file__).parent / "auto_pipeline.py"
    result = subprocess.run(
        [sys.executable, str(script), "scan", str(file_path), "--direction", direction],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout.strip()
    # Count both English residue (EN->CN) and Chinese residue (CN->EN) lines.
    issue_count = sum(
        1 for line in output.split("\n")
        if "English residue:" in line or "Chinese residue:" in line
    )
    return issue_count == 0, issue_count


def run_phase_c_check(file_path: Path, lock_path: Path | None, direction: str, json_mode: bool) -> tuple[bool, int]:
    """Run phase_c_check.py and return (pass, issue_count)."""
    script = Path(__file__).parent / "phase_c_check.py"
    if not script.exists():
        return True, 0

    args = [str(file_path), "--direction", direction]
    if lock_path:
        args.extend(["--lock", str(lock_path)])

    if json_mode:
        ok, parsed, _ = run_script_json("phase_c_check.py", args)
        if parsed and "data" in parsed:
            return ok, parsed["data"].get("automated_failed", 0)
        return ok, 0

    result = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout.strip()
    issue_count = 0
    if "automated check(s) failed" in output:
        try:
            issue_count = int(output.split("automated check(s) failed")[0].strip().split()[-1])
        except (IndexError, ValueError):
            pass
    return issue_count == 0 and result.returncode == 0, issue_count


def run_term_authority_check(file_path: Path, lock_path: Path | None, direction: str, json_mode: bool) -> tuple[bool, int, str]:
    """Run term_enforcer.py and return (pass, violation_count, status).

    status is one of:
      "not_applicable" — CN->EN output; enforcing official CN terms does not apply
      "skipped"        — EN->CN but no lock file (or term_enforcer.py missing); not run
      "ran"            — actually executed; pass/count are meaningful
      "error"          — the check itself raised (set by the caller's except guard)
    """
    if direction == "cnen":
        return True, 0, "not_applicable"
    if lock_path is None:
        return True, 0, "skipped"

    script = Path(__file__).parent / "term_enforcer.py"
    if not script.exists():
        return True, 0, "skipped"

    if json_mode:
        ok, parsed, _ = run_script_json("term_enforcer.py", [str(file_path), "--lock", str(lock_path)])
        if parsed and "data" in parsed:
            return ok, parsed["data"].get("violation_count", 0), "ran"
        return ok, 0, "ran"

    result = subprocess.run(
        [sys.executable, str(script), str(file_path), "--lock", str(lock_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = result.stdout.strip()
    issue_count = 0
    if "Issues:" in output:
        try:
            issue_count = int(output.split("Issues:")[1].strip().split()[0])
        except (IndexError, ValueError):
            pass
    return issue_count == 0 and result.returncode == 0, issue_count, "ran"


def main() -> None:
    parser = argparse.ArgumentParser(description="Completeness Guard — Final gate before translation finalization")
    parser.add_argument("file", help="Translated file to check")
    parser.add_argument("--source", help="Source file for term authority enforcement")
    parser.add_argument("--direction", choices=["encn", "cnen"], help="Translation direction (auto-detected if omitted)")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    args = parser.parse_args()

    file_path = Path(args.file)
    source_path = Path(args.source) if args.source else None
    if not file_path.exists():
        if args.json:
            json_output(
                None,
                errors=[f"file not found: {args.file}"],
                exit_code=1,
            )
        print("=" * 60)
        print("COMPLETENESS GUARD")
        print("=" * 60)
        print("")
        print(f"[BLOCKED] File not found: {file_path}")
        print("")
        print("Save your translation to a file first, then re-run.")
        sys.exit(1)

    # Detect direction once and pass it to every downstream check so all of
    # them agree on which language is the target (and thus which residue to
    # flag). An explicit --direction overrides the heuristic.
    direction = args.direction or detect_direction(file_path.read_text(encoding="utf-8"))

    # Build the context lock once and reuse it for every downstream check,
    # instead of letting each sub-script rebuild it from the source.
    lock_path: Path | None = None
    if source_path:
        try:
            lock_path = build_lock_from_source(source_path)
        except Exception as e:
            print(f"[WARN] context lock build failed; term authority checks skipped: {e}")

    checks = []

    # Check 1: File exists
    if file_path.exists() and file_path.stat().st_size > 0:
        checks.append({"name": "file_exists", "passed": True, "issue_count": 0, "message": "File exists and is non-empty"})
    else:
        checks.append({"name": "file_exists", "passed": False, "issue_count": 0, "message": "File missing or empty"})

    residue_lang = "English" if direction == "encn" else "Chinese"

    # Check 2: Terminology check
    try:
        passed, count = run_check_translation(file_path, lock_path, direction, args.json)
        checks.append({"name": "terminology", "passed": passed, "issue_count": count, "message": "No terminology issues" if passed else f"Terminology: {count} issue(s)"})
    except Exception as e:
        checks.append({"name": "terminology", "passed": False, "issue_count": 0, "message": f"Terminology check failed: {e}"})

    # Check 3: Residue scan (English residue for EN->CN, Chinese residue for CN->EN)
    try:
        passed, count = run_residue_scan(file_path, direction, args.json)
        checks.append({"name": "residue_scan", "passed": passed, "issue_count": count, "message": f"No {residue_lang} residue" if passed else f"Residue: {count} untranslated card name(s)"})
    except Exception as e:
        checks.append({"name": "residue_scan", "passed": False, "issue_count": 0, "message": f"Residue scan failed: {e}"})

    # Check 4: Phase C self-check
    try:
        passed, count = run_phase_c_check(file_path, lock_path, direction, args.json)
        checks.append({"name": "phase_c", "passed": passed, "issue_count": count, "message": "Phase C checks passed" if passed else f"Phase C: {count} issue(s)"})
    except Exception as e:
        checks.append({"name": "phase_c", "passed": False, "issue_count": 0, "message": f"Phase C check failed: {e}"})

    # Check 5: Term authority enforcement (EN->CN only)
    try:
        passed, count, status = run_term_authority_check(file_path, lock_path, direction, args.json)
        if status == "not_applicable":
            msg = "Term authority: not applicable (CN->EN)"
        elif status == "skipped":
            msg = "Term authority: skipped (no lock file)"
        else:
            msg = "Term authority checks passed" if passed else f"Term authority: {count} violation(s)"
        checks.append({"name": "term_authority", "passed": passed, "issue_count": count, "status": status, "message": msg})
    except Exception as e:
        checks.append({"name": "term_authority", "passed": False, "issue_count": 0, "status": "error", "message": f"Term authority check failed: {e}"})

    if lock_path:
        lock_path.unlink(missing_ok=True)

    all_pass = all(c["passed"] for c in checks)

    if args.json:
        data = {
            "direction": direction,
            "all_passed": all_pass,
            "blocked": not all_pass,
            "checks": checks,
        }
        json_output(data, exit_code=0 if all_pass else 1)

    print("=" * 60)
    print("COMPLETENESS GUARD — FINAL CHECK")
    print("=" * 60)
    print("")
    print(f"File: {file_path}")
    print(f"Direction: {'EN->CN' if direction == 'encn' else 'CN->EN'}")
    print("")

    check_labels = [
        ("Checking file exists", checks[0]),
        ("Running terminology check", checks[1]),
        ("Running residue scan", checks[2]),
        ("Running Phase C self-check", checks[3]),
        ("Running term authority enforcement", checks[4]),
    ]

    for idx, (label, check) in enumerate(check_labels, start=1):
        print(f"[{idx}/5] {label:40} ", end="", flush=True)
        if check["passed"]:
            print("[PASS]")
        else:
            print(f"[WARN] {check['issue_count']} issue(s)")

    print("")
    print("=" * 60)

    if all_pass:
        print("[PASS] TRANSLATION READY")
        print("=" * 60)
        print("")
        print("All critical checks passed. You may finalize the translation.")
        sys.exit(0)
    else:
        print("[BLOCKED] DO NOT FINALIZE TRANSLATION")
        print("=" * 60)
        print("")
        print("Issues found:")
        for check in checks:
            if not check["passed"]:
                print(f"  • {check['message']}")
        print("")
        print("Fix all issues above, then re-run:")
        print(f"  python scripts/completeness_guard.py {file_path}")
        print("")
        print("[BLOCKED] Do not finalize the translation while BLOCKED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
