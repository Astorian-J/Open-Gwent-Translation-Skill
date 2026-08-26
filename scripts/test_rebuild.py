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

from _shared import TermAuthority, build_lock_from_source, format_issue, parse_ta_envelope  # noqa: E402
from check_translation import check_term_authority_violations  # noqa: E402
import translate  # noqa: E402
from translate import _aggregate_violations, _card_db_status, _load_lock_terms  # noqa: E402
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
        # Ambiguous bases lock too (cn empty, variants non-empty) — a bare
        # "Avallac'h" resolves ambiguous since the base-priority fix.
        keys: set[str] = set()
        for r in ta.get_all_for_text(text):
            if r.get("canonical_en") and (r.get("cn") or r.get("variants")):
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


def _t_ambiguous_base_priority() -> tuple[str, str]:
    """Ambiguous bases resolve ambiguous even when the base is itself a card.

    Before the fix, the exact registry won for Regis/Dandelion/Ciri-style
    bases, pinning the gate to the BASE version and rejecting a
    context-chosen subtitle version (vampire context -> Regis: Bloodlust).
    Full names must keep resolving exactly.
    """
    ta = TermAuthority()

    for base in ("Regis", "Geralt", "Avallac'h"):
        r = ta.resolve(base)
        if not r or r.get("type") != "ambiguous" or not r.get("variants"):
            return ("FAIL", f"resolve({base!r}) -> {r and r.get('type')} (expected ambiguous with variants)")

    full = ta.resolve("Regis: Bloodlust")
    if not full or full.get("match_type") == "ambiguous_base" or not full.get("cn"):
        return ("FAIL", f"full name resolve degraded: {full}")

    # Gate-level: a context-chosen subtitle version satisfies the ambiguous
    # lock for a bare-base source mention.
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "s.md"
        src.write_text("Regis kept bleeding the opponent.\n", encoding="utf-8")
        lock_path = build_lock_from_source(src)
        lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
        regis = lock.get("terms", {}).get("Regis") or {}
        if regis.get("status") != "ambiguous" or len(regis.get("variants", [])) < 2:
            return ("FAIL", f"lock Regis status={regis.get('status')} variants={len(regis.get('variants', []))}")
        # The translation renders the context-chosen SUBTITLE version
        # (blood context -> Regis: Bloodlust). The ambiguous lock must
        # accept any official variant, not just the base 雷吉斯.
        out = Path(td) / "out.md"
        out.write_text("雷吉斯：血欲化身持续给对面挂重伤。\n", encoding="utf-8")
        res = enforce_terms(out, lock)
        viol_terms = [v.get("term") for v in res.get("violations", [])]
        if "Regis" in viol_terms:
            return ("FAIL", f"context-chosen variant rejected: {res.get('violations')}")
    return ("PASS", "Ambiguous base priority: bare base ambiguous, full name exact, variant accepted")


def _t_format_issue_shapes() -> tuple[str, str]:
    ta = format_issue({"term": "Avallac'h", "expected_official": "阿瓦拉克"})
    if "Avallac'h" not in ta or "阿瓦拉克" not in ta:
        return ("FAIL", f"TA shape lost fields: {ta!r}")
    cat = format_issue({"category": "provision_mix", "message": "12 provisions"})
    if "provision_mix" not in cat or "12 provisions" not in cat:
        return ("FAIL", f"category shape lost fields: {cat!r}")
    rule = format_issue({"rule_id": "encn-10", "message": "quote residue"})
    if "encn-10" not in rule or "quote residue" not in rule:
        return ("FAIL", f"rule_id shape lost fields: {rule!r}")
    if format_issue("bare") != "bare":
        return ("FAIL", "bare string not passed through")
    weird = format_issue({"weird": "shape"})
    if "weird" not in weird:
        return ("FAIL", f"unknown-dict fallback broken: {weird!r}")
    return ("PASS", "format_issue: 4 known shapes + unknown-dict fallback render")


def _t_lock_terms_filter() -> tuple[str, str]:
    lock = {"terms": {
        "Confirmed Card": {"canonical_en": "Confirmed Card", "cn": "已确认", "status": "confirmed"},
        "Auto Card": {"canonical_en": "Auto Card", "cn": "自动", "status": "auto_locked"},
        "Ambig": {"canonical_en": "Ambig", "cn": "", "status": "ambiguous"},
        "Pend": {"canonical_en": "Pend", "cn": "", "status": "pending"},
        "NoStatus": {"canonical_en": "NoStatus", "cn": "无状态"},
    }}
    with tempfile.TemporaryDirectory() as td:
        lp = Path(td) / "lock.json"
        lp.write_text(json.dumps(lock), encoding="utf-8")
        got = {t["canonical_en"] for t in _load_lock_terms(lp)}
    if got != {"Confirmed Card", "Auto Card"}:
        return ("FAIL", f"status filter wrong: {sorted(got)}")
    return ("PASS", "lock_terms filter: only confirmed/auto_locked kept (dict + list forms)")


