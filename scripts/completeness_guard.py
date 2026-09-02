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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (
    build_lock_from_source,
    detect_direction,
    format_issue,
    json_output,
    parse_ta_envelope,
    run_utf8,
    terms_summary,
)


def run_script_json(script_name: str, args: list[str]) -> tuple[bool, dict | None, str]:
    """Run a sub-script with --json and return (ok, parsed, raw_output)."""
    script = Path(__file__).parent / script_name
    if not script.exists():
        return False, None, f"{script_name} not found"

    result = run_utf8(
        [sys.executable, str(script), *args, "--json"],
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


def run_check_translation(file_path: Path, lock_path: Path | None, direction: str,
                          source_path: Path | None = None) -> tuple[bool, int, list]:
    """Run check_translation.py; return (pass, issue_count, structured issues).

    Always speaks --json to the sub-script and parses its envelope — no
    human-text scraping. Runs with --skip-ta: within the guard, term
    authority is executed ONCE by check 5 (this used to run it three times
    across checks 2/4/5); check_translation's own inline TA pass remains for
    standalone invocations. source_path is forwarded when the caller has it so
    the source-aware structural checks (protected tokens, bold-marker loss,
    completeness) can run — with --lock alone those checks are unreachable.
    A failed parse is fail-closed — (False, 0, []) regardless of exit code:
    a checker asked for --json that produced no parseable envelope can never
    fake a PASS here (same discipline as check 5's parse_ta_envelope).
    """
    args = [str(file_path), "--direction", direction, "--skip-ta"]
    if lock_path:
        args.extend(["--lock", str(lock_path)])
    if source_path:
        args.extend(["--source", str(source_path)])
    ok, parsed, _ = run_script_json("check_translation.py", args)
    if parsed and isinstance(parsed.get("data"), dict):
        d = parsed["data"]
        return ok, d.get("issue_count", 0), d.get("issues", []) or []
    return False, 0, []


def run_phase_c_check(file_path: Path, lock_path: Path | None, direction: str) -> tuple[bool, int, list]:
    """Run phase_c_check.py; return (pass, automated_failed, failed checks).

    Runs with --skip-ta: encn-10's term-enforcement is covered by the
    guard's single check-5 execution (see run_check_translation); without
    the flag, phase_c would spawn term_enforcer a second time.
    A failed parse is fail-closed — (False, 0, []) regardless of exit code,
    same discipline as run_check_translation and check 5's parse_ta_envelope.
    """
    script = Path(__file__).parent / "phase_c_check.py"
    if not script.exists():
        # Fail-closed: a missing sibling checker surfaces through the caller's
        # except guard as passed=False (same semantics as the M9 lock guard).
        raise FileNotFoundError(f"scripts/phase_c_check.py missing — check cannot run")

    args = [str(file_path), "--direction", direction, "--skip-ta"]
    if lock_path:
        args.extend(["--lock", str(lock_path)])
    ok, parsed, _ = run_script_json("phase_c_check.py", args)
    if parsed and isinstance(parsed.get("data"), dict):
        d = parsed["data"]
        return ok, d.get("automated_failed", 0), d.get("automated_issues", []) or []
    return False, 0, []


def run_term_authority_check(file_path: Path, lock_path: Path | None) -> tuple[bool, int, str, list[dict]]:
    """Run term_enforcer.py — the guard's SINGLE term-authority execution.

    check_translation and phase_c run with --skip-ta inside the guard (their
    own TA passes exist for standalone use); this check owns the one
    execution, and every consumer of term_enforcer output interprets the
    envelope through _shared.parse_ta_envelope so the fail-closed rules
    (value-not-key data check, degraded-warnings-count-as-violations) can
    never drift between checkers.

    status is one of:
      "skipped" — no lock file provided; not run
      "ran"     — actually executed; pass/count are meaningful
      "error"   — the check itself raised (set by the caller's except guard)

    Direction-aware since the lock carries the official target for both ways
    (term_enforcer.enforce_terms branches on the lock's direction).
    """
    if lock_path is None:
        return True, 0, "skipped", []

    script = Path(__file__).parent / "term_enforcer.py"
    if not script.exists():
        # Fail-closed: surfaces through the caller's except guard as
        # status="error" + passed=False (same semantics as the M9 lock guard).
        raise FileNotFoundError(f"scripts/term_enforcer.py missing — check cannot run")

    rc_ok, parsed, _raw = run_script_json("term_enforcer.py", [str(file_path), "--lock", str(lock_path)])
    ta_ok, count, violations, err = parse_ta_envelope(parsed)
    if err is not None:
        return False, count, "ran", [{
            "term": "[checker error]",
            "expected_official": "term_enforcer envelope unusable",
            "severity": "error",
            "offending_quote": err,
        }]
    # rc_ok in the conjunction restores defense in depth: today term_enforcer's
    # exit-code discipline (rc!=0 iff violations or degradation) makes this
    # redundant with the envelope check — but why rely on another script's
    # discipline staying perfect.
    return ta_ok and rc_ok, count, "ran", violations


def main() -> None:
    parser = argparse.ArgumentParser(description="Completeness Guard — Final gate before translation finalization")
    parser.add_argument("file", help="Translated file to check")
    parser.add_argument("--source", help="Source file to build the term lock from"
                        " (or pass --lock to reuse a prepare-time snapshot)")
    parser.add_argument("--lock", help="Pre-built context lock JSON (reuse, do not rebuild)")
    parser.add_argument("--direction", choices=["encn", "cnen"], help="Translation direction (auto-detected if omitted)")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    parser.add_argument("--verbose-terms", action="store_true", help="Emit full violation/term lists (default: counts + top 5)")
    parser.add_argument("--lite", action="store_true", help="Skip the Phase C style/format self-check (chat-length content): terminology + residue + term authority still gate")
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
    # flag). An explicit --direction overrides the heuristic. A read failure
    # (non-UTF-8 bytes, permissions) must not escape as a bare traceback —
    # report through the same channel as every other entry error.
    try:
        translated_text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        if args.json:
            json_output(None, errors=[f"cannot read file: {args.file} ({e})"], exit_code=1)
        print(f"Error: cannot read file: {args.file} ({e})")
        sys.exit(1)
    direction = args.direction or detect_direction(translated_text)

    # Build the context lock once and reuse it for every downstream check,
    # instead of letting each sub-script rebuild it from the source.
    lock_path: Path | None = None
    lock_build_error: str | None = None
    if args.lock:
        lock_path = Path(args.lock)
        if not lock_path.exists():
            # Fail-closed: an explicitly requested lock that is missing is an
            # error, never a silent fallback to rebuilding from --source.
            lock_build_error = f"--lock file not found: {args.lock}"
            lock_path = None
            print(f"[WARN] {lock_build_error}", file=sys.stderr)
    elif source_path:
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
    terminology_issues: list = []
    terminology_ok = False
    terminology_crashed = False
    try:
        terminology_ok, count, terminology_issues = run_check_translation(
            file_path, lock_path, direction, source_path=source_path
        )
        checks.append({"name": "terminology", "passed": terminology_ok, "issue_count": count, "issues": terms_summary(terminology_issues, args.verbose_terms), "message": "No terminology issues" if terminology_ok else f"Terminology: {count} issue(s)"})
    except Exception as e:
        terminology_crashed = True
        checks.append({"name": "terminology", "passed": False, "issue_count": 0, "issues": [], "message": f"Terminology check failed: {e}"})

    # Check 3: Residue (English residue for EN->CN, Chinese residue for CN->EN)
    # — derived from check 2's structured issues: check_translation already
    # runs the same residue detectors, so spawning auto_pipeline scan just
    # re-ran the whole checker to filter one category back out. "Found other
    # terminology issues" (terminology_ok False, list populated) is NOT a
    # crash — residue still derives from the issues check 2 did return.
    # ok=False with zero issues and an empty list means the checker's OUTPUT
    # was unusable (crash-degraded, or rc-0-but-not-JSON under the I2
    # fail-closed rule) — residue must not claim a green "No residue" over
    # output it never really parsed.
    terminology_unusable = (not terminology_crashed
                            and not terminology_ok
                            and count == 0
                            and not terminology_issues)
    if terminology_crashed:
        checks.append({"name": "residue_scan", "passed": False, "issue_count": 0, "issues": [], "message": "Residue not checked (terminology check crashed)"})
    elif terminology_unusable:
        checks.append({"name": "residue_scan", "passed": False, "issue_count": 0, "issues": [], "message": "Residue not checked (terminology check output unusable)"})
    else:
        residue_issues = [
            i for i in terminology_issues
            if isinstance(i, dict) and i.get("category") in ("english_residue", "chinese_residue")
        ]
        checks.append({"name": "residue_scan", "passed": not residue_issues, "issue_count": len(residue_issues), "issues": terms_summary(residue_issues, args.verbose_terms), "message": f"No {residue_lang} residue" if not residue_issues else f"Residue: {len(residue_issues)} untranslated card name(s)"})

    # Check 4: Phase C self-check (--lite skips it: sentence-style/format rules
    # are article-grade and misfire on chat-length content; the term gates above
    # are what a short translation actually needs).
    if args.lite:
        checks.append({"name": "phase_c", "passed": True, "issue_count": 0, "issues": [], "status": "skipped", "message": "Phase C skipped (--lite: chat-length content)"})
    else:
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

    # Only delete a lock WE built from --source; a caller's --lock snapshot
    # (prepare/finish binding) must survive for later finish re-runs.
    if lock_path and not args.lock:
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
