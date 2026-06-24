#!/usr/bin/env python3
"""Effect Verifier (informational self-check) — official card effects in a translation.

For each card mentioned in the SOURCE, looks up its official CN ability
(references/effect_text.json) and reports whether that official text appears
(verbatim, whitespace-normalized) in the TRANSLATION.

This is INFORMATIONAL, not a gate: a card's official effect being absent usually
just means the translation did not quote it. Use it as a self-check when the
article discusses card effects. Exit code is always 0 (unless input is missing),
so it never blocks finalization on its own.

Usage:
    python effect_verifier.py source.md translated.txt
    python effect_verifier.py source.md translated.txt --json
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import (  # noqa: E402
    extract_card_names,
    extract_card_names_no_colon,
    get_term_authority,
    json_output,
)


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def _cards_in_source(text: str) -> set[str]:
    # max_words/min_length mirror _shared.TermAuthority.get_all_for_text so the
    # verifier sees the same cards the lock builder would.
    cands: set[str] = set()
    for n in extract_card_names(text):
        cands.add(n.strip())
    for n in extract_card_names_no_colon(text, max_words=5, min_length=4):
        cands.add(n.strip())
    return cands


def main() -> None:
    ap = argparse.ArgumentParser(description="Official-effect self-check (informational)")
    ap.add_argument("source", help="Original source file")
    ap.add_argument("translated", help="Translated file")
    ap.add_argument("--json", action="store_true", help="Structured JSON output")
    args = ap.parse_args()

    src, tr = Path(args.source), Path(args.translated)
    if not src.exists() or not tr.exists():
        msg = f"file not found: {args.source if not src.exists() else args.translated}"
        if args.json:
            json_output(None, errors=[msg], exit_code=1)
        print(msg)
        sys.exit(1)

    src_text = src.read_text(encoding="utf-8")
    tr_norm = _normalize(tr.read_text(encoding="utf-8"))
    authority = get_term_authority()

    present, missing = [], []
    for en in _cards_in_source(src_text):
        rec = authority.get_official_ability(en)
        if not rec or not rec.get("cn_ability"):
            continue
        ability = _normalize(rec["cn_ability"])
        # Verbatim test: the full normalized official ability must appear as a
        # substring of the normalized translation. (Minor punctuation/wording
        # differences still count as a miss — this is informational, not a gate.)
        if ability and ability in tr_norm:
            present.append({"english": en, "chinese": rec.get("cn_name", "")})
        else:
            missing.append({
                "english": en,
                "chinese": rec.get("cn_name", ""),
                "official_ability": rec["cn_ability"],
            })

    data = {
        "checked": len(present) + len(missing),
        "verbatim_present": present,
        "not_found": missing,
    }
    if args.json:
        json_output(data, exit_code=0)

    print("=" * 60)
    print("EFFECT VERIFIER (informational)")
    print("=" * 60)
    print(f"Checked {data['checked']} card(s) that appear in the source and have")
    print("official effect text.")
    print()
    print(f"Official effect found verbatim in translation: {len(present)}")
    for p in present:
        print(f"  + {p['english']} / {p['chinese']}")
    print()
    print(f"Official effect NOT found: {len(missing)}")
    print("(likely just not quoted — only review these if the article DID quote")
    print(" the card's effect.)")
    for m in missing[:20]:
        ab = " ".join(m["official_ability"].split())
        print(f"  . {m['english']} / {m['chinese']}: {ab[:50]}")
    if len(missing) > 20:
        print(f"  . ... ({len(missing) - 20} more)")
    sys.exit(0)


if __name__ == "__main__":
    main()
