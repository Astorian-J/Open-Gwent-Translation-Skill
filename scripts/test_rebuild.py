#!/usr/bin/env python3
"""Committed synthetic behavior tests for the gwent-translation rebuild (01-07b).

Locks the EXTERNALLY OBSERVABLE behavior of the rebuild into committed (no
samples, no copyright) assertions, so a regression fails `health_check`. Pure
stdlib; runnable standalone (`python scripts/test_rebuild.py [--json]`) or
imported by `health_check` via `run()`.

Each check asserts public behavior only (get_all_for_text / get_all_for_text_cn
/ count_occurrences / enforce_terms via a real built lock) — never internals.

Categories:
  1. EN extraction        — Dagur/Froth/Schirru/Geraltt variants resolve
  2. CN extraction        — 希里/烧灼 + 迪门家族水手 collision (Pirate|Corsair)
  3. False-lock guard     — Deploy/Armor/Boost/cat/rat not mis-locked to cards
  4. Check block (both)   — missing/wrong -> BLOCKED; correct -> PASS
  5. CJK absorb           — 希里 inside 冒牌希里 -> NOT present
  6. True unknown         — out-of-dict fabricated words -> not falsely locked
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _shared import TermAuthority, build_lock_from_source  # noqa: E402
from term_enforcer import enforce_terms, count_occurrences, _build_cjk_suppress  # noqa: E402


def _lock_from(source_text: str) -> dict:
    """Build a real context lock from synthetic source text (temp file)."""
    p = Path(tempfile.mktemp(suffix=".md"))
    p.write_text(source_text, encoding="utf-8")
    lp = build_lock_from_source(str(p))
    p.unlink()
    lock = json.loads(lp.read_text(encoding="utf-8"))
    lp.unlink()
    return lock


def _enforce(source_text: str, translation_text: str) -> dict:
    lock = _lock_from(source_text)
    tp = Path(tempfile.mktemp(suffix=".txt"))
    tp.write_text(translation_text, encoding="utf-8")
    try:
        return enforce_terms(tp, lock)
    finally:
        tp.unlink()


def _t_en_extraction() -> tuple[str, str]:
    ta = TermAuthority()
    text = ("Double-Bladed Dagur hits hard. Froth is strong. "
            "Schirru and Geraltt of Rivia are also good.")
    got = {r["canonical_en"] for r in ta.get_all_for_text(text)}
    need = {"Dagur Two Blades", "Golden Froth", "Schirrú", "Geralt of Rivia"}
    missing = need - got
    if missing:
        return ("FAIL", f"EN extraction missed: {sorted(missing)} (got {sorted(got)})")
    return ("PASS", "EN extraction: Dagur/Froth/Schirru/Geraltt variants resolve")


def _t_cn_extraction() -> tuple[str, str]:
    ta = TermAuthority()
    text = "希里很强，烧灼可以解场，迪门家族水手也很强。"
    res = {r["term"]: r for r in ta.get_all_for_text_cn(text)}
    detail = []
    if res.get("希里", {}).get("canonical_en") != "Ciri":
        detail.append("希里!=Ciri")
    if res.get("烧灼", {}).get("canonical_en") != "Scorch":
        detail.append("烧灼!=Scorch")
    dmn = res.get("迪门家族水手")
    ens = {c["en"] for c in (dmn or {}).get("candidates", [])}
    if not dmn or dmn.get("match_type") != "cn_collision":
        detail.append("迪门家族水手 not a collision")
    if "Dimun Pirate" not in ens or "Dimun Corsair" not in ens:
        detail.append(f"collision missing Pirate/Corsair (got {sorted(ens)})")
    if detail:
        return ("FAIL", f"CN extraction failed: {detail}")
    return ("PASS", "CN extraction: 希里/烧灼 + 迪门家族水手 collision (Pirate|Corsair)")


def _t_false_lock_guard() -> tuple[str, str]:
    ta = TermAuthority()
    res = ta.get_all_for_text("Deploy the unit. The cat and rat sit. Armor and boost.")
    # Common/game words must NOT resolve to a CARD (Deploy->Decoy was the bug).
    bad = [(r["term"], r["canonical_en"]) for r in res
           if r["term"].lower() in ("deploy", "cat", "rat", "armor", "boost")
           and r.get("type") == "card"]
    decoy = any(r["term"].lower() == "deploy" and r["canonical_en"] == "Decoy"
                for r in res)
    if bad or decoy:
        return ("FAIL", f"false lock to a card: {bad} (decoy={decoy})")
    return ("PASS", "False-lock guard: Deploy/Armor/Boost/cat/rat not mis-locked to cards")


def _t_block_encn() -> tuple[str, str]:
    wrong = _enforce("Ciri and Scorch are strong.", "这张卡很强，没提任何卡名。")
    right = _enforce("Ciri and Scorch are strong.", "希里和烧灼都很强。")
    flagged_wrong = [v["term"].lower() for v in wrong["violations"]
                     if v["term"].lower() in ("ciri", "scorch")]
    flagged_right = [v["term"].lower() for v in right["violations"]
                     if v["term"].lower() in ("ciri", "scorch")]
    if not flagged_wrong:
        return ("FAIL", "encn: missing official CN not blocked")
    if flagged_right:
        return ("FAIL", f"encn: correct CN falsely blocked: {flagged_right}")
    return ("PASS", "encn block: missing->BLOCKED, correct->PASS")


def _t_block_cnen() -> tuple[str, str]:
    wrong = _enforce("希里与烧灼是核心卡。", "This output drops every card name.")
    right = _enforce("希里与烧灼是核心卡。", "Ciri and Scorch are core cards.")
    flagged_wrong = [v["term"] for v in wrong["violations"]
                     if v["term"] in ("希里", "烧灼")]
    flagged_right = [v["term"] for v in right["violations"]
                     if v["term"] in ("希里", "烧灼")]
    if not flagged_wrong:
        return ("FAIL", "cnen: missing official EN not blocked")
    if flagged_right:
        return ("FAIL", f"cnen: correct EN falsely blocked: {flagged_right}")
    return ("PASS", "cnen block: missing->BLOCKED, correct->PASS")


def _t_cjk_absorb() -> tuple[str, str]:
    sup = _build_cjk_suppress({})
    bare = count_occurrences("玩家用了冒牌希里解场", ["希里"])
    fixed = count_occurrences("玩家用了冒牌希里解场", ["希里"], cjk_suppress=sup)
    real = count_occurrences("我用希里解场", ["希里"], cjk_suppress=sup)
    if not (bare == 1 and fixed == 0 and real == 1):
        return ("FAIL", f"CJK absorb broken: bare={bare} fixed={fixed} real={real}")
    return ("PASS", "CJK absorb: 希里 in 冒牌希里 -> NOT-present; real adjacency stays")


def _t_true_unknown() -> tuple[str, str]:
    ta = TermAuthority()
    en_res = ta.get_all_for_text("The Zyxqwopt card and a Blarghuffle unit appear.")
    cn_res = ta.get_all_for_text_cn("卡兹克沃普和弗拉古弗尔是虚构词。")
    bogus_en = [r["term"] for r in en_res
                if r["term"].lower() in ("zyxqwopt", "blarghuffle")]
    bogus_cn = [r["term"] for r in cn_res
                if r["term"] in ("卡兹克沃普", "弗拉古弗尔")]
    if bogus_en or bogus_cn:
        return ("FAIL", f"unknown words falsely locked: en={bogus_en} cn={bogus_cn}")
    return ("PASS", "True unknown: fabricated out-of-dict words not falsely locked")


_TESTS = [
    _t_en_extraction,
    _t_cn_extraction,
    _t_false_lock_guard,
    _t_block_encn,
    _t_block_cnen,
    _t_cjk_absorb,
    _t_true_unknown,
]


def run() -> list[tuple[str, str]]:
    """Run all rebuild behavior tests; return [(status, message), ...]."""
    results: list[tuple[str, str]] = []
    for test in _TESTS:
        try:
            results.append(test())
        except Exception as e:  # noqa: BLE001
            results.append(("FAIL", f"{test.__name__}: raised {type(e).__name__}: {e}"))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild behavior tests (committed synthetic)")
    parser.add_argument("--json", action="store_true", help="Emit a JSON envelope")
    args = parser.parse_args()
    results = run()
    passed = sum(1 for s, _ in results if s == "PASS")
    failed = sum(1 for s, _ in results if s == "FAIL")
    if args.json:
        from _shared import json_output
        json_output(
            {"passed": passed, "failed": failed, "total": len(results), "results": results},
            exit_code=0 if failed == 0 else 1,
        )
    print("=" * 60)
    print("REBUILD BEHAVIOR TESTS (committed synthetic)")
    print("=" * 60)
    for status, msg in results:
        print(f"  [{status}] {msg}")
    print()
    print(f"PASS: {passed}  FAIL: {failed}")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
