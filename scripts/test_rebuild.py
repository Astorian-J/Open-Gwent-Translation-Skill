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
  7. Gate integrity       — H1 fail-closed guard (check_translation + phase_c),
                            H2 --fix keeps TA, M9 lock build failure, M5
                            degradation signal (producer + consumer propagation)
"""

import argparse
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _shared import TermAuthority, build_lock_from_source  # noqa: E402
from check_translation import check_term_authority_violations  # noqa: E402
from phase_c_check import check_context_lock_terms  # noqa: E402
from term_enforcer import enforce_terms, count_occurrences, _build_cjk_suppress  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent


def _lock_from(source_text: str) -> dict:
    """Build a real context lock from synthetic source text (temp file)."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "source.md"
        p.write_text(source_text, encoding="utf-8")
        lp = build_lock_from_source(str(p))
        try:
            return json.loads(lp.read_text(encoding="utf-8"))
        finally:
            lp.unlink(missing_ok=True)


def _enforce(source_text: str, translation_text: str) -> dict:
    lock = _lock_from(source_text)
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / "translated.txt"
        tp.write_text(translation_text, encoding="utf-8")
        return enforce_terms(tp, lock)


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


def _t_subsume_guard() -> tuple[str, str]:
    ta = TermAuthority()

    def locked(text: str) -> set[str]:
        keys: set[str] = set()
        for r in ta.get_all_for_text(text):
            if r.get("cn") and r.get("canonical_en"):
                keys.add(r["term"].lower())
                keys.add(r["canonical_en"].lower())
        return keys

    # Substring card names occurring ONLY inside longer locked card names must
    # NOT keep standalone locks (Avallac'h inside "Avallac'h: Sage", Illusionist
    # inside "Yennefer: Illusionist" — CJK absorb made those locks unpassable).
    res = locked("Rank 4 is Avallac'h: Sage, rank 5 Yennefer: Illusionist.")
    subsumed_bad = [t for t in ("avallac'h", "illusionist") if t in res]
    full_ok = {"avallac'h: sage", "yennefer: illusionist"} <= res
    if subsumed_bad or not full_ok:
        return ("FAIL", f"subsumed locks kept={subsumed_bad}, full names locked={full_ok}")

    # A standalone occurrence keeps the short lock (only subsumed ones drop).
    res2 = locked("Avallac'h: Sage and plain Avallac'h both see play.")
    if not {"avallac'h", "avallac'h: sage"} <= res2:
        return ("FAIL", f"standalone Avallac'h lost its lock: {sorted(res2)}")

    # "Eternal" must not fuzzy-lock to Ethereal (edit distance 2; blocklisted).
    res3 = ta.get_all_for_text("Eternal Eclipse Deacon is rank 10.")
    ethereal = [r for r in res3 if r.get("canonical_en") == "Ethereal"]
    if ethereal:
        return ("FAIL", f"Eternal fuzzy-locked to Ethereal: {ethereal}")
    return ("PASS", "Subsume guard: substring-only drops, standalone keeps, no Eternal->Ethereal")


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
    sup, degraded = _build_cjk_suppress({})
    if degraded:
        return ("FAIL", f"healthy references flagged degraded: {degraded}")
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


def _t_h1_guard_fail_closed() -> tuple[str, str]:
    """Corrupted lock AND null-envelope (data:null) both -> [checker error]."""
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / "translated.txt"
        tp.write_text("这张卡很强。", encoding="utf-8")
        bad = Path(td) / "lock.json"
        bad.write_text("{broken json", encoding="utf-8")
        crashed = check_term_authority_violations(tp, lock_path=bad)
        # --source on a missing file: term_enforcer exits 1 with a
        # "data": null error envelope (key present, value null).
        null_env = check_term_authority_violations(
            tp, source_path=Path("/tmp/definitely-not-exist-src.md"))
    if not any("[checker error]" in i for i in crashed):
        return ("FAIL", f"corrupted lock not fail-closed: {crashed}")
    if not any("[checker error]" in i for i in null_env):
        return ("FAIL", f"null-envelope not fail-closed: {null_env}")
    return ("PASS", "H1 fail-closed: corrupted lock + null-envelope -> [checker error]")


def _t_h1_guard_fail_closed_phase_c() -> tuple[str, str]:
    """phase_c_check.py carries its own copy of the H1 guard clause — drive it too.

    Same two branches as _t_h1_guard_fail_closed: corrupted lock -> [checker
    error]; --source on a missing file (null-envelope, data:null) -> no crash,
    [checker error]."""
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / "translated.txt"
        tp.write_text("这张卡很强。", encoding="utf-8")
        bad = Path(td) / "lock.json"
        bad.write_text("{broken json", encoding="utf-8")
        crashed = check_context_lock_terms(tp, lock_path=bad)
        null_env = check_context_lock_terms(
            tp, source_path=Path("/tmp/definitely-not-exist-src.md"))
    if not any("[checker error]" in i for i in crashed):
        return ("FAIL", f"phase_c corrupted lock not fail-closed: {crashed}")
    if not any("[checker error]" in i for i in null_env):
        return ("FAIL", f"phase_c null-envelope not fail-closed: {null_env}")
    return ("PASS", "H1 fail-closed (phase_c): corrupted lock + null-envelope -> [checker error]")


