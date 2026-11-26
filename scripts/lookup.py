#!/usr/bin/env python3
"""
Gwent Terminology Lookup.
Quick search across all reference files.

Usage:
    python lookup.py <query> [--fuzzy] [--plain] [--json]
    python lookup.py "Provision"
    python lookup.py "杰洛特" --fuzzy
    python lookup.py "部署"
"""

import argparse
import json
import re
import sys
from pathlib import Path
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent))
from _shared import json_output, parse_markdown_table


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


# The reference files that are searched. Hits are printed grouped by file name
# (alphabetically within a score), not in this order.
REFERENCE_FILES = (
    "terminology_map.md",
    "reverse_terminology_map.md",
    "card_overrides.md",
    "keywords_map.md",
    "competitive_terms.md",
    "ambiguous_names.md",
    "category_map.md",
    "correction_guide.md",
    "common_pitfalls.md",
    "style_fingerprint.md",
    "version_map.md",
    "cn_fuzzy_fixes.md",
    "slang_map.md",
)


def search_references(query: str, ref_dir: Path, fuzzy: bool = False) -> list[dict]:
    """Search all reference files for query."""
    results = []
    query_lower = query.lower()

    for fname in REFERENCE_FILES:
        fpath = ref_dir / fname
        if not fpath.exists():
            continue

        text = fpath.read_text(encoding="utf-8")

        # Parse tables (shared parser; header keys are lowercased with spaces
        # normalized to underscores)
        rows = parse_markdown_table(text, min_columns=1)
        for row in rows:
            row["_file"] = fname

        for row in rows:
            # Search all fields
            match_score = 0
            matched_field = ""
            matched_value = ""

            for key, val in row.items():
                if key.startswith("_"):
                    continue
                val_str = str(val).lower()

                if query_lower in val_str:
                    match_score = 1.0
                    matched_field = key
                    matched_value = str(val)
                    break
                elif fuzzy and len(query) >= 2:
                    # Fuzzy match on individual words
                    for word in val_str.split():
                        if len(word) >= 2:
                            sim = similarity(query, word)
                            if sim > 0.6 and sim > match_score:
                                match_score = sim
                                matched_field = key
                                matched_value = str(val)

            if match_score > 0:
                results.append({
                    "file": row["_file"],
                    "score": match_score,
                    "field": matched_field,
                    "value": matched_value,
                    "row": row,
                })

    # Sort by score (exact matches first)
    results.sort(key=lambda x: (-x["score"], x["file"]))

    # Deduplicate by value
    seen = set()
    deduped = []
    for r in results:
        key = (r["file"], r["value"])
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return deduped


CARD_DB_FILE = "card_names_4lang.json"


