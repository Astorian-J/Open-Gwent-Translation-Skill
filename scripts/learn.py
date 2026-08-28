#!/usr/bin/env python3
"""
Gwent translation learning script.
Analyzes the source text to discover new terms not in references.
Outputs suggested additions to pending_terms.md for verification.

Usage:
    python learn.py <source_file> [--auto] [--from-lock <lock.json>] [--json]
    python learn.py --commit [--json]

    source_file:      English source text
    --auto:           Write discoveries to the gitignored auto buffer
                      (references/pending_terms.auto.md, default: preview only)
    --from-lock:      Also feed the lock's status=pending entries (machine-
                      extracted terms with no official match) into the same
                      buffer — the precise candidates prepare identified, not
                      just a fresh source-wide scan
    --commit:         Merge the auto buffer into the local pending_terms.md
                      (the human review inbox, gitignored runtime data)
                      and delete the buffer
    --json:           Output structured JSON for agent consumption
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (
    _QUOTE_NORM,
    _edit_distance,
    SKIP_ABBREVS_FULL,
    SKIP_WORDS_FULL,
    extract_abbreviations,
    extract_capitalized_phrases,
    extract_card_names,
    get_card_names_index,
    is_likely_common_word,
    json_output,
    parse_markdown_table,
)


def _get_ref_path(filename: str) -> Path:
    return Path(__file__).parent.parent / "references" / filename


def _add_term(terms: dict[str, str], en: str, cn: str) -> None:
    """Add English term(s) to the dictionary, splitting on '/'.

    Typographic quotes fold to ASCII first: card data ships names like
    "The Manor’s Dark Secret" (U+2019) — without the fold, the >127 guard
    below silently drops every such card, and its fragments then leak into
    pending as "unknown" terms.
    """
    if not en or not cn:
        return
    en = en.translate(_QUOTE_NORM)
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

    # Card names — cards-only, from the 4lang table + card_overrides.md (via the
    # shared helper). Supersedes the old card_names.md verified section.
    for en, cn in get_card_names_index().values():
        _add_term(terms, en, cn)

    return terms


def load_pending_terms(path: Path | None = None) -> list[dict]:
    """Load terms already in a pending file (local review inbox or auto buffer)."""
    pending = path or _get_ref_path("pending_terms.md")
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

    # Pattern 3: All-caps abbreviations. Table/label markers (NOTE, RANK, ...)
    # are all-caps in BC tables but are never terms — gate them through the
    # common-word list via capitalize() ("NOTE" -> "Note").
    for abbrev in extract_abbreviations(source_text, skip_abbrevs=SKIP_ABBREVS_FULL):
        if not is_likely_common_word(abbrev.capitalize()):
            candidates.append(("abbrev", abbrev))

    # Pattern 4: Single-word capitalized terms that are not common words.
    # capitalize() folds ALL-CAPS table markers ("NOTE" -> "Note") into the
    # curated list lookup, same as Pattern 3.
    for match in re.finditer(r'\b([A-Z][a-zA-Z]{3,})\b', source_text):
        word = match.group(1)
        if not is_likely_common_word(word.capitalize()):
            candidates.append(("phrase", word))

    # Pattern 5: Words with special Gwent notation
    for match in re.finditer(r'\b([A-Z][a-z]+)\s+(?:for)\s+(\d+)\b', source_text):
        candidates.append(("phrase", match.group(0)))

    return candidates



# Typo-gate minimum candidate length. Short candidates (Kiri vs ciri, seal
# vs seas) sit in every known term's 1-edit neighborhood — gating them would
# silently swallow real new card names, which is learn's whole job. Same
# reasoning as _shared.CARD_FUZZY_MIN_TOKEN ("short = noisy").
TYPO_GATE_MIN_LEN = 5


def _is_typo_of_known(key: str, known, known_tokens) -> bool:
    """True when key is within edit distance 1 of a known term or token.

    Whole-key compare first; single-word candidates additionally compare
    against known terms' individual words ("Dechhand" is 1 edit from the
    word "deckhand" inside "acherontia deckhand" but 10 from the full key).
    Candidates shorter than TYPO_GATE_MIN_LEN are never gated.
    """
    if len(key) < TYPO_GATE_MIN_LEN:
        return False
    if any(
        _edit_distance(key, k) <= 1
        for k in known
        if abs(len(k) - len(key)) <= 1
    ):
        return True
    if " " not in key:
        return any(
            _edit_distance(key, t) <= 1
            for t in known_tokens
            if abs(len(t) - len(key)) <= 1
        )
    return False


def find_unknown_terms(source_text: str) -> list[dict]:
    """Find terms in source that are not in our reference database."""
    known = load_all_terms()
    candidates = extract_candidate_terms(source_text)

    unknown = []
    seen = set()
    # pending_terms 只读不写，循环外预读一次（原写法每个未知候选都重读重解析）
    pending_keys = {
        p.get("source", "").lower().translate(_QUOTE_NORM)
        for p in load_pending_terms()
    }
    # Known terms' individual words, for token-level typo comparison below.
    known_tokens = {w for k in known for w in k.split()}

    for term_type, term_text in candidates:
        key = term_text.lower().translate(_QUOTE_NORM)
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

        # Typo gate (see _is_typo_of_known): real data ships typos like
        # "Dechhand" for "Deckhand" — 1-edit neighbors of known terms are
        # noise, not discoveries.
        if _is_typo_of_known(key, known, known_tokens):
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

        # Check if already in pending（pending_keys 在循环外预读一次）
        if key in pending_keys:
            continue

        unknown.append({
            "type": term_type,
            "source": term_text,
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
        f"- Suggested: (translate and verify)",
        f"- Confidence: {term['confidence']}",
        # Preserve the original discovery date when re-formatting (e.g. a
        # --commit merge re-renders buffered entries; the date should say when
        # the term was FOUND, not when it was merged).
        f"- Discovered: {term.get('discovered') or datetime.now().strftime('%Y-%m-%d')}",
        "- Status: pending review",
        ""
    ]
    return "\n".join(lines)


def preview_new_terms(source_text: str, silent: bool = False) -> list[dict]:
    """Preview new terms without writing to file."""
    unknown = find_unknown_terms(source_text)

    if not silent and not unknown:
        print("No new terms discovered.")
        return []

    if not silent:
        print(f"Discovered {len(unknown)} potential new term(s):\n")
        for term in unknown:
            print(f"  [{term['type']}] {term['source']}")
            print()

    return unknown


AUTO_BUFFER_NAME = "pending_terms.auto.md"


def add_to_pending(terms: list[dict], buffer: bool = False) -> tuple[int, Path]:
    """Append terms to the local pending inbox or the auto buffer.

    Both files are gitignored runtime data — installs and updates never
    touch them. --auto discovery writes to the auto buffer so findings
    batch up; --commit later merges the buffer into the review inbox
    for human review.

    Returns (count_added, path_written).
    Uses atomic write (temp file + rename) to avoid corruption
    if two processes run simultaneously.
    """
    import os
    import tempfile

    pending_path = _get_ref_path(AUTO_BUFFER_NAME if buffer else "pending_terms.md")

    if buffer:
        header = (
            "# Pending Terms — auto buffer (learn --auto)\n\n"
            "Collected automatically during finish; NOT tracked by git.\n"
            "Run `python scripts/learn.py --commit` to merge into pending_terms.md "
            "for human review.\n\n"
            "---\n\n"
        )
    elif not pending_path.exists():
        header = (
            "# Pending Terms (待审核术语)\n\n"
            "Terms discovered during translation that need verification.\n"
            "After verification, move confirmed entries to the appropriate reference file.\n\n"
            "---\n\n"
        )
    else:
        header = None

    content = header if header is not None else pending_path.read_text(encoding="utf-8")

    # Check for duplicates (quote-folded: _QUOTE_NORM's invariant — every
    # English-name comparison folds, so a hand-written curly-quote entry and
    # an ASCII re-discovery dedupe against each other)
    existing_sources = set()
    for line in content.split("\n"):
        if line.startswith("### "):
            existing_sources.add(line[4:].strip().lower().translate(_QUOTE_NORM))

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

    return added, pending_path


def commit_buffer() -> tuple[int, int]:
    """Merge the auto buffer into the local pending review inbox.

    Returns (merged, dropped_duplicates). The buffer file is physically
    removed afterwards — committed entries live in the review inbox, and
    an emptied buffer would only invite double-merges.
    """
    buffer_path = _get_ref_path(AUTO_BUFFER_NAME)
    if not buffer_path.exists():
        return 0, 0
    entries = load_pending_terms(buffer_path)
    if not entries:
        buffer_path.unlink(missing_ok=True)
        return 0, 0
    merged, _ = add_to_pending(entries, buffer=False)
    # missing_ok: a concurrent --commit may have consumed the buffer between
    # our read and this unlink — treat that as success, not a crash.
    buffer_path.unlink(missing_ok=True)
    return merged, len(entries) - merged


def main():
    parser = argparse.ArgumentParser(description="Gwent translation learning script")
    parser.add_argument("source", nargs="?", help="English source file (not needed for --commit)")
    parser.add_argument("--auto", action="store_true",
                        help="Write discoveries to the gitignored auto buffer (pending_terms.auto.md)")
    parser.add_argument("--from-lock", metavar="LOCK_JSON",
                        help="Also feed status=pending entries from a context lock JSON into "
                             "the candidate list (precise machine-extracted unknowns)")
    parser.add_argument("--commit", action="store_true",
                        help="Merge the auto buffer into the local pending_terms.md (human review inbox)")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    args = parser.parse_args()

    if args.commit:
        merged, dupes = commit_buffer()
        if args.json:
            json_output({"command": "commit", "merged": merged, "dropped_duplicates": dupes}, exit_code=0)
        tail = f" ({dupes} duplicate(s) dropped)" if dupes else ""
        print(f"Committed {merged} term(s) from auto buffer to pending_terms.md{tail}")
        return

    if not args.source:
        parser.error("source file is required unless --commit is given")

    source_path = Path(args.source)

    if not source_path.exists():
        if args.json:
            json_output(None, errors=[f"source file not found: {args.source}"], exit_code=1)
        print(f"Error: source file not found: {args.source}")
        sys.exit(1)

    source_text = source_path.read_text(encoding="utf-8")

    unknown = preview_new_terms(source_text, silent=args.json)

    # Lock-pending entries: prepare already singled out machine-extracted terms
    # with no official match ("translate by judgment; if recurring, record").
    # Recycling them here turns the human review from "think of candidate
    # words" into "tick or reject the pre-collected list" — same buffer, same
    # gitignored local file, deduped against existing entries by add_to_pending.
    lock_candidates: list[dict] = []
    if args.from_lock:
        lock_path = Path(args.from_lock)
        if lock_path.exists():
            try:
                lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, ValueError):
                lock_data = None
            if isinstance(lock_data, dict):
                for term, info in (lock_data.get("terms") or {}).items():
                    if isinstance(info, dict) and info.get("status") == "pending":
                        lock_candidates.append({
                            "source": term,
                            "type": "unknown",
                            "confidence": "medium (lock-pending: machine-extracted, no official match)",
                        })
            if not args.json:
                print(f"Lock-pending candidates from {lock_path.name}: {len(lock_candidates)}")
        else:
            print(f"[WARN] --from-lock file not found, skipped: {args.from_lock}",
                  file=sys.stderr)
        seen = {t["source"].lower() for t in unknown}
        for cand in lock_candidates:
            if cand["source"].lower() not in seen:
                unknown.append(cand)
                seen.add(cand["source"].lower())

    added, buffer_path = 0, _get_ref_path(AUTO_BUFFER_NAME)
    if unknown and args.auto:
        added, buffer_path = add_to_pending(unknown, buffer=True)

    if args.json:
        data = {
            "new_terms_found": len(unknown),
            "from_lock_candidates": len(lock_candidates),
            "auto_write": args.auto,
            "added_to_buffer": added,
            "buffer_path": str(buffer_path),
            "terms": unknown,
        }
        json_output(data, exit_code=0)

    if not unknown:
        sys.exit(0)

    if args.auto:
        print(f"Added {added} term(s) to the auto buffer ({buffer_path.name})")
        print("Review and merge into the review inbox with: python scripts/learn.py --commit")
    else:
        print("Preview mode. Run with --auto to write to the auto buffer")
        print("Or manually add confirmed terms to the appropriate reference file.")


if __name__ == "__main__":
    main()