def _t_h2_fix_keeps_ta() -> tuple[str, str]:
    """--fix rewrites 费->人口 AND term authority violations survive the re-check."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "source.md"
        src.write_text("Ciri is a strong gold card.\n", encoding="utf-8")
        trans = Path(td) / "translated.txt"
        trans.write_text("这张12费换8战力的卡很多人带。\n", encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "check_translation.py"),
             str(trans), "--source", str(src), "--fix", "--direction", "encn"],
            capture_output=True, text=True, timeout=60)
    if "Auto-fixed" not in r.stdout:
        return ("FAIL", f"--fix did not apply: {r.stdout[:200]}")
    if "term authority" not in r.stdout or r.returncode != 1:
        return ("FAIL", f"TA violation lost after --fix (exit {r.returncode}): {r.stdout[:300]}")
    return ("PASS", "H2: --fix applies 费→人口 AND keeps TA violations + exit 1")


def _t_m9_guard_lock_build_fail() -> tuple[str, str]:
    """Guard with --source whose lock build fails -> TA status=error, BLOCKED."""
    with tempfile.TemporaryDirectory() as td:
        trans = Path(td) / "translated.txt"
        trans.write_text("这张卡很强。\n", encoding="utf-8")
        bad_source = Path(td) / "a_directory.md"  # a directory: lock build must fail
        bad_source.mkdir()
        r = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "completeness_guard.py"),
             str(trans), "--source", str(bad_source), "--direction", "encn", "--json"],
            capture_output=True, text=True, timeout=120)
        try:
            data = json.loads(r.stdout)["data"]
        except (json.JSONDecodeError, KeyError) as e:
            return ("FAIL", f"guard stdout not clean JSON: {e}: {r.stdout[:200]}")
    checks = {c["name"]: c for c in data.get("checks", [])}
    ta = checks.get("term_authority", {})
    if (data.get("all_passed") is not False or ta.get("passed") is not False
            or ta.get("status") != "error" or r.returncode != 1):
        return ("FAIL", f"lock build failure not fail-closed: ta={ta} exit={r.returncode}")
    return ("PASS", "M9: --source lock build failure -> TA status=error, BLOCKED")


def _t_m5_degradation_signal() -> tuple[str, str]:
    """TermAuthority load failure -> degraded list + enforce_terms data.warnings."""
    import term_enforcer
    orig = term_enforcer.get_term_authority

    def _boom():
        raise RuntimeError("simulated load failure")

    term_enforcer.get_term_authority = _boom
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            _sup, degraded = _build_cjk_suppress({})
            res = _enforce("Ciri is strong.", "希里很强。")
    finally:
        term_enforcer.get_term_authority = orig
    if not degraded:
        return ("FAIL", "TA load failure produced no degradation warning")
    if not res.get("warnings"):
        return ("FAIL", "enforce_terms result missing warnings (degradation not in data)")
    return ("PASS", "M5: TA load failure -> degraded list + enforce_terms data.warnings")


def _t_m5_consumer_propagation() -> tuple[str, str]:
    """Degraded term_enforcer -> check_translation reports [checker warning], exit 1.

    Locks the CONSUMER side of M5 (the producer side is _t_m5_degradation_signal):
    when TermAuthority fails to load inside the term_enforcer subprocess, its
    data.warnings must surface in check_translation's output as a
    "[checker warning] term_enforcer degraded" issue that counts toward the
    issue total and the exit code — otherwise a degraded run reads as a false
    PASS. Degradation is triggered by appending a non-UTF-8 byte to the
    terminology_map.md of a TEMP COPY of scripts/ + references/ (scripts
    resolve references relative to __file__.parent.parent, so the copy is
    self-contained) — the tracked repo tree is never touched, so even SIGKILL
    mid-test cannot corrupt it.
    """
    lock = _lock_from("Ciri is strong.")  # built while references are healthy
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        shutil.copytree(SCRIPT_DIR, root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(SCRIPT_DIR.parent / "references", root / "references")
        (root / "references" / "terminology_map.md").write_bytes(b"\xff")  # non-UTF-8
        tp = root / "translated.txt"
        tp.write_text("这张卡很强。\n", encoding="utf-8")
        lp = root / "lock.json"
        lp.write_text(json.dumps(lock, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(root / "scripts" / "check_translation.py"),
             str(tp), "--lock", str(lp), "--direction", "encn", "--json"],
            capture_output=True, text=True, timeout=60)
    try:
        envelope = json.loads(r.stdout)
        issues = envelope["data"]["issues"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return ("FAIL", f"check_translation stdout not a clean JSON envelope: {e}: {r.stdout[:200]}")
    if not any("[checker warning]" in str(i.get("message", "")) for i in issues):
        return ("FAIL", f"degradation warning not propagated to consumer: {issues}")
    if r.returncode != 1:
        return ("FAIL", f"degraded run not counted toward exit code (exit {r.returncode})")
    return ("PASS", "M5 consumer: degraded term_enforcer -> [checker warning] issue + exit 1")


_TESTS = [
    _t_en_extraction,
    _t_cn_extraction,
    _t_false_lock_guard,
    _t_subsume_guard,
    _t_block_encn,
    _t_block_cnen,
    _t_cjk_absorb,
    _t_true_unknown,
    _t_h1_guard_fail_closed,
    _t_h1_guard_fail_closed_phase_c,
    _t_h2_fix_keeps_ta,
    _t_m9_guard_lock_build_fail,
    _t_m5_degradation_signal,
    _t_m5_consumer_propagation,
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