def search_card_db(query: str, ref_dir: Path, fuzzy: bool = False) -> list[dict] | None:
    """Search the build-time card-name DB (1381 cards, EN<->CN).

    The markdown reference tables carry terms/slang/keywords but NOT plain card
    names — the full EN/CN mapping lives only in card_names_4lang.json (a
    gitignored build artifact loaded by TermAuthority). Without this search a
    lookup for e.g. "Villentretenmerth" finds nothing even though the card DB
    knows it. Returns None when the DB is missing (not built yet) so the caller
    can warn instead of silently pretending the full corpus was searched.

    Result dicts match search_references' shape (file/score/field/value/row) so
    merging, sorting, and formatting stay shared. Only EN/CN are searched — this
    tool is EN<->CN; ru/pl fields are ignored.
    """
    fpath = ref_dir / CARD_DB_FILE
    if not fpath.exists():
        return None
    try:
        cards = json.loads(fpath.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    query_lower = query.lower()
    results = []
    for entry in cards.values() if isinstance(cards, dict) else cards:
        if not isinstance(entry, dict):
            continue
        en = str(entry.get("en", "") or "")
        cn = str(entry.get("cn", "") or "")
        en_lower = en.lower()
        score = 0.0
        field = ""
        value = ""
        if query_lower == en_lower or query == cn:
            score, field, value = 1.0, "en" if query_lower == en_lower else "cn", en or cn
        elif query_lower in en_lower or query in cn:
            # Substring scores 1.0, same as the markdown tables' substring hit —
            # cross-source ordering then follows insertion order (md first) instead
            # of an arbitrary penalty on card hits.
            score, field, value = 1.0, ("en" if query_lower in en_lower else "cn"), (en or cn)
        elif fuzzy and len(query) >= 2:
            best = 0.0
            for word in en_lower.split():
                if len(word) >= 2:
                    sim = similarity(query_lower, word)
                    if sim > best:
                        best = sim
            if best > 0.6:
                score, field, value = best, "en", en
        if score > 0:
            results.append({
                "file": CARD_DB_FILE,
                "score": score,
                "field": field,
                "value": value,
                "row": entry,
            })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def _has(row: dict, *columns: str) -> bool:
    """Whether the row's table has these columns, filled or not."""
    return all(column in row for column in columns)


def format_result(r: dict) -> str:
    """Format a single search result.

    Every cell of a markdown row that holds something is shown. Most reference
    files hold several tables with different columns, so a layout below applies
    only to a row that has its columns — the deck names of competitive_terms.md
    are read under their own column names, as TermAuthority reads them — and it
    shows the row's other columns too. Any other row is listed field by field.
    The card DB is the one exception: its rows carry far more than a lookup is
    asked for, so only the two names and the id are shown.
    """
    lines = []
    file = r["file"]
    row = r["row"]

    lines.append(f"  [{file}]")

    # Extract relevant fields based on the row's columns
    if file == CARD_DB_FILE:
        en = row.get("en", "")
        cn = row.get("cn", "")
        cid = row.get("card_id", "")
        parts = []
        if en:
            parts.append(en)
        if cn:
            parts.append(f"→ {cn}")
        if cid:
            parts.append(f"[{cid}]")
        lines.append(f"    {' '.join(parts)}")

    elif file == "terminology_map.md" and (
            _has(row, "english", "chinese") or _has(row, "english", "slang")
            or _has(row, "forbidden", "must_use")):
        en = row.get("english", row.get("forbidden", ""))
        cn = row.get("chinese", row.get("must_use", row.get("slang", "")))
        notes = row.get("notes", "")
        example = row.get("example", "")
        if en and cn:
            lines.append(f"    {en} → {cn}")
        if notes:
            lines.append(f"    Notes: {notes}")
        if example:
            lines.append(f"    Example: {example}")

    elif file == "reverse_terminology_map.md" and _has(row, "chinese", "english"):
        cn = row.get("chinese", "")
        en = row.get("english", "")
        notes = row.get("notes", "")
        if cn and en:
            lines.append(f"    {cn} → {en}")
        if notes:
            lines.append(f"    Notes: {notes}")

    elif file == "card_overrides.md" and (
            _has(row, "english", "chinese") or _has(row, "alias", "maps_to")):
        en = row.get("english", "") or row.get("alias", "")
        cn = row.get("chinese", "") or row.get("maps_to", "")
        cid = row.get("card_id", "")
        faction = row.get("faction", "")
        parts = []
        if en:
            parts.append(en)
        if cn:
            parts.append(f"→ {cn}")
        if cid:
            parts.append(f"[{cid}]")
        if faction:
            parts.append(f"| {faction}")
        lines.append(f"    {' '.join(parts)}")
        notes = row.get("notes", "")
        if notes:
            lines.append(f"    Notes: {notes}")

    elif file == "keywords_map.md" and _has(row, "english", "chinese"):
        en = row.get("english", "")
        cn = row.get("chinese", "")
        freq = row.get("freq", "")
        faction = row.get("faction", "")
        notes = row.get("notes", "")
        parts = []
        if en:
            parts.append(en)
        if cn:
            parts.append(f"→ {cn}")
        if freq:
            parts.append(f"(freq: {freq})")
        if faction:
            parts.append(f"| {faction}")
        lines.append(f"    {' '.join(parts)}")
        if notes:
            lines.append(f"    Notes: {notes}")

    elif file == "competitive_terms.md" and (
            _has(row, "english", "chinese") or _has(row, "english_deck_name", "community_chinese")):
        en = row.get("english", "") or row.get("english_deck_name", "")
        cn = row.get("chinese", "") or row.get("community_chinese", "")
        abbr = row.get("abbreviations", "")
        parts = []
        if en:
            parts.append(en)
        if cn:
            parts.append(f"→ {cn}")
        if abbr:
            parts.append(f"| Abbr: {abbr}")
        lines.append(f"    {' '.join(parts)}")
        # A terms row explains itself in `notes`, a deck row in `context`.
        for column in ("notes", "context"):
            if row.get(column):
                lines.append(f"    {row[column]}")

    elif file == "slang_map.md" and _has(row, "english", "intended_cn"):
        en = row.get("english", "")
        cn = row.get("intended_cn", "")
        forbidden = row.get("literal_forbidden", "")
        note = row.get("note", "")
        parts = []
        if en:
            parts.append(en)
        if cn:
            parts.append(f"→ {cn}")
        lines.append(f"    {' '.join(parts)}")
        if forbidden:
            lines.append(f"    Literal forbidden: {forbidden}")
        if note:
            lines.append(f"    Notes: {note}")

    elif file == "ambiguous_names.md" and _has(row, "full_name", "chinese"):
        en = row.get("full_name", "")
        cn = row.get("chinese", "")
        clue = row.get("clue", "")
        notes = row.get("notes", "")
        if en and cn:
            lines.append(f"    {en} → {cn}")
        if clue:
            lines.append(f"    Context: {clue}")
        if notes:
            lines.append(f"    Notes: {notes}")

    elif file in ("correction_guide.md", "common_pitfalls.md") and "wrong" in row and (
            "right" in row or "correct" in row):
        wrong = row.get("wrong", "")
        right = row.get("right", "") or row.get("correct", "")
        severity = row.get("severity", "")
        if wrong and right:
            lines.append(f"    [WRONG] {wrong} → [RIGHT] {right}")
        if severity:
            lines.append(f"    Severity: {severity}")
        # correction_guide.md explains a fix in `issue`, common_pitfalls.md in `why` or `notes`.
        for column, label in (("issue", "Issue"), ("why", "Why"), ("notes", "Notes")):
            if row.get(column):
                lines.append(f"    {label}: {row[column]}")

    elif file == "cn_fuzzy_fixes.md" and _has(row, "wrong", "correct"):
        wrong = row.get("wrong", "")
        correct = row.get("correct", "")
        ftype = row.get("type", "")
        if wrong and correct:
            icon = {"别字": "[TYP]", "同音": "[HOM]", "漏字": "[MISS]", "音近": "[SIM]"}.get(ftype, "[FIX]")
            lines.append(f"    {icon} 「{wrong}」→ 「{correct}」 ({ftype})")
        for column, label in (("notes", "Notes"), ("context", "Context")):
            if row.get(column):
                lines.append(f"    {label}: {row[column]}")

    else:
        # Generic: show all non-empty fields
        for key, val in row.items():
            if not key.startswith("_") and val:
                lines.append(f"    {key}: {val}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Gwent Terminology Lookup")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--fuzzy", action="store_true", help="Enable fuzzy matching")
    parser.add_argument("--plain", action="store_true", help="Disable emoji in output")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    args = parser.parse_args()

    # An empty query substring-matches EVERY row in every table (plus all 1381
    # cards) — refuse instead of flooding the caller.
    if not args.query.strip():
        print("Error: empty query", file=sys.stderr)
        sys.exit(1)

    ref_dir = Path(__file__).parent.parent / "references"
    results = search_references(args.query, ref_dir, args.fuzzy)

    # Card-name DB: the markdown tables carry terms/slang but not plain card
    # names; merge DB hits so one lookup covers the full corpus. A missing or
    # corrupted DB (build artifact, not in git) must warn — silence would read
    # as "not found in the full corpus" when only the md tables were searched.
    card_results = search_card_db(args.query, ref_dir, args.fuzzy)
    if card_results is None:
        if (ref_dir / CARD_DB_FILE).exists():
            reason, hint = "found but failed to parse (corrupted?)", "Rebuild it"
        else:
            reason, hint = "not built", "Build it once"
        print(
            f"[WARN] {CARD_DB_FILE} {reason} — card NAMES not searched (terms/slang only). "
            f"{hint}: python3 scripts/build_card_names_reference.py "
            "--src ~/gwent-card-db (offline) or --fetch",
            file=sys.stderr,
        )
    else:
        results.extend(card_results)
        results.sort(key=lambda r: r["score"], reverse=True)

    if args.json:
        data = {
            "query": args.query,
            "fuzzy": args.fuzzy,
            "result_count": len(results),
            "results": results,
        }
        json_output(data, exit_code=0 if results else 1)

    if not results:
        print(f"No results found for '{args.query}'")
        if not args.fuzzy:
            print("Try with --fuzzy for approximate matching")
        sys.exit(1)

    print(f"Results for '{args.query}': {len(results)} found\n")

    # Group by file
    by_file = {}
    for r in results:
        by_file.setdefault(r["file"], []).append(r)

    for file, file_results in by_file.items():
        print(f"\n{'=' * 50}")
        icon = "" if args.plain else "📄 "
        print(f"{icon}{file}")
        print(f"{'=' * 50}")
        for r in file_results[:5]:  # Limit to 5 per file
            print(format_result(r))
            print()

        if len(file_results) > 5:
            print(f"  ... and {len(file_results) - 5} more in this file")


if __name__ == "__main__":
    main()
