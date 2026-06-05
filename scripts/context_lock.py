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

import json
import sys
from pathlib import Path
from datetime import datetime

from _shared import (
    extract_abbreviations,
    extract_capitalized_phrases,
    extract_card_names,
    extract_card_names_no_colon,
    extract_terms_from_markdown,
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


def build_lock(source_file: str, lock_file: str):
    """Build a new lock table from source text."""
    source_text = Path(source_file).read_text(encoding="utf-8")
    candidates = extract_terms_from_source(source_text)

    lock = {
        "document": Path(source_file).stem,
        "created_at": datetime.now().isoformat(),
        "terms": {}
    }

    for term, _ in candidates.items():
        lock["terms"][term] = {
            "cn": "",
            "status": "pending",
            "first_seen": "auto-detected"
        }

    save_lock(lock, lock_file)
    print(f"Built lock table with {len(lock['terms'])} terms")
    print(f"Save to: {lock_file}")
    print()
    print("Next steps:")
    print("1. Translate the text, looking up terms in references/")
    print("2. As you decide each translation, update the lock table:")
    print(f'   python context_lock.py add "Term" "翻译" --lock {lock_file}')
    print("3. For subsequent paragraphs, check against the lock:")
    print(f'   python context_lock.py check translated.txt --lock {lock_file}')


def check_translation(translation_file: str, lock_file: str):
    """Check translation against lock table for consistency violations."""
    lock = load_lock(lock_file)
    translation = Path(translation_file).read_text(encoding="utf-8")

    violations = []
    confirmed = []

    for en_term, info in lock["terms"].items():
        cn_term = info.get("cn", "")
        status = info.get("status", "pending")

        if status == "confirmed" and cn_term:
            # Check if the Chinese term appears (or its alternatives)
            variants = [cn_term]
            # Also check for partial matches
            if "/" in cn_term:
                variants = [v.strip() for v in cn_term.split("/")]

            found = any(v in translation for v in variants)
            if found:
                confirmed.append(en_term)
            else:
                # The English term might be translated differently
                # This is a soft check—only flag if the EN term appears untranslated
                if en_term.lower() in translation.lower():
                    violations.append({
                        "term": en_term,
                        "expected": cn_term,
                        "issue": "English term left untranslated"
                    })

    print(f"# Context Lock Check")
    print()
    print(f"Lock file: {lock_file}")
    print(f"Confirmed terms in lock: {len([t for t in lock['terms'].values() if t.get('status') == 'confirmed'])}")
    print(f"Terms found in translation: {len(confirmed)}")
    print()

    if violations:
        print("## Violations")
        print()
        for v in violations:
            print(f"- **{v['term']}**: {v['issue']}")
            print(f"  Expected: 「{v['expected']}」")
        print()
    else:
        print("No consistency violations found.")
        print()

    # Show pending terms
    pending = [(en, info) for en, info in lock["terms"].items() if info.get("status") != "confirmed"]
    if pending:
        print(f"## Pending terms ({len(pending)})")
        print()
        for en, info in pending:
            print(f"- {en}")
        print()
        print("Confirm with: python context_lock.py add \"Term\" \"翻译\" --lock", lock_file)


def add_term(en_term: str, cn_term: str, lock_file: str):
    """Add or update a term in the lock table."""
    lock = load_lock(lock_file)

    lock["terms"][en_term] = {
        "cn": cn_term,
        "status": "confirmed",
        "locked_at": datetime.now().isoformat()
    }

    save_lock(lock, lock_file)
    print(f"Locked: 「{en_term}」→ 「{cn_term}」")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python context_lock.py build source.txt --output lock.json")
        print("  python context_lock.py check translation.txt --lock lock.json")
        print("  python context_lock.py add \"Term\" \"翻译\" --lock lock.json")
        sys.exit(1)

    command = sys.argv[1]

    if command == "build":
        if len(sys.argv) < 3:
            print("Usage: python context_lock.py build source.txt --output lock.json")
            sys.exit(1)
        source_file = sys.argv[2]
        lock_file = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--output" else "lock.json"
        build_lock(source_file, lock_file)

    elif command == "check":
        if len(sys.argv) < 3:
            print("Usage: python context_lock.py check translation.txt --lock lock.json")
            sys.exit(1)
        translation_file = sys.argv[2]
        lock_file = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--lock" else "lock.json"
        check_translation(translation_file, lock_file)

    elif command == "add":
        if len(sys.argv) < 5:
            print("Usage: python context_lock.py add \"Term\" \"翻译\" --lock lock.json")
            sys.exit(1)
        en_term = sys.argv[2]
        cn_term = sys.argv[3]
        lock_file = sys.argv[5] if len(sys.argv) > 5 and sys.argv[4] == "--lock" else "lock.json"
        add_term(en_term, cn_term, lock_file)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
