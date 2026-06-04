#!/usr/bin/env python3
"""
Gwent Terminology Lookup.
Quick search across all reference files.

Usage:
    python lookup.py <query> [--fuzzy]
    python lookup.py "Provision"
    python lookup.py "杰洛特" --fuzzy
    python lookup.py "部署"
"""

import re
import sys
from pathlib import Path
from difflib import SequenceMatcher


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def parse_markdown_table(text: str, filename: str) -> list[dict]:
    """Parse markdown tables from text."""
    results = []
    in_table = False
    headers = []

    for line in text.split("\n"):
        line = line.strip()

        # Detect table header
        if line.startswith("|") and "---" not in line and not in_table:
            headers = [h.strip().lower() for h in line.split("|")]
            in_table = False  # Wait for separator
            continue

        # Table separator
        if line.startswith("|") and "---" in line:
            in_table = True
            continue

        # Table row
        if in_table and line.startswith("|") and "---" not in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                # Build row dict from headers
                row = {"_file": filename}
                for i, h in enumerate(headers):
                    if i < len(parts):
                        row[h] = parts[i]
                # Only include rows that look like data (not header repeats)
                first_val = parts[1] if len(parts) > 1 else ""
                if first_val and first_val not in ("English", "Forbidden", "Wrong", "—", ""):
                    results.append(row)
            continue

        # End of table
        if in_table and not line.startswith("|"):
            in_table = False
            headers = []

    return results


def search_references(query: str, ref_dir: Path, fuzzy: bool = False) -> list[dict]:
    """Search all reference files for query."""
    results = []
    query_lower = query.lower()

    ref_files = [
        "terminology_map.md",
        "reverse_terminology_map.md",
        "card_names.md",
        "keywords_map.md",
        "competitive_terms.md",
        "ambiguous_names.md",
        "category_map.md",
        "correction_guide.md",
        "common_pitfalls.md",
        "style_fingerprint.md",
        "version_map.md",
        "cn_fuzzy_fixes.md",
    ]

    for fname in ref_files:
        fpath = ref_dir / fname
        if not fpath.exists():
            continue

        text = fpath.read_text(encoding="utf-8")

        # Parse tables
        rows = parse_markdown_table(text, fname)

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


def format_result(r: dict) -> str:
    """Format a single search result."""
    lines = []
    file = r["file"]
    value = r["value"]
    row = r["row"]

    lines.append(f"  [{file}]")

    # Extract relevant fields based on file type
    if file == "terminology_map.md":
        en = row.get("english", row.get("forbidden", ""))
        cn = row.get("chinese", row.get("must use", row.get("slang", "")))
        notes = row.get("notes", "")
        if en and cn:
            lines.append(f"    {en} → {cn}")
        if notes:
            lines.append(f"    Notes: {notes}")

    elif file == "reverse_terminology_map.md":
        cn = row.get("chinese", "")
        en = row.get("english", "")
        notes = row.get("notes", "")
        if cn and en:
            lines.append(f"    {cn} → {en}")
        if notes:
            lines.append(f"    Notes: {notes}")

    elif file == "card_names.md":
        en = row.get("english", "")
        cn = row.get("chinese", "")
        cid = row.get("card id", "")
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

    elif file == "keywords_map.md":
        en = row.get("english", "")
        cn = row.get("chinese", "")
        freq = row.get("freq", "")
        notes = row.get("notes", "")
        parts = []
        if en:
            parts.append(en)
        if cn:
            parts.append(f"→ {cn}")
        if freq:
            parts.append(f"(freq: {freq})")
        lines.append(f"    {' '.join(parts)}")
        if notes:
            lines.append(f"    Notes: {notes}")

    elif file == "competitive_terms.md":
        en = row.get("english", "")
        cn = row.get("chinese", "")
        abbr = row.get("abbreviations", "")
        notes = row.get("notes", row.get("context", ""))
        parts = []
        if en:
            parts.append(en)
        if cn:
            parts.append(f"→ {cn}")
        if abbr:
            parts.append(f"| Abbr: {abbr}")
        lines.append(f"    {' '.join(parts)}")
        if notes:
            lines.append(f"    {notes}")

    elif file == "ambiguous_names.md":
        en = row.get("full name", "")
        cn = row.get("chinese", "")
        clue = row.get("clue", "")
        if en and cn:
            lines.append(f"    {en} → {cn}")
        if clue:
            lines.append(f"    Context: {clue}")

    elif file == "correction_guide.md":
        wrong = row.get("wrong", "")
        right = row.get("right", "")
        if wrong and right:
            lines.append(f"    ❌ {wrong} → ✅ {right}")

    elif file == "common_pitfalls.md":
        wrong = row.get("wrong", "")
        right = row.get("right", "")
        issue = row.get("issue", "")
        if wrong and right:
            lines.append(f"    ❌ {wrong} → ✅ {right}")
        if issue:
            lines.append(f"    Issue: {issue}")

    elif file == "cn_fuzzy_fixes.md":
        wrong = row.get("wrong", "")
        correct = row.get("correct", "")
        ftype = row.get("type", "")
        notes = row.get("notes", "")
        if wrong and correct:
            icon = {"别字": "✏️", "同音": "🔊", "漏字": "📝", "音近": "🎵"}.get(ftype, "📌")
            lines.append(f"    {icon} 「{wrong}」→ 「{correct}」 ({ftype})")
        if notes:
            lines.append(f"    Notes: {notes}")

    else:
        # Generic: show all non-empty fields
        for key, val in row.items():
            if not key.startswith("_") and val:
                lines.append(f"    {key}: {val}")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python lookup.py <query> [--fuzzy] [--plain]")
        print("  --fuzzy: Enable fuzzy matching")
        print("  --plain: Disable emoji in output")
        print()
        print("Examples:")
        print('  python lookup.py "Provision"')
        print('  python lookup.py "杰洛特"')
        print('  python lookup.py "部署"')
        sys.exit(1)

    query = sys.argv[1]
    fuzzy = "--fuzzy" in sys.argv
    plain = "--plain" in sys.argv

    ref_dir = Path(__file__).parent.parent / "references"

    results = search_references(query, ref_dir, fuzzy)

    if not results:
        print(f"No results found for '{query}'")
        if not fuzzy:
            print("Try with --fuzzy for approximate matching")
        sys.exit(1)

    print(f"Results for '{query}': {len(results)} found\n")

    # Group by file
    by_file = {}
    for r in results:
        by_file.setdefault(r["file"], []).append(r)

    for file, file_results in by_file.items():
        print(f"\n{'=' * 50}")
        icon = "" if plain else "📄 "
        print(f"{icon}{file}")
        print(f"{'=' * 50}")
        for r in file_results[:5]:  # Limit to 5 per file
            print(format_result(r))
            print()

        if len(file_results) > 5:
            print(f"  ... and {len(file_results) - 5} more in this file")


if __name__ == "__main__":
    main()
