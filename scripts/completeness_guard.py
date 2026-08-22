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
from _shared import build_lock_from_source, detect_direction, format_issue, json_output, terms_summary


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


def run_check_translation(file_path: Path, lock_path: Path | None, direction: str) -> tuple[bool, int, list]:
    """Run check_translation.py; return (pass, issue_count, structured issues).

    Always speaks --json to the sub-script and parses its envelope — no
    human-text scraping. A failed parse degrades to (ok, 0, []): counts read
    0 but `passed` still carries the sub-script's exit code, so a broken
    checker can never fake a PASS here (the caller's except guard and the
    finish-level status checks back this up).
    """
    args = [str(file_path), "--direction", direction]
    if lock_path:
        args.extend(["--lock", str(lock_path)])
    ok, parsed, _ = run_script_json("check_translation.py", args)
    if parsed and isinstance(parsed.get("data"), dict):
        d = parsed["data"]
        return ok, d.get("issue_count", 0), d.get("issues", []) or []
    return ok, 0, []


def run_residue_scan(file_path: Path, direction: str) -> tuple[bool, int, list]:
    """Run auto_pipeline.py scan; return (pass, residue_count, residue items)."""
    script = Path(__file__).parent / "auto_pipeline.py"
    if not script.exists():
        # Fail-closed: a missing sibling checker surfaces through the caller's
        # except guard as passed=False (same semantics as the M9 lock guard).
        raise FileNotFoundError(f"scripts/auto_pipeline.py missing — check cannot run")

    ok, parsed, _ = run_script_json("auto_pipeline.py", ["scan", str(file_path), "--direction", direction])
    if parsed and isinstance(parsed.get("data"), dict):
        d = parsed["data"]
        return ok, d.get("residue_count", 0), d.get("residues", []) or []
    return ok, 0, []


def run_phase_c_check(file_path: Path, lock_path: Path | None, direction: str) -> tuple[bool, int, list]:
    """Run phase_c_check.py; return (pass, automated_failed, failed checks)."""
    script = Path(__file__).parent / "phase_c_check.py"
    if not script.exists():
        # Fail-closed: a missing sibling checker surfaces through the caller's
        # except guard as passed=False (same semantics as the M9 lock guard).
        raise FileNotFoundError(f"scripts/phase_c_check.py missing — check cannot run")

    args = [str(file_path), "--direction", direction]
    if lock_path:
        args.extend(["--lock", str(lock_path)])
    ok, parsed, _ = run_script_json("phase_c_check.py", args)
    if parsed and isinstance(parsed.get("data"), dict):
        d = parsed["data"]
        return ok, d.get("automated_failed", 0), d.get("automated_issues", []) or []
    return ok, 0, []


def run_term_authority_check(file_path: Path, lock_path: Path | None) -> tuple[bool, int, str, list[dict]]:
    """Run term_enforcer.py and return (pass, violation_count, status, violations).

    status is one of:
      "skipped" — no lock file provided; not run
      "ran"     — actually executed; pass/count are meaningful
      "error"   — the check itself raised (set by the caller's except guard)

    Direction-aware since the lock carries the official target for both ways:
    EN->CN asserts the official Chinese appears in the Chinese translation;
    CN->EN asserts the official English appears in the English translation
    (term_enforcer.enforce_terms branches on the lock's direction).

    violations: the per-term violation dicts, each carrying term /
    expected_official / severity / offending_quote so a BLOCKED report is
    agent-actionable.
    """
    if lock_path is None:
        return True, 0, "skipped", []

    script = Path(__file__).parent / "term_enforcer.py"
    if not script.exists():
        # Fail-closed: surfaces through the caller's except guard as
        # status="error" + passed=False (same semantics as the M9 lock guard).
        raise FileNotFoundError(f"scripts/term_enforcer.py missing — check cannot run")

    ok, parsed, _ = run_script_json("term_enforcer.py", [str(file_path), "--lock", str(lock_path)])
    if parsed and isinstance(parsed.get("data"), dict):
        data = parsed["data"]
        # Degradation can flip a BLOCKED into a false PASS — surface each
        # notice as a counted violation-like entry so it blocks the gate.
        degraded = data.get("warnings", [])
        violations = data.get("violations", [])
        for w in degraded:
            violations.append({
                "term": "[checker warning]",
                "expected_official": "term_enforcer degraded",
                "severity": "error",
                "offending_quote": w,
            })
        count = data.get("violation_count", 0) + len(degraded)
        return ok and not degraded, count, "ran", violations
    return ok, 0, "ran", []


