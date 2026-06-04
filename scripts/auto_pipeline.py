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
import subprocess
import sys
import tempfile
from pathlib import Path


def get_script_dir() -> Path:
    return Path(__file__).parent


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

    # Step 3: Terminology lookup summary
    lines.append("[3/3] Pre-translation summary")
    lines.append(f"    Source file: {source_path}")
    lines.append(f"    Skeleton:    {skeleton_file}")
    lines.append(f"    Lock table:  {lock_file}")
    lines.append("")
    lines.append("Next steps for the agent:")
    lines.append("    1. Read SKILL.md Step 1-4 for translation guidelines")
    lines.append("    2. Perform the translation")
    lines.append("    3. Save translation to a file (e.g., translated.txt)")
    lines.append("    4. Run: python auto_pipeline.py post source.md translated.txt")
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

    args = parser.parse_args()

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