def _t_violations_aggregation() -> tuple[str, str]:
    checks = [
        {"name": "term_authority", "passed": False, "issue_count": 2,
         "violations": [{"term": "T", "expected_official": "X"}], "issues": []},
        {"name": "terminology", "passed": False, "issue_count": 1,
         "issues": [{"category": "c", "message": "m"}, "bare"]},
        {"name": "file_exists", "passed": True, "issues": [{"message": "ignored"}]},
    ]
    out = _aggregate_violations(checks)
    tags = {v["check"] for v in out}
    if tags != {"term_authority", "terminology"}:
        return ("FAIL", f"failed-check filter/tags wrong: {sorted(tags)}")
    if len(out) != 3 or not any(v.get("term") == "T" for v in out) \
            or not any(v.get("message") == "bare" for v in out):
        return ("FAIL", f"aggregation contents wrong: {out}")
    return ("PASS", "violations aggregation: dual keys + check tag + bare wrap")


def _t_card_db_cache() -> tuple[str, str]:
    saved = translate._CARD_DB_CACHE
    try:
        translate._CARD_DB_CACHE = (1234, True)
        if _card_db_status() != (1234, True):
            return ("FAIL", "cache hit not honored")
        translate._CARD_DB_CACHE = None
        count, ready = _card_db_status()
        if translate._CARD_DB_CACHE is None:
            return ("FAIL", "fresh read did not repopulate cache")
        if ready != (count >= 1000):
            return ("FAIL", "readiness threshold mismatch")
    finally:
        translate._CARD_DB_CACHE = saved
    return ("PASS", "card_db cache: hit honored, miss repopulates")


def _t_parse_ta_envelope() -> tuple[str, str]:
    ok, n, v, err = parse_ta_envelope({"data": {"violation_count": 0, "violations": [], "warnings": []}})
    if not (ok and n == 0 and v == [] and err is None):
        return ("FAIL", f"clean envelope misread: ok={ok} n={n} err={err}")
    ok, n, v, err = parse_ta_envelope({"data": {"violation_count": 2, "violations": [{"term": "T"}, {"term": "U"}]}})
    if ok or n != 2 or len(v) != 2:
        return ("FAIL", f"violations envelope misread: ok={ok} n={n}")
    ok, n, v, err = parse_ta_envelope({"data": {"violation_count": 0, "violations": [], "warnings": ["references degraded"]}})
    if ok or n != 1 or v[0].get("term") != "[checker warning]":
        return ("FAIL", "degraded warning must flip to a counted violation")
    ok, n, v, err = parse_ta_envelope({"data": None, "errors": ["boom"]})
    if ok or err is None:
        return ("FAIL", "data:null error envelope must fail closed")
    ok, n, v, err = parse_ta_envelope("not-a-dict")
    if ok or err is None:
        return ("FAIL", "non-dict input must fail closed")
    return ("PASS", "parse_ta_envelope: clean/violations/degraded/crash shapes")