def main() -> None:
    parser = argparse.ArgumentParser(description="Completeness Guard — Final gate before translation finalization")
    parser.add_argument("file", help="Translated file to check")
    parser.add_argument("--source", help="Source file for term authority enforcement")
    parser.add_argument("--direction", choices=["encn", "cnen"], help="Translation direction (auto-detected if omitted)")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    parser.add_argument("--verbose-terms", action="store_true", help="Emit full violation/term lists (default: counts + top 5)")
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
    lock_build_error: str | None = None
    if source_path:
        try:
            lock_path = build_lock_from_source(source_path)
        except Exception as e:
            lock_build_error = str(e)
            # Diagnostic, not report data — stderr keeps stdout pure JSON.
            print(f"[WARN] context lock build failed: {e}", file=sys.stderr)

    checks = []

    # Check 1: File exists
    if file_path.exists() and file_path.stat().st_size > 0:
        checks.append({"name": "file_exists", "passed": True, "issue_count": 0, "message": "File exists and is non-empty"})
    else:
        checks.append({"name": "file_exists", "passed": False, "issue_count": 0, "message": "File missing or empty"})

    residue_lang = "English" if direction == "encn" else "Chinese"

    # Check 2: Terminology check
    try:
        passed, count, issues = run_check_translation(file_path, lock_path, direction)
        checks.append({"name": "terminology", "passed": passed, "issue_count": count, "issues": terms_summary(issues, args.verbose_terms), "message": "No terminology issues" if passed else f"Terminology: {count} issue(s)"})
    except Exception as e:
        checks.append({"name": "terminology", "passed": False, "issue_count": 0, "issues": [], "message": f"Terminology check failed: {e}"})

    # Check 3: Residue scan (English residue for EN->CN, Chinese residue for CN->EN)
    try:
        passed, count, residues = run_residue_scan(file_path, direction)
        checks.append({"name": "residue_scan", "passed": passed, "issue_count": count, "issues": terms_summary(residues, args.verbose_terms), "message": f"No {residue_lang} residue" if passed else f"Residue: {count} untranslated card name(s)"})
    except Exception as e:
        checks.append({"name": "residue_scan", "passed": False, "issue_count": 0, "issues": [], "message": f"Residue scan failed: {e}"})

    # Check 4: Phase C self-check
    try:
        passed, count, failed_items = run_phase_c_check(file_path, lock_path, direction)
        checks.append({"name": "phase_c", "passed": passed, "issue_count": count, "issues": terms_summary(failed_items, args.verbose_terms), "message": "Phase C checks passed" if passed else f"Phase C: {count} issue(s)"})
    except Exception as e:
        checks.append({"name": "phase_c", "passed": False, "issue_count": 0, "issues": [], "message": f"Phase C check failed: {e}"})

    # Check 5: Term authority enforcement (both directions)
    if lock_build_error is not None:
        # --source was given but the lock could not be built: the TA check
        # should have run and could not — fail closed, never a fake PASS.
        # (No --source at all stays "skipped" -> passed, by design.)
        checks.append({"name": "term_authority", "passed": False, "issue_count": 0, "status": "error", "violations": [], "message": f"Term authority: context lock build failed ({lock_build_error}); check could not run"})
    else:
        try:
            passed, count, status, ta_violations = run_term_authority_check(file_path, lock_path)
            if status == "skipped":
                msg = "Term authority: skipped (no lock file)"
            else:
                msg = "Term authority checks passed" if passed else f"Term authority: {count} violation(s)"
            checks.append({"name": "term_authority", "passed": passed, "issue_count": count, "status": status, "violations": terms_summary(ta_violations, args.verbose_terms), "message": msg})
        except Exception as e:
            checks.append({"name": "term_authority", "passed": False, "issue_count": 0, "status": "error", "violations": [], "message": f"Term authority check failed: {e}"})

    if lock_path:
        lock_path.unlink(missing_ok=True)

    all_pass = all(c["passed"] for c in checks)

    if args.json:
        data = {
            "direction": direction,
            "direction_auto_detected": args.direction is None,
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
                for issue in (check.get("issues", []) or []) + (check.get("violations", []) or []):
                    print(f"      - {format_issue(issue)}")
        print("")
        print("Fix all issues above, then re-run the gate via translate.py:")
        print(f"  python scripts/translate.py finish {file_path} --source <source.md> --direction {direction}")
        print("")
        print("[BLOCKED] Do not finalize the translation while BLOCKED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
