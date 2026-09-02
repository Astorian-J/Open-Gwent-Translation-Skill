#!/usr/bin/env python3
"""
Context Lock (上下文一致性锁).
Maintains a per-document terminology lock table to ensure consistency.

Usage:
    # Build lock table from source text
    python context_lock.py build source_en.txt --output lock.json

    # Check translation against lock table
    python context_lock.py check translation.txt --lock lock.json

    # Add a new term to the lock table
    python context_lock.py add "English Term" "中文翻译" --lock lock.json

Lock table format:
    {
        "document": "article_slug",
        "terms": {
            "English Term": {
                "cn": "中文翻译",
                "first_seen": "paragraph_3",
                "locked_at": "2026-06-03T14:30:00"
            }
        }
    }
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (
    json_output,
    source_is_chinese,
    TermAuthority,
)
from term_enforcer import enforce_terms

# --output/--lock defaults anchor to the script directory, not the caller's
# cwd, so running from elsewhere never drops lock.json into a random folder.
_DEFAULT_LOCK = str(Path(__file__).resolve().parent / "lock.json")


def load_lock(lock_file: str) -> dict:
    """Load or create a lock table."""
    path = Path(lock_file)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"document": "", "terms": {}}


def save_lock(lock: dict, lock_file: str) -> None:
    """Save lock table to file."""
    Path(lock_file).write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")


def build_lock(source_file: str, lock_file: str) -> dict:
    """Build a new lock table from source text.

    Direction-aware: a Chinese source (CN->EN article) is extracted with the
    Chinese dictionary lookup (TermAuthority.get_all_for_text_cn); an English
    source (EN->CN article) keeps the existing English regex extraction. Source
    language is detected via source_is_chinese (reusing detect_direction), so
    the EN->CN path is unchanged. Official translations are pre-filled from
    TermAuthority when available; unknown terms remain pending.
    """
    source_text = Path(source_file).read_text(encoding="utf-8")
    ref_dir = Path(__file__).parent.parent / "references"
    authority = TermAuthority(ref_dir)
    source_cn = source_is_chinese(source_text)

    lock = {
        "document": Path(source_file).stem,
        "created_at": datetime.now().isoformat(),
        "direction": "cnen" if source_cn else "encn",
        "terms": {}
    }

    resolved_iter = (
        authority.get_all_for_text_cn(source_text) if source_cn
        else authority.get_all_for_text(source_text)
    )

    for resolved in resolved_iter:
        term = resolved["term"]
        if resolved["match_type"] in ("ambiguous_base", "cn_collision"):
            lock["terms"][term] = {
                "canonical_en": resolved.get("canonical_en") or term,
                "cn": resolved.get("cn", ""),
                "status": "ambiguous",
                "first_seen": "auto-detected",
                "source_ref": resolved["source"],
                "type": resolved["type"],
                "variants": resolved.get("candidates") or resolved.get("variants", []),
            }
        elif resolved["cn"]:
            lock["terms"][term] = {
                "canonical_en": resolved["canonical_en"],
                "cn": resolved["cn"],
                "status": "auto_locked",
                "first_seen": "auto-detected",
                "source_ref": resolved["source"],
                "type": resolved["type"],
                "aliases": resolved.get("aliases", []),
                "abbrevs": resolved.get("abbrevs", []),
            }
        else:
            lock["terms"][term] = {
                "cn": "",
                "status": "pending",
                "first_seen": "auto-detected"
            }

    save_lock(lock, lock_file)
    return lock


def check_translation(translation_file: str, lock_file: str) -> dict:
    """Check translation against lock table for consistency violations.

    Delegates to term_enforcer.enforce_terms so word-boundary matching, the
    CJK suppress guard (希里 inside 冒牌希里), and direction handling live in
    exactly one place; this function only maps the result onto this command's
    report shape (term/expected/issue per violation).
    """
    lock = load_lock(lock_file)
    enforced = enforce_terms(Path(translation_file), lock)
    is_cnen = enforced.get("direction") == "cnen"

    # issue_type -> the human-readable message this command prints.
    issue_labels = {
        "term_left_untranslated": (
            "Chinese term left untranslated" if is_cnen
            else "English term left untranslated"
        ),
        "term_missing_or_literal": "Locked term missing from translation",
        "ambiguous_not_disambiguated": "Ambiguous name not disambiguated in translation",
    }
    violations = [
        {
            "term": v["term"],
            "expected": v.get("expected_official") or v.get("expected_en") or v.get("expected_cn", ""),
            "issue": issue_labels.get(v["issue_type"], v["issue_type"]),
        }
        for v in enforced["violations"]
    ]
    # Degradation notices (e.g. CJK suppress built incompletely) can flip a
    # BLOCKED into a false PASS — surface them as violations, not hints.
    for warning in enforced.get("warnings", []):
        violations.append({"term": "(checker)", "expected": "", "issue": warning})

    confirmed_count = len([
        t for t in lock['terms'].values()
        if t.get('status') in ("confirmed", "auto_locked")
    ])
    pending = [
        (en, info) for en, info in lock["terms"].items()
        if info.get("status") not in ("confirmed", "auto_locked")
    ]

    return {
        "lock_file": lock_file,
        "confirmed_count": confirmed_count,
        # pass_count 也计入已正确消歧的 ambiguous 项；旧实现只数 auto_locked/
        # confirmed，此处口径略宽但更如实（消歧成功=译文中确实用了锁定译名）。
        "found_in_translation": enforced["pass_count"],
        "violation_count": len(violations),
        "violations": violations,
        "pending_count": len(pending),
        "pending_terms": [en for en, _ in pending],
    }


def add_term(en_term: str, cn_term: str, lock_file: str) -> dict:
    """Add or update a term in the lock table."""
    lock = load_lock(lock_file)

    lock["terms"][en_term] = {
        "cn": cn_term,
        "status": "confirmed",
        "locked_at": datetime.now().isoformat()
    }

    save_lock(lock, lock_file)
    return {"term": en_term, "translation": cn_term, "lock_file": lock_file}


def main():
    parser = argparse.ArgumentParser(description="Context Lock — per-document terminology consistency")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build lock table from source text")
    build.add_argument("source", help="Source file")
    build.add_argument("--output", default=_DEFAULT_LOCK, help="Output lock file")
    build.add_argument("--json", action="store_true", help="Output structured JSON")

    check = subparsers.add_parser("check", help="Check translation against lock table")
    check.add_argument("translation", help="Translated file")
    check.add_argument("--lock", default=_DEFAULT_LOCK, help="Lock file")
    check.add_argument("--json", action="store_true", help="Output structured JSON")

    add = subparsers.add_parser("add", help="Add a term to the lock table")
    add.add_argument("en_term", help="English term")
    add.add_argument("cn_term", help="Chinese translation")
    add.add_argument("--lock", default=_DEFAULT_LOCK, help="Lock file")
    add.add_argument("--json", action="store_true", help="Output structured JSON")

    args = parser.parse_args()

    if args.command == "build":
        source_path = Path(args.source)
        if not source_path.exists():
            if args.json:
                json_output(None, errors=[f"source file not found: {args.source}"], exit_code=1)
            print(f"Error: source file not found: {args.source}")
            sys.exit(1)
        lock = build_lock(args.source, args.output)
        term_count = len(lock["terms"])
        if args.json:
            json_output({
                "lock_file": args.output,
                "term_count": term_count,
                "document": lock["document"],
            }, exit_code=0)
        print(f"Built lock table with {term_count} terms")
        print(f"Save to: {args.output}")
        print()
        print("Next steps:")
        print("1. Translate the text, looking up terms in references/")
        print("2. As you decide each translation, update the lock table:")
        print(f'   python context_lock.py add "Term" "翻译" --lock {args.output}')
        print("3. For subsequent paragraphs, check against the lock:")
        print(f'   python context_lock.py check translated.txt --lock {args.output}')

    elif args.command == "check":
        translation_path = Path(args.translation)
        if not translation_path.exists():
            if args.json:
                json_output(None, errors=[f"translation file not found: {args.translation}"], exit_code=1)
            print(f"Error: translation file not found: {args.translation}")
            sys.exit(1)
        # Fail-closed on a missing lock: an absent lock loads as empty
        # (load_lock's create-on-missing semantics exists for `add`), and an
        # empty lock checks NOTHING yet would report "No consistency
        # violations found." — a silent PASS. Refuse instead.
        lock_path = Path(args.lock)
        if not lock_path.exists():
            if args.json:
                json_output(None, errors=[f"lock file not found: {args.lock}"], exit_code=1)
            print(f"Error: lock file not found: {args.lock}")
            print(f"Build one first: python context_lock.py build <source> --output {args.lock}")
            sys.exit(1)
        result = check_translation(args.translation, args.lock)
        if args.json:
            json_output(result, exit_code=1 if result["violation_count"] > 0 else 0)
        print(f"# Context Lock Check")
        print()
        print(f"Lock file: {result['lock_file']}")
        print(f"Confirmed terms in lock: {result['confirmed_count']}")
        print(f"Terms found in translation: {result['found_in_translation']}")
        print()
        if result["violations"]:
            print("## Violations")
            print()
            for v in result["violations"]:
                print(f"- **{v['term']}**: {v['issue']}")
                print(f"  Expected: 「{v['expected']}」")
            print()
        else:
            print("No consistency violations found.")
            print()
        if result["pending_terms"]:
            print(f"## Pending terms ({result['pending_count']})")
            print()
            for en in result["pending_terms"]:
                print(f"- {en}")
            print()
            print("Confirm with: python context_lock.py add \"Term\" \"翻译\" --lock", args.lock)

    elif args.command == "add":
        result = add_term(args.en_term, args.cn_term, args.lock)
        if args.json:
            json_output(result, exit_code=0)
        print(f"Locked: 「{result['term']}」→ 「{result['translation']}」")


if __name__ == "__main__":
    main()