def _t_pipeline() -> tuple[str, str]:
    """End-to-end orchestration: prepare -> good/bad translation -> finish.

    Locks the BC34 bug class into an assertion: the substring card name
    "Avallac'h" (only occurring inside "Avallac'h: Sage") must NOT get a
    standalone lock row, and a correct translation must PASS finish while a
    residue+provision-reversed one must BLOCK with actionable violations.
    Runs against a throwaway copy of this repo (learn --auto writes runtime
    files and the last leg deletes the build-time card DB), so the working
    tree stays pristine. GWENT_CARD_DB points at an empty dir so a missing
    card DB fails closed OFFLINE (never the ~3-min online fetch).
    """
    import os
    import re as _re
    source_md = "Avallac'h: Sage sees play. Geralt: Igni costs 12 provisions for 8 points.\n"
    good_cn = "阿瓦拉克：贤者能上场。杰洛特：伊格尼法印是12人口8战力。\n"
    bad_cn = "Avallac'h: Sage sees play. 杰洛特：伊格尼法印是8战力12人口。\n"
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "skill"
        shutil.copytree(
            SCRIPT_DIR.parent, repo,
            ignore=shutil.ignore_patterns(".git", ".scratch", "__pycache__", "*.pyc"),
        )
        offline_db = Path(td) / "empty-card-db"
        offline_db.mkdir()
        env = {**os.environ, "GWENT_CARD_DB": str(offline_db)}
        src = repo / "pipeline_source.md"
        src.write_text(source_md, encoding="utf-8")

        def run(args_: list[str]) -> subprocess.CompletedProcess:
            return subprocess.run(
                [sys.executable, str(repo / "scripts" / "translate.py"), *args_],
                capture_output=True, text=True, timeout=300, env=env, cwd=str(repo),
            )

        # The copy carries this machine's gitignored card DB; a bare clone
        # would have none — fail with a pointer instead of a confusing
        # "prepare not ready: 0 cards".
        if not (repo / "references" / "card_names_4lang.json").exists():
            return ("FAIL", "card DB missing in this checkout — build first: "
                    "python scripts/build_card_names_reference.py --src ~/gwent-card-db "
                    "(or run install.sh)")

        # 1) prepare: ready + pack lock-table shape (full names locked, no
        #    standalone substring row — the _drop_subsumed regression)
        r = run(["prepare", str(src), "--json"])
        if r.returncode != 0:
            return ("FAIL", f"prepare exit {r.returncode}: {r.stdout[-200:]}")
        pdata = json.loads(r.stdout)["data"]
        if not pdata.get("ready") or not pdata.get("cards_ready"):
            return ("FAIL", f"prepare not ready: {pdata.get('card_db_count')} cards")
        pack = (repo / "pipeline_source.pack.md").read_text(encoding="utf-8")
        if "Geralt: Igni" not in pack:
            return ("FAIL", "pack missing full-name lock (Geralt: Igni)")
        # Scope to the MANDATORY lock table only — the quick-reference table
        # legitimately lists a base card AND its variants for lookup.
        mand = pack.split("MANDATORY Term Lock Table", 1)[1].split("\n## ", 1)[0]
        if _re.search(r"^\| Avallac'h \|", mand, _re.M):
            return ("FAIL", "MANDATORY table still carries a standalone Avallac'h row")

        # 2) finish on a correct translation -> PASS
        good = repo / "pipeline_good.md"
        good.write_text(good_cn, encoding="utf-8")
        r = run(["finish", str(good), "--source", str(src), "--direction", "encn", "--json"])
        if r.returncode != 0:
            return ("FAIL", f"finish(good) exit {r.returncode}: {r.stdout[-300:]}")

        # 2.5) pack/lock binding: a source edited after prepare BLOCKS, and
        # --allow-source-changed re-gates against a REBUILT lock — the stale
        # snapshot must NOT be reused (lock_reused False on that path).
        src.write_text(source_md + "An extra closing line.\n", encoding="utf-8")
        r = run(["finish", str(good), "--source", str(src), "--direction", "encn", "--json"])
        if r.returncode == 0 or "source changed" not in (json.loads(r.stdout)["data"].get("block_reason") or ""):
            return ("FAIL", "source-changed must BLOCK with a clear reason")
        r = run(["finish", str(good), "--source", str(src), "--direction", "encn",
                 "--allow-source-changed", "--json"])
        if r.returncode != 0:
            return ("FAIL", f"--allow-source-changed exit {r.returncode}: {r.stdout[-200:]}")
        if json.loads(r.stdout)["data"].get("lock_reused"):
            return ("FAIL", "--allow-source-changed must NOT reuse the stale snapshot")
        src.write_text(source_md, encoding="utf-8")

        # 3) finish on residue + provision-reversed translation -> BLOCKED
        #    with actionable violations
        bad = repo / "pipeline_bad.md"
        bad.write_text(bad_cn, encoding="utf-8")
        r = run(["finish", str(bad), "--source", str(src), "--direction", "encn", "--json"])
        if r.returncode == 0:
            return ("FAIL", "finish(bad) unexpectedly PASSED")
        fdata = json.loads(r.stdout)["data"]
        if not fdata.get("blocked"):
            return ("FAIL", "finish(bad) exit 1 but blocked flag not set")
        if not fdata.get("violations") or not fdata.get("violations_total"):
            return ("FAIL", "finish(bad) BLOCKED without actionable violation detail")

        # 4) card DB missing -> prepare fails closed (offline, never fetches)
        (repo / "references" / "card_names_4lang.json").unlink()
        r = run(["prepare", str(src), "--json"])
        if r.returncode == 0:
            return ("FAIL", "prepare PASSED with card DB missing (should fail closed)")
        mdata = json.loads(r.stdout).get("data") or {}
        if mdata.get("cards_ready", True):
            return ("FAIL", "cards_ready should be False when the card DB is missing")
    return ("PASS", "pipeline: prepare pack shape, good PASS, bad BLOCKED w/ detail, DB-missing fail-closed")


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
    _t_ambiguous_base_priority,
    _t_format_issue_shapes,
    _t_lock_terms_filter,
    _t_violations_aggregation,
    _t_card_db_cache,
    _t_parse_ta_envelope,
    _t_pipeline,
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
