#!/usr/bin/env python3
"""
Gwent Translation Workflow Orchestrator.
Chains all scripts into a single workflow.

Usage:
    python translate.py source.md --date 2026-05 --type bc-proposal --output result.md
    python translate.py source.md --user-translation user.txt --output report.md
    python translate.py source.md --check-only
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime


def get_script_dir():
    return Path(__file__).parent


def run_command(cmd, desc):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout
        if result.stderr:
            output += ("\n" + result.stderr if output else result.stderr)
        if result.returncode == 0 or result.stdout:
            return True, output
        else:
            return False, result.stderr or "No output"
    except subprocess.TimeoutExpired as e:
        return False, f"Timeout: {e}"
    except subprocess.CalledProcessError as e:
        return False, f"Command failed: {e}"
    except OSError as e:
        return False, f"OS error: {e}"


def step_0_context(args):
    lines = ["=" * 60, "Step 0: Context Setup", "=" * 60, ""]

    VERSION_YEAR_BASE = 2020
    VERSION_YEAR_EXTENDED = 2021

    date = args.date or datetime.now().strftime("%Y-%m")
    year = int(date.split("-")[0])

    if year < VERSION_YEAR_BASE:
        version_range = "Base game only (11xxxx-16xxxx)"
    elif year < VERSION_YEAR_EXTENDED:
        version_range = "Base + 200xxx + 201xxx + 202xxx"
    else:
        version_range = "All cards including 203xxx"

    lines.extend([
        f"Article date: {date}",
        f"Article type: {args.type or 'general'}",
        f"Card version range: {version_range}",
        f"Source file: {args.input}",
        "",
    ])

    return lines


def step_1_format_extract(source_path):
    lines = ["=" * 60, "Step 1: Format Skeleton", "=" * 60, ""]

    text = source_path.read_text(encoding="utf-8")
    has_markdown = any(c in text for c in ["#", "|", ">", "-", "*"])

    if not has_markdown:
        lines.append("Source appears to be plain text. No skeleton extraction needed.")
        lines.append("")
        return lines, None

    script = get_script_dir() / "format_skeleton.py"
    if not script.exists():
        lines.append("WARNING: format_skeleton.py not found, skipping format extraction")
        lines.append("")
        return lines, None

    skeleton_file = Path(tempfile.gettempdir()) / "skeleton.json"
    success, output = run_command(
        [sys.executable, str(script), "extract", str(source_path), "--output", str(skeleton_file)],
        "Format extraction"
    )

    if success:
        lines.append(f"Format skeleton extracted to: {skeleton_file}")
    else:
        lines.append(f"Format extraction failed: {output}")

    lines.append("")
    return lines, skeleton_file if success else None


def step_2_context_lock(source_path):
    lines = ["=" * 60, "Step 2: Context Lock", "=" * 60, ""]

    script = get_script_dir() / "context_lock.py"
    if not script.exists():
        lines.append("WARNING: context_lock.py not found, skipping context lock")
        lines.append("")
        return lines, None

    lock_file = Path(tempfile.gettempdir()) / "lock.json"
    success, output = run_command(
        [sys.executable, str(script), "build", str(source_path), "--output", str(lock_file)],
        "Context lock build"
    )

    if success:
        lines.extend(output.split("\n"))
        lines.append(f"Lock file: {lock_file}")
    else:
        lines.append(f"Context lock failed: {output}")

    lines.append("")
    return lines, lock_file if success else None


def step_3_translation():
    return [
        "=" * 60, "Step 3: Translation", "=" * 60, "",
        "Translate the source text using SKILL.md guidelines.",
        "Checklist:",
        "  - Load all references from Step 1",
        "  - Apply context lock terms consistently",
        "  - Preserve format skeleton structure",
        "  - Follow style fingerprint preferences",
        "",
        "Save translation to a file, then run --check-only to verify.",
        "",
    ]


def step_4_check(translated_path):
    lines = ["=" * 60, "Step 4: Terminology Check", "=" * 60, ""]

    script = get_script_dir() / "check_translation.py"
    if not script.exists():
        lines.append("WARNING: check_translation.py not found")
        lines.append("")
        return lines

    success, output = run_command(
        [sys.executable, str(script), str(translated_path)],
        "Terminology check"
    )
    lines.append(output)
    lines.append("")
    return lines


def step_5_diff_review(source_path, user_translation):
    lines = ["=" * 60, "Step 5: Diff Review", "=" * 60, ""]

    script = get_script_dir() / "diff_review.py"
    if not script.exists():
        lines.append("WARNING: diff_review.py not found")
        lines.append("")
        return lines

    report_file = Path(tempfile.gettempdir()) / "diff_report.md"
    success, output = run_command(
        [sys.executable, str(script), str(source_path), str(user_translation),
         "--output", str(report_file)],
        "Diff review"
    )

    if success:
        lines.append(f"Diff report: {report_file}")
    else:
        lines.append(f"Diff review failed: {output}")

    lines.append("")
    return lines


def step_6_learn(source_path, translated_path):
    lines = ["=" * 60, "Step 6: Learn", "=" * 60, ""]

    script = get_script_dir() / "learn.py"
    if not script.exists():
        lines.append("WARNING: learn.py not found")
        lines.append("")
        return lines

    success, output = run_command(
        [sys.executable, str(script), str(source_path), str(translated_path)],
        "Learn new terms"
    )
    lines.append(output)
    lines.append("")
    return lines


def main():
    parser = argparse.ArgumentParser(description="Gwent Translation Workflow")
    parser.add_argument("input", help="Source file to translate")
    parser.add_argument("--date", help="Article date (YYYY-MM)")
    parser.add_argument("--type", choices=["meta", "bc-proposal", "card-analysis", "patch-notes", "general"],
                        default="general", help="Article type")
    parser.add_argument("--user-translation", help="User's translation file (for diff review)")
    parser.add_argument("--check-only", action="store_true", help="Only run checks on translated file")
    parser.add_argument("--output", "-o", help="Output report file")

    args = parser.parse_args()

    source_path = Path(args.input)
    if not source_path.exists():
        print(f"Error: Source file not found: {args.input}")
        sys.exit(1)

    all_lines = []
    all_lines.extend(step_0_context(args))

    if args.check_only:
        translated_path = Path(args.user_translation) if args.user_translation else source_path
        if args.user_translation and not translated_path.exists():
            print(f"Error: User translation file not found: {args.user_translation}")
            sys.exit(1)
        all_lines.extend(step_4_check(translated_path))
        if args.user_translation:
            all_lines.extend(step_5_diff_review(source_path, translated_path))
        all_lines.extend(step_6_learn(source_path, translated_path))
    else:
        format_lines, _ = step_1_format_extract(source_path)
        all_lines.extend(format_lines)

        lock_lines, _ = step_2_context_lock(source_path)
        all_lines.extend(lock_lines)

        all_lines.extend(step_3_translation())

        print("\n".join(all_lines))
        print()
        print("=" * 60)
        print("Workflow prepared. Next steps:")
        print("=" * 60)
        print()
        print("1. Translate the source text")
        print("2. Save to a file (e.g., translated.txt)")
        print(f"3. Run: python {get_script_dir() / 'check_translation.py'} translated.txt")
        print()
        print("4. For diff review:")
        print(f"   python {get_script_dir() / 'diff_review.py'} {args.input} reference.txt")
        print()
        print("5. After finalizing:")
        print(f"   python {get_script_dir() / 'learn.py'} {args.input} translated.txt --auto")
        print()

        output_path = Path(args.output) if args.output else None
        if output_path:
            output_path.write_text("\n".join(all_lines), encoding="utf-8")
            print(f"Setup report saved to: {output_path}")
        return

    output_path = Path(args.output) if args.output else None
    if output_path:
        output_path.write_text("\n".join(all_lines), encoding="utf-8")
        print(f"\nReport saved to: {output_path}")
    print("\n".join(all_lines))


if __name__ == "__main__":
    main()
