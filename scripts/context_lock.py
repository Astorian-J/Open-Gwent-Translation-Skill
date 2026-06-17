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
    extract_abbreviations,
    extract_capitalized_phrases,
    extract_card_names,
    extract_card_names_no_colon,
    extract_terms_from_markdown,
    json_output,
    TermAuthority,
)


def load_lock(lock_file: str) -> dict:
    """Load or create a lock table."""
    path = Path(lock_file)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"document": "", "terms": {}}


def save_lock(lock: dict, lock_file: str) -> None:
    """Save lock table to file."""
    Path(lock_file).write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")


def extract_terms_from_source(source_text: str) -> dict[str, str]:
    """Extract candidate terms from English source that need locking."""
    terms = {}

    # Card names with colons (e.g., "Geralt: Igni")
    for name in extract_card_names(source_text):
        terms[name] = ""

    # Card names without colons (e.g., "Paulie Dahlberg", "Horst Borsodi")
    for name in extract_card_names_no_colon(source_text, max_words=5, min_length=4):
        terms[name] = ""

    # Terms from Markdown headers and bold text (often missed by paragraph scanners)
    for name in extract_terms_from_markdown(source_text):
        terms[name] = ""

    # Capitalized phrases (potential card names / abilities)
    for name in extract_capitalized_phrases(source_text, max_words=3, min_length=4):
        terms[name] = ""

    # Abbreviations
    for abbrev in extract_abbreviations(source_text):
        terms[abbrev] = ""

    return terms


def build_lock(source_file: str, lock_file: str) -> dict:
    """Build a new lock table from source text.

    Official translations are pre-filled from TermAuthority when available.
    Unknown terms remain pending for manual resolution.
    """
    source_text = Path(source_file).read_text(encoding="utf-8")
    ref_dir = Path(__file__).parent.parent / "references"
    authority = TermAuthority(ref_dir)

    lock = {
        "document": Path(source_file).stem,
        "created_at": datetime.now().isoformat(),
        "terms": {}
    }

    for resolved in authority.get_all_for_text(source_text):
        term = resolved["term"]
        if resolved["match_type"] == "ambiguous_base":
            lock["terms"][term] = {
                "canonical_en": resolved["canonical_en"],
                "cn": "",
                "status": "ambiguous",
                "first_seen": "auto-detected",
                "source_ref": resolved["source"],
                "type": resolved["type"],
                "variants": resolved.get("variants", []),
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
    """Check translation against lock table for consistency violations."""
    lock = load_lock(lock_file)
    translation = Path(translation_file).read_text(encoding="utf-8")

    violations = []
    confirmed = []

    for en_term, info in lock["terms"].items():
        cn_term = info.get("cn", "")
        status = info.get("status", "pending")
        variants = info.get("variants", [])

        if status == "ambiguous" and variants:
            variant_cns = [v["cn"] for v in variants if v.get("cn")]
            found = any(vcn in translation for vcn in variant_cns)
            if found:
                confirmed.append(en_term)
            else:
                expected = " / ".join(variant_cns)
                violations.append({
                    "term": en_term,
                    "expected": expected,
                    "issue": "Ambiguous name not disambiguated in translation"
                })
            continue

        if status not in ("confirmed", "auto_locked") or not cn_term:
            continue

        # Check if any variant of the Chinese term appears in the translation.
        cn_variants = [v.strip() for v in cn_term.split("/")]
        found_cn = any(v in translation for v in cn_variants)
        translation_lower = translation.lower()
        found_en = en_term.lower() in translation_lower
        for abbrev in info.get("abbrevs", []):
            if abbrev.strip().lower() in translation_lower:
                found_en = True
                break
        for alias in info.get("aliases", []):
            if alias.strip().lower() in translation_lower:
                found_en = True
                break

        if found_cn:
            confirmed.append(en_term)
        elif found_en:
            # English term still present — likely untranslated.
            violations.append({
                "term": en_term,
                "expected": cn_term,
                "issue": "English term left untranslated"
            })
        else:
            # Neither English nor Chinese variant present — term may be omitted.
            violations.append({
                "term": en_term,
                "expected": cn_term,
                "issue": "Locked term missing from translation"
            })

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
        "found_in_translation": len(confirmed),
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
    build.add_argument("--output", default="lock.json", help="Output lock file")
    build.add_argument("--json", action="store_true", help="Output structured JSON")

    check = subparsers.add_parser("check", help="Check translation against lock table")
    check.add_argument("translation", help="Translated file")
    check.add_argument("--lock", default="lock.json", help="Lock file")
    check.add_argument("--json", action="store_true", help="Output structured JSON")

    add = subparsers.add_parser("add", help="Add a term to the lock table")
    add.add_argument("en_term", help="English term")
    add.add_argument("cn_term", help="Chinese translation")
    add.add_argument("--lock", default="lock.json", help="Lock file")
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
