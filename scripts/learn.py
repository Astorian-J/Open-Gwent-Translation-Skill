#!/usr/bin/env python3
"""
Gwent translation learning script.
Analyzes source + translated text to discover new terms not in references.
Outputs suggested additions to pending_terms.md for verification.

Usage:
    python learn.py <source_file> <translated_file> [--auto] [--json]

    source_file:      English source text
    translated_file:  Chinese translation
    --auto:           Write directly to pending_terms.md (default: preview only)
    --json:           Output structured JSON for agent consumption
"""

import argparse
import json
import re
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (
    SKIP_ABBREVS_FULL,
    SKIP_WORDS_FULL,
    extract_abbreviations,
    extract_capitalized_phrases,
    extract_card_names,
    is_likely_common_word,
    json_output,
    parse_markdown_table,
)


def _get_ref_path(filename: str) -> Path:
    return Path(__file__).parent.parent / "references" / filename


def _add_term(terms: dict[str, str], en: str, cn: str) -> None:
    """Add English term(s) to the dictionary, splitting on '/'."""
    if not en or not cn:
        return
    if any(ord(c) > 127 for c in en):
        return
    for part in en.split("/"):
        part = part.strip().lower()
        if part and part not in ("english", "—", ""):
            terms[part] = cn


def load_all_terms() -> dict[str, str]:
    """Load all known English terms and their Chinese translations.

    Returns: english_lower -> chinese mapping
    """
    terms: dict[str, str] = {}

    # terminology_map.md, competitive_terms.md, keywords_map.md
    for fname in ["terminology_map.md", "competitive_terms.md", "keywords_map.md"]:
        fpath = _get_ref_path(fname)
        if not fpath.exists():
            continue
        text = fpath.read_text(encoding="utf-8")
        for row in parse_markdown_table(text, min_columns=2):
            en = row.get("english", "")
            cn = row.get("chinese", "")
            _add_term(terms, en, cn)

            # competitive_terms.md has an abbreviations column
            abbr = row.get("abbreviations", "")
            if abbr and abbr not in ("Abbreviations", "—", ""):
                for part in abbr.split(";"):
                    _add_term(terms, part.strip(), cn)

    # card_names.md — verified section only
    card_file = _get_ref_path("card_names.md")
    if card_file.exists():
        text = card_file.read_text(encoding="utf-8")
        # Slice from the verified header to the renamed/corrected header.
        verified_start = text.find("## Verified")
        renamed_start = text.find("## Renamed / Corrected")
        if verified_start != -1:
            end = renamed_start if renamed_start != -1 else len(text)
            verified_text = text[verified_start:end]
            for row in parse_markdown_table(verified_text, min_columns=2):
                en = row.get("english", "")
                cn = row.get("chinese", "")
                _add_term(terms, en, cn)

    return terms


def load_pending_terms() -> list[dict]:
    """Load terms already in pending buffer."""
    pending = _get_ref_path("pending_terms.md")
    if not pending.exists():
        return []

    terms = []
    current = {}
    in_entry = False
    for line in pending.read_text(encoding="utf-8").split("\n"):
        if line.startswith("### "):
            if current:
                terms.append(current)
            current = {"source": line[4:].strip()}
            in_entry = True
        elif in_entry and line.startswith("- "):
            key, _, val = line[2:].partition(":")
            current[key.strip().lower()] = val.strip()
    if current:
        terms.append(current)

    return terms


def extract_candidate_terms(source_text: str) -> list[tuple[str, str]]:
    """Extract candidate terms from English source text.
    Returns: list of (term_type, term_text)
    """
    candidates = []

    # Pattern 1: Card names with colons
    for name in extract_card_names(source_text):
        candidates.append(("card", name))

    # Pattern 2: Multi-word capitalized phrases
    for name in extract_capitalized_phrases(
        source_text, max_words=4, min_length=4, skip_words=SKIP_WORDS_FULL
    ):
        first = name.split()[0]
        if not is_likely_common_word(first):
            candidates.append(("phrase", name))

    # Pattern 3: All-caps abbreviations
    for abbrev in extract_abbreviations(source_text, skip_abbrevs=SKIP_ABBREVS_FULL):
        candidates.append(("abbrev", abbrev))

    # Pattern 4: Single-word capitalized terms that are not common words.
    for match in re.finditer(r'\b([A-Z][a-zA-Z]{3,})\b', source_text):
        word = match.group(1)
        if not is_likely_common_word(word):
            candidates.append(("phrase", word))

    # Pattern 5: Words with special Gwent notation
    for match in re.finditer(r'\b([A-Z][a-z]+)\s+(?:for)\s+(\d+)\b', source_text):
        candidates.append(("phrase", match.group(0)))

    return candidates



