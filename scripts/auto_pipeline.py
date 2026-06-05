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
import re
import subprocess
import sys
import tempfile
from pathlib import Path


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
    for cand in sorted(candidates):
        key = cand.lower()
        if key in card_map:
            results.append(card_map[key])
        else:
            # Try partial match (e.g., "Geralt" matches "Geralt: Igni")
            for db_key, (db_en, db_cn) in card_map.items():
                if key in db_key or db_key in key:
                    if (db_en, db_cn) not in results:
                        results.append((db_en, db_cn))
                    break

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for en, cn in results:
        if en.lower() not in seen:
            seen.add(en.lower())
            unique.append((en, cn))

    return unique


def run_script(name: str, args: list[str]) -> tuple[bool, str]:
    """Run a sub-script and return (success, output)."""
    script = get_script_dir() / name
    if not script.exists():
        return False, f"Script not found: {script}"
    cmd = [sys.executable, str(script)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    output = result.stdout
    if result.stderr:
        output += "\n[stderr] " + result.stderr
    return result.returncode == 0, output


def pre_translation(source_path: Path, date: str | None, article_type: str) -> str:
    """Run all preprocessing steps. Returns a report for the agent."""
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

    # Step 1: Format skeleton
    lines.append("[1/3] Extracting format skeleton...")
    skeleton_file = Path(tempfile.gettempdir()) / "skeleton.json"
    ok, out = run_script("format_skeleton.py", ["extract", str(source_path), "--output", str(skeleton_file)])
    if ok:
        lines.append(f"    ✓ Skeleton saved to: {skeleton_file}")
    else:
        lines.append(f"    ⚠ Format extraction skipped or failed: {out.strip()}")
    lines.append("")

    # Step 2: Context lock
    lines.append("[2/3] Building context lock...")
    lock_file = Path(tempfile.gettempdir()) / "lock.json"
    ok, out = run_script("context_lock.py", ["build", str(source_path), "--output", str(lock_file)])
    if ok:
        lines.append(f"    ✓ Lock table saved to: {lock_file}")
        # Show candidate terms count
        if "terms" in out:
            lines.append(f"    {out.strip()}")
    else:
        lines.append(f"    ⚠ Context lock skipped or failed: {out.strip()}")
    lines.append("")

    # Step 3: Build card name quick reference table
    lines.append("[3/3] Building card name quick reference...")
    quick_ref = build_card_lookup_table(source_path)
    if quick_ref:
        lines.append(f"    ✓ Found {len(quick_ref)} card name(s) in source:")
        lines.append("")
        lines.append("    | English | Chinese |")
        lines.append("    |---------|---------|")
        for en, cn in quick_ref[:30]:
            lines.append(f"    | {en} | {cn} |")
        if len(quick_ref) > 30:
            lines.append(f"    | ... ({len(quick_ref) - 30} more) | ... |")
    else:
        lines.append("    ℹ No card names detected in source")
    lines.append("")

    # Summary
    lines.append("-" * 50)
    lines.append("Pre-translation complete. Next steps for the agent:")
    lines.append("    1. Read SKILL.md Step 1-4 for translation guidelines")
    lines.append("    2. Use the card name quick reference table above")
    lines.append("    3. Perform the translation")
    lines.append("    4. Save translation to a file (e.g., translated.txt)")
    lines.append("    5. Run: python auto_pipeline.py post source.md translated.txt")
    lines.append("")

    return "\n".join(lines)


def post_translation(source_path: Path, translated_path: Path) -> str:
    """Run all postprocessing steps. Returns a report for the agent."""
    lines = [
        "=" * 60,
        "GWENT TRANSLATION PIPELINE — POST-TRANSLATION",
        "=" * 60,
        "",
        f"Source:      {source_path}",
        f"Translated:  {translated_path}",
        "",
    ]

    # Step 1: Check terminology
    lines.append("[1/3] Running terminology check...")
    ok, out = run_script("check_translation.py", [str(translated_path)])
    lines.append(out)
    lines.append("")

    # Step 2: Diff review (if user provided their own translation — not applicable here)
    # Skip auto diff-review; only run if explicitly requested

    # Step 3: Learn new terms
    lines.append("[2/3] Learning new terms...")
    ok, out = run_script("learn.py", [str(source_path), str(translated_path), "--auto"])
    lines.append(out)
    lines.append("")

    # Step 4: Health check
    lines.append("[3/3] Skill health check...")
    ok, out = run_script("health_check.py", [])
    # Only show summary
    for line in out.split("\n"):
        if "PASS" in line or "FAIL" in line or "All checks" in line:
            lines.append(line)
    lines.append("")

    return "\n".join(lines)


def scan_translation(translated_path: Path) -> str:
    """Standalone scan mode: check a translated file for English residue.

    This is the final defense line after translation. It scans the translated
    text for any remaining English card names and reports them with suggested
    Chinese translations.
    """
    lines = [
        "=" * 60,
        "GWENT TRANSLATION — ENGLISH RESIDUE SCAN",
        "=" * 60,
        "",
        f"File: {translated_path}",
        "",
    ]

    # Import directly to avoid subprocess overhead and get structured data
    sys.path.insert(0, str(get_script_dir()))
    from check_translation import check_english_residue

    text = translated_path.read_text(encoding="utf-8")
    issues = check_english_residue(text)

    if issues:
        lines.append(f"⚠️  Found {len(issues)} English residue(s):")
        lines.append("")
        for issue in issues:
            lines.append(f"  - {issue}")
        lines.append("")
        lines.append("-" * 50)
        lines.append("Action required: Replace the above English card names")
        lines.append("with their Chinese translations before delivery.")
    else:
        lines.append("✅ No English residue found. Translation is clean.")

    lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Gwent Translation Auto-Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pre = subparsers.add_parser("pre", help="Pre-translation preprocessing")
    pre.add_argument("source", help="Source file to translate")
    pre.add_argument("--date", help="Article date (YYYY-MM)")
    pre.add_argument("--type", choices=["meta", "bc-proposal", "card-analysis", "patch-notes", "general"],
                     default="general", help="Article type")

    post = subparsers.add_parser("post", help="Post-translation checks")
    post.add_argument("source", help="Original source file")
    post.add_argument("translated", help="Translated file")

    scan = subparsers.add_parser("scan", help="Scan translated file for English residue")
    scan.add_argument("translated", help="Translated file to scan")

    args = parser.parse_args()

    if args.command == "scan":
        translated_path = Path(args.translated)
        if not translated_path.exists():
            print(f"Error: Translated file not found: {args.translated}")
            sys.exit(1)
        report = scan_translation(translated_path)
        print(report)
        sys.exit(0)

    source_path = Path(args.source)
    if not source_path.exists():
        print(f"Error: Source file not found: {args.source}")
        sys.exit(1)

    if args.command == "pre":
        report = pre_translation(source_path, args.date, args.type)
        print(report)
    elif args.command == "post":
        translated_path = Path(args.translated)
        if not translated_path.exists():
            print(f"Error: Translated file not found: {args.translated}")
            sys.exit(1)
        report = post_translation(source_path, translated_path)
        print(report)


if __name__ == "__main__":
    main()
