#!/usr/bin/env python3
"""
Gwent Translation Auto-Pipeline.

ONE command to rule them all. Run this before and after translation
to ensure all preprocessing and postprocessing steps are executed.

Usage (Pre-translation):
    python auto_pipeline.py pre source.md --date 2026-05 --type meta

Usage (Post-translation, after you have translated.txt):
    python auto_pipeline.py post source.md translated.txt

This script chains all sub-scripts automatically so the agent
does not need to remember individual steps.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import json_output


# Scripts that already support --json in Phase 1.
JSON_CAPABLE_SCRIPTS = {
    "check_translation.py",
    "health_check.py",
    "phase_c_check.py",
    "learn.py",
    "context_lock.py",
    "format_skeleton.py",
}


def get_script_dir() -> Path:
    return Path(__file__).parent


def build_card_lookup_table(source_path: Path) -> list[tuple[str, str]]:
    """Build a quick reference table of card names found in the source text.

    Returns: list of (english_name, chinese_name) tuples.
    """
    from _shared import (
        extract_abbreviations,
        extract_capitalized_phrases,
        extract_card_names,
        extract_card_names_no_colon,
        extract_terms_from_markdown,
    )

    source_text = source_path.read_text(encoding="utf-8")

    # Extract candidate card names from source
    candidates = set()
    for name in extract_card_names(source_text):
        candidates.add(name.strip())
    for name in extract_card_names_no_colon(source_text, max_words=5, min_length=4):
        candidates.add(name.strip())
    for name in extract_terms_from_markdown(source_text):
        candidates.add(name.strip())
    for name in extract_capitalized_phrases(source_text, max_words=3, min_length=4):
        candidates.add(name.strip())

    if not candidates:
        return []

    # Load card_names.md and build EN -> CN mapping
    ref_dir = get_script_dir().parent / "references"
    card_file = ref_dir / "card_names.md"
    if not card_file.exists():
        return []

    card_map = {}
    text = card_file.read_text(encoding="utf-8")
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("|") and "---" not in line and "English" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4 and parts[1] and parts[2]:
                en = parts[1]
                cn = parts[2]
                if en not in ("English", "—", "") and cn not in ("Chinese", "—", ""):
                    card_map[en.lower()] = (en, cn)

    # Match candidates against card database
    results = []
    seen = set()
    for cand in sorted(candidates):
        key = cand.lower()
        if key in card_map:
            en, cn = card_map[key]
            if en.lower() not in seen:
                seen.add(en.lower())
                results.append((en, cn))
        else:
            # Partial match: collect ALL cards that contain or are contained by this candidate.
            # This surfaces ambiguous base names (e.g. "Geralt" matches all 6 variants).
            partial_hits = [
                (db_en, db_cn)
                for db_key, (db_en, db_cn) in card_map.items()
                if key in db_key or db_key in key
            ]
            for db_en, db_cn in partial_hits:
                if db_en.lower() not in seen:
                    seen.add(db_en.lower())
                    results.append((db_en, db_cn))

    return results


def run_script(name: str, args: list[str], json_mode: bool = False) -> tuple[bool, str, dict | None]:
    """Run a sub-script and return (success, output, parsed_json).

    If json_mode is True and the script is in JSON_CAPABLE_SCRIPTS, --json is
    appended and the stdout is parsed as JSON when possible.
    """
    script = get_script_dir() / name
    if not script.exists():
        return False, f"Script not found: {script}", None
    cmd = [sys.executable, str(script)] + args
    if json_mode and name in JSON_CAPABLE_SCRIPTS:
        cmd.append("--json")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired as e:
        output = e.stdout or ""
        if e.stderr:
            output += "\n[stderr] " + e.stderr
        output += "\n[timeout] Script exceeded 120s and was terminated."
        return False, output, None

    output = result.stdout
    if result.stderr:
        output += "\n[stderr] " + result.stderr

    parsed = None
    if json_mode and name in JSON_CAPABLE_SCRIPTS and result.stdout:
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass

    return result.returncode == 0, output, parsed


def pre_translation(source_path: Path, date: str | None, article_type: str, json_mode: bool = False) -> tuple[str | dict, bool]:
    """Run all preprocessing steps. Returns a report and overall success."""
    all_ok = True
    skeleton_file = Path(tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="gwent_skeleton_", delete=False
    ).name)
    lock_file = Path(tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="gwent_lock_", delete=False
    ).name)

    # Step 1: Format skeleton
    ok, out, _ = run_script(
        "format_skeleton.py",
        ["extract", str(source_path), "--output", str(skeleton_file)],
        json_mode=json_mode,
    )
    skeleton_extracted = ok
    if not ok:
        all_ok = False

    # Step 2: Context lock
    ok, out, _ = run_script(
        "context_lock.py",
        ["build", str(source_path), "--output", str(lock_file)],
        json_mode=json_mode,
    )
    lock_built = ok
    if not ok:
        all_ok = False

    # Step 3: Build card name quick reference table
    quick_ref = build_card_lookup_table(source_path)

    if json_mode:
        data = {
            "command": "pre",
            "source": str(source_path),
            "date": date or "auto",
            "type": article_type,
            "skeleton_extracted": skeleton_extracted,
            "skeleton_path": str(skeleton_file),
            "lock_built": lock_built,
            "lock_path": str(lock_file),
            "card_references_found": len(quick_ref),
            "card_references": [{"english": en, "chinese": cn} for en, cn in quick_ref],
        }
        return data, all_ok

    lines = [
        "=" * 60,
        "GWENT TRANSLATION PIPELINE — PRE-TRANSLATION",
        "=" * 60,
        "",
        f"Source: {source_path}",
        f"Date: {date or 'auto'}",
        f"Type: {article_type}",
        "",
    ]

    lines.append("[1/3] Extracting format skeleton...")
    if skeleton_extracted:
        lines.append(f"    [OK] Skeleton saved to: {skeleton_file}")
    else:
        lines.append(f"    [WARN] Format extraction skipped or failed: {out.strip()}")
    lines.append("")

    lines.append("[2/3] Building context lock...")
    if lock_built:
        lines.append(f"    [OK] Lock table saved to: {lock_file}")
        if "terms" in out:
            lines.append(f"    {out.strip()}")
    else:
        lines.append(f"    [WARN] Context lock skipped or failed: {out.strip()}")
    lines.append("")

    lines.append("[3/3] Building card name quick reference...")
    if quick_ref:
        lines.append(f"    [OK] Found {len(quick_ref)} card name(s) in source:")
        lines.append("")
        lines.append("    | English | Chinese |")
        lines.append("    |---------|---------|")
        for en, cn in quick_ref[:30]:
            lines.append(f"    | {en} | {cn} |")
        if len(quick_ref) > 30:
            lines.append(f"    | ... ({len(quick_ref) - 30} more) | ... |")
    else:
        lines.append("    [INFO] No card names detected in source")
    lines.append("")

    lines.append("-" * 50)
    lines.append("Pre-translation complete.")
    lines.append("")

    lines.append("=" * 60)
    lines.append("MANDATORY NEXT STEP — DO NOT SKIP")
    lines.append("")
    lines.append("1. Perform the translation using the quick reference above")
    lines.append("2. Save translation to a file (e.g., translated.txt)")
    lines.append("3. Run: python auto_pipeline.py post source.md translated.txt")
    lines.append("")
    lines.append("You must run 'post' after translation. Do not finalize")
    lines.append("the translation without running post first.")
    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines), all_ok


def post_translation(source_path: Path, translated_path: Path, json_mode: bool = False) -> tuple[str | dict, bool]:
    """Run all postprocessing steps. Returns a report and overall success."""
    all_ok = True

    # Step 1: Check terminology
    check_ok, check_out, check_parsed = run_script(
        "check_translation.py",
        [str(translated_path)],
        json_mode=json_mode,
    )
    if not check_ok:
        all_ok = False
    terminology_issue_count = check_parsed.get("data", {}).get("issue_count", 0) if check_parsed else 0

    # Step 2: Diff review (if user provided their own translation — not applicable here)
    # Skip auto diff-review; only run if explicitly requested

    # Step 3: Learn new terms
    learn_ok, learn_out, learn_parsed = run_script(
        "learn.py",
        [str(source_path), str(translated_path), "--auto"],
        json_mode=json_mode,
    )
    if not learn_ok:
        all_ok = False
    if learn_parsed and "data" in learn_parsed:
        new_terms_learned = learn_parsed["data"].get("added_to_pending", 0)
    else:
        new_terms_learned = 0
        if "Discovered" in learn_out and "potential new term" in learn_out:
            try:
                new_terms_learned = int(learn_out.split("Discovered ")[1].split(" potential new term")[0])
            except (IndexError, ValueError):
                pass

    # Step 4: Health check
    health_ok, health_out, _ = run_script(
        "health_check.py",
        [],
        json_mode=json_mode,
    )
    if not health_ok:
        all_ok = False
    health_check_passed = health_ok

    if json_mode:
        data = {
            "command": "post",
            "source": str(source_path),
            "translated": str(translated_path),
            "terminology_issue_count": terminology_issue_count,
            "new_terms_learned": new_terms_learned,
            "health_check_passed": health_check_passed,
        }
        return data, all_ok

    lines = [
        "=" * 60,
        "GWENT TRANSLATION PIPELINE — POST-TRANSLATION",
        "=" * 60,
        "",
        f"Source:      {source_path}",
        f"Translated:  {translated_path}",
        "",
    ]

    lines.append("[1/3] Running terminology check...")
    lines.append(check_out)
    lines.append("")

    lines.append("[2/3] Learning new terms...")
    lines.append(learn_out)
    lines.append("")

    lines.append("[3/3] Skill health check...")
    for line in health_out.split("\n"):
        if "PASS" in line or "FAIL" in line or "All checks" in line:
            lines.append(line)
    lines.append("")

    lines.append("=" * 60)
    lines.append("MANDATORY NEXT STEP — DO NOT SKIP")
    lines.append("")
    lines.append("Run: python scripts/completeness_guard.py")
    lines.append("")
    lines.append("You must run the guard BEFORE finalizing the translation.")
    lines.append("Do not ignore guard output.")
    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines), all_ok


def scan_translation(translated_path: Path, json_mode: bool = False) -> tuple[str | dict, bool]:
    """Standalone scan mode: check a translated file for English residue.

    This is the final defense line after translation. It scans the translated
    text for any remaining English card names and reports them with suggested
    Chinese translations.
    """
    ok, out, parsed = run_script(
        "check_translation.py",
        [str(translated_path)],
        json_mode=json_mode,
    )

    residues = []
    if parsed and parsed.get("data"):
        for issue in parsed["data"].get("issues", []):
            if issue.get("category") == "english_residue":
                residues.append(issue)
    else:
        # Fallback for non-JSON mode or parse failure.
        residues = [
            {"message": line}
            for line in out.split("\n")
            if "English residue" in line
        ]

    if json_mode:
        data = {
            "command": "scan",
            "translated": str(translated_path),
            "english_residue_count": len(residues),
            "residues": residues,
        }
        return data, len(residues) == 0

    lines = [
        "=" * 60,
        "GWENT TRANSLATION — ENGLISH RESIDUE SCAN",
        "=" * 60,
        "",
        f"File: {translated_path}",
        "",
    ]

    if residues:
        lines.append(f"[WARN] Found {len(residues)} English residue(s):")
        lines.append("")
        for issue in residues:
            lines.append(f"  {issue.get('message', issue)}")
        lines.append("")
        lines.append("-" * 50)
        lines.append("Action required: Replace the above English card names")
        lines.append("with their Chinese translations before finalizing.")
        lines.append("")
        lines.append("[BLOCKED] After fixing, re-run: python auto_pipeline.py scan translated.txt")
    else:
        lines.append("[PASS] No English residue found. Translation is clean.")
        lines.append("")
        lines.append("If you have not yet run post-processing:")
        lines.append("  python auto_pipeline.py post source.md translated.txt")

    lines.append("")
    return "\n".join(lines), len(residues) == 0


def main():
    parser = argparse.ArgumentParser(description="Gwent Translation Auto-Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pre = subparsers.add_parser("pre", help="Pre-translation preprocessing")
    pre.add_argument("source", help="Source file to translate")
    pre.add_argument("--date", help="Article date (YYYY-MM)")
    pre.add_argument("--type", choices=["meta", "bc-proposal", "card-analysis", "patch-notes", "general"],
                     default="general", help="Article type")
    pre.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")

    post = subparsers.add_parser("post", help="Post-translation checks")
    post.add_argument("source", help="Original source file")
    post.add_argument("translated", help="Translated file")
    post.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")

    scan = subparsers.add_parser("scan", help="Scan translated file for English residue")
    scan.add_argument("translated", help="Translated file to scan")
    scan.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")

    args = parser.parse_args()
    json_mode = args.json

    if args.command == "scan":
        translated_path = Path(args.translated)
        if not translated_path.exists():
            if json_mode:
                json_output(None, errors=[f"Translated file not found: {args.translated}"], exit_code=1)
            print(f"Error: Translated file not found: {args.translated}")
            sys.exit(1)
        report, ok = scan_translation(translated_path, json_mode=json_mode)
        if json_mode:
            json_output(report, exit_code=0 if ok else 1)
        print(report)
        sys.exit(0 if ok else 1)

    source_path = Path(args.source)
    if not source_path.exists():
        if json_mode:
            json_output(None, errors=[f"Source file not found: {args.source}"], exit_code=1)
        print(f"Error: Source file not found: {args.source}")
        sys.exit(1)

    if args.command == "pre":
        report, ok = pre_translation(source_path, args.date, args.type, json_mode=json_mode)
        if json_mode:
            json_output(report, exit_code=0 if ok else 1)
        print(report)
        sys.exit(0 if ok else 1)
    elif args.command == "post":
        translated_path = Path(args.translated)
        if not translated_path.exists():
            if json_mode:
                json_output(None, errors=[f"Translated file not found: {args.translated}"], exit_code=1)
            print(f"Error: Translated file not found: {args.translated}")
            sys.exit(1)
        report, ok = post_translation(source_path, translated_path, json_mode=json_mode)
        if json_mode:
            json_output(report, exit_code=0 if ok else 1)
        print(report)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