def find_unknown_terms(source_text: str, translated_text: str) -> list[dict]:
    """Find terms in source that are not in our reference database."""
    known = load_all_terms()
    candidates = extract_candidate_terms(source_text)

    unknown = []
    seen = set()

    for term_type, term_text in candidates:
        key = term_text.lower()
        if key in seen:
            continue
        seen.add(key)

        # Check if known (fuzzy match)
        if key in known:
            continue

        # Check if any known term contains this
        found_parent = False
        for known_en in known:
            if key in known_en or known_en in key:
                found_parent = True
                break
        if found_parent:
            continue

        # For colon-style card names, if the prefix is a known standalone card
        # and the suffix doesn't appear in ANY card name in the database,
        # skip it as a likely sentence fragment (not a real card).
        # This catches cases like "Syanna: Duchess" where "Syanna" is a card
        # but "Duchess" is not a card subtitle.
        if term_type == "card" and ":" in term_text:
            parts = term_text.split(":", 1)
            prefix = parts[0].strip().lower()
            suffix = parts[1].strip().lower() if len(parts) > 1 else ""
            if prefix in known and suffix:
                suffix_in_db = any(suffix in k for k in known)
                if not suffix_in_db:
                    continue

        # Check if already in pending
        pending = load_pending_terms()
        in_pending = any(p.get("source", "").lower() == key for p in pending)
        if in_pending:
            continue

        # Try to find Chinese translation in the translated text
        # Simple heuristic: look for Chinese text near where this term might be
        cn_translation = ""

        unknown.append({
            "type": term_type,
            "source": term_text,
            "translation": cn_translation,
            "confidence": "low"  # Requires human verification
        })

    # Sort by type priority: card > abbrev > phrase
    type_order = {"card": 0, "abbrev": 1, "phrase": 2}
    unknown.sort(key=lambda x: type_order.get(x["type"], 3))

    return unknown


def format_pending_entry(term: dict) -> str:
    """Format a single term as markdown entry."""
    lines = [
        f"### {term['source']}",
        f"- Type: {term['type']}",
        f"- Suggested: {term['translation'] or '(translate and verify)'}",
        f"- Confidence: {term['confidence']}",
        f"- Discovered: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}",
        "- Status: pending review",
        ""
    ]
    return "\n".join(lines)


def preview_new_terms(source_text: str, translated_text: str, silent: bool = False) -> list[dict]:
    """Preview new terms without writing to file."""
    unknown = find_unknown_terms(source_text, translated_text)

    if not silent and not unknown:
        print("No new terms discovered.")
        return []

    if not silent:
        print(f"Discovered {len(unknown)} potential new term(s):\n")
        for term in unknown:
            print(f"  [{term['type']}] {term['source']}")
            if term['translation']:
                print(f"           → {term['translation']}")
            print()

    return unknown


def add_to_pending(terms: list[dict]) -> int:
    """Add terms to pending_terms.md. Returns count added.

    Uses atomic write (temp file + rename) to avoid corruption
    if two processes run simultaneously.
    """
    import os
    import tempfile

    pending_path = _get_ref_path("pending_terms.md")

    # Create file with header if not exists
    if not pending_path.exists():
        content = (
            "# Pending Terms (待审核术语)\n\n"
            "Terms discovered during translation that need verification.\n"
            "After verification, move confirmed entries to the appropriate reference file.\n\n"
            "---\n\n"
        )
    else:
        content = pending_path.read_text(encoding="utf-8")

    # Check for duplicates
    existing_sources = set()
    for line in content.split("\n"):
        if line.startswith("### "):
            existing_sources.add(line[4:].strip().lower())

    added = 0
    for term in terms:
        if term["source"].lower() in existing_sources:
            continue
        content += format_pending_entry(term)
        added += 1

    if added > 0:
        # Atomic write: temp file + rename
        temp_fd, temp_path = tempfile.mkstemp(
            dir=str(pending_path.parent), suffix=".md"
        )
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(temp_path, pending_path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    return added


def main():
    parser = argparse.ArgumentParser(description="Gwent translation learning script")
    parser.add_argument("source", help="English source file")
    parser.add_argument("translated", help="Chinese translated file")
    parser.add_argument("--auto", action="store_true", help="Write directly to pending_terms.md")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    args = parser.parse_args()

    source_path = Path(args.source)
    translated_path = Path(args.translated)

    if not source_path.exists():
        if args.json:
            json_output(None, errors=[f"source file not found: {args.source}"], exit_code=1)
        print(f"Error: source file not found: {args.source}")
        sys.exit(1)
    if not translated_path.exists():
        if args.json:
            json_output(None, errors=[f"translated file not found: {args.translated}"], exit_code=1)
        print(f"Error: translated file not found: {args.translated}")
        sys.exit(1)

    source_text = source_path.read_text(encoding="utf-8")
    translated_text = translated_path.read_text(encoding="utf-8")

    unknown = preview_new_terms(source_text, translated_text, silent=args.json)

    added = 0
    if unknown and args.auto:
        added = add_to_pending(unknown)

    if args.json:
        data = {
            "new_terms_found": len(unknown),
            "auto_write": args.auto,
            "added_to_pending": added,
            "terms": unknown,
        }
        json_output(data, exit_code=0)

    if not unknown:
        sys.exit(0)

    if args.auto:
        print(f"Added {added} term(s) to pending_terms.md")
    else:
        print("Preview mode. Run with --auto to write to pending_terms.md")
        print("Or manually add confirmed terms to the appropriate reference file.")


if __name__ == "__main__":
    main()
