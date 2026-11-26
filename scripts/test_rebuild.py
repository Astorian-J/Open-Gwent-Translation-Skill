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
  8. Direction             — the task direction is required everywhere and
                            reaches the lock; checkers act on it even when the
                            text suggests the other one; mixed-language sources
                            gate correctly; untranslated output cannot PASS"""

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

from _shared import TermAuthority, build_lock_from_source, format_issue, parse_ta_envelope, run_utf8  # noqa: E402
from check_translation import check_term_authority_violations  # noqa: E402
import translate  # noqa: E402
from translate import _aggregate_violations, _card_db_status, _load_lock_terms  # noqa: E402
from phase_c_check import check_context_lock_terms, run_phase_c_check  # noqa: E402
from term_enforcer import enforce_terms, count_occurrences, _build_cjk_suppress  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent

# The shape the pre-fix text heuristic misread: more English words (16) than Han
# characters (14), so a character-ratio guess took it for an English source and
# locked the English side of a CN->EN task. Purely Chinese sources, and mixes
# where the Han characters outnumber the English words, were read correctly even
# before the fix — only this shape tells a guesser from the stated direction.
MIXED_CN_SOURCE = (
    "Royal Decree, Golden Nekker, Roche: Cold Blood, Lacerate, Geralt: Igni, "
    "Villen: Whitehall Launch, Oneiromancy, Royal Commentator "
    "配上黄金孽鬼像和皇家谕令很稳。"
)
MIXED_EN_SOURCE = "孽鬼跳松 is strong in R1, use 黄金孽鬼像 to tutor for 皇家谕令."


def _lock_from(source_text: str, direction: str) -> dict:
    """Build a real context lock from synthetic source text (temp file)."""
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "source.md"
        p.write_text(source_text, encoding="utf-8")
        lp = build_lock_from_source(str(p), direction)
        try:
            return json.loads(lp.read_text(encoding="utf-8"))
        finally:
            lp.unlink(missing_ok=True)


def _enforce(source_text: str, translation_text: str, direction: str) -> dict:
    lock = _lock_from(source_text, direction)
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / "translated.txt"
        tp.write_text(translation_text, encoding="utf-8")
        return enforce_terms(tp, lock, direction)


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
        lock_path = build_lock_from_source(src, "encn")
        lock = json.loads(Path(lock_path).read_text(encoding="utf-8"))
        regis = lock.get("terms", {}).get("Regis") or {}
        if regis.get("status") != "ambiguous" or len(regis.get("variants", [])) < 2:
            return ("FAIL", f"lock Regis status={regis.get('status')} variants={len(regis.get('variants', []))}")
        # The translation renders the context-chosen SUBTITLE version
        # (blood context -> Regis: Bloodlust). The ambiguous lock must
        # accept any official variant, not just the base 雷吉斯.
        out = Path(td) / "out.md"
        out.write_text("雷吉斯：血欲化身持续给对面挂重伤。\n", encoding="utf-8")
        res = enforce_terms(out, lock, "encn")
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
            return run_utf8(
                [sys.executable, str(repo / "scripts" / "translate.py"), *args_],
                timeout=300, env=env, cwd=str(repo),
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
        r = run(["prepare", str(src), "--direction", "encn", "--json"])
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
        r = run(["prepare", str(src), "--direction", "encn", "--json"])
        if r.returncode == 0:
            return ("FAIL", "prepare PASSED with card DB missing (should fail closed)")
        mdata = json.loads(r.stdout).get("data") or {}
        if mdata.get("cards_ready", True):
            return ("FAIL", "cards_ready should be False when the card DB is missing")
    return ("PASS", "pipeline: prepare pack shape, good PASS, bad BLOCKED w/ detail, DB-missing fail-closed")


def _t_ambiguous_rebuild() -> tuple[str, str]:
    """2026-09 ambiguous_names.md rebuild invariants.

    (a) Roche (BC35 misidentification trap): bare base resolves ambiguous
        with BOTH cards as variants; full names stay exact.
    (b) Accented names: 'Dana Méadbh: Caretaker' extracts from EN text as
        one exact lock (extractor word classes include the À-ÿ range), and
        the accented group header parses (base 'Dana Méadbh' loads).
    (c) CN gate: a translation using bare 罗契 with no full version
        anywhere gets an ambiguous-name issue that names both candidates.
    """
    ta = TermAuthority()

    r = ta.resolve("Roche")
    variants = {(v["en"], v["cn"]) for v in (r or {}).get("variants", [])}
    if (r or {}).get("type") != "ambiguous" or \
            ("Vernon Roche", "弗农·罗契") not in variants or \
            ("Roche: Merciless", "罗契：冷酷之心") not in variants:
        return ("FAIL", f"resolve('Roche') -> {r}")
    full = ta.resolve("Roche: Merciless")
    if not full or full.get("match_type") != "exact" or full.get("cn") != "罗契：冷酷之心":
        return ("FAIL", f"resolve('Roche: Merciless') degraded: {full}")

    got = {t["canonical_en"]: t["match_type"]
           for t in ta.get_all_for_text("Dana Méadbh: Caretaker is underrated.")}
    if got.get("Dana Méadbh: Caretaker") != "exact":
        return ("FAIL", f"accented colon extraction: {got}")
    if "dana méadbh" not in ta._ambiguous:
        return ("FAIL", f"accented header not loaded, bases={sorted(ta._ambiguous)[:3]}...")

    got2 = {t["canonical_en"]: t["match_type"]
            for t in ta.get_all_for_text("Éibhear Hattori boosts artifacts.")}
    if got2.get("Éibhear Hattori") != "exact":
        return ("FAIL", f"accent-initial extraction: {got2}")

    from check_translation import check_translation
    issues, _ = check_translation(
        "罗契这个版本很强。",
        locked_phrases=set(),
        direction="encn",
        source_text="Roche is a strong pick this patch.",
    )
    amb = [i for i in issues if i.startswith("ambiguous name: 「罗契」") and "弗农·罗契" in i]
    if not amb:
        return ("FAIL", f"bare 罗契 not flagged, issues={issues}")
    issues_ok, _ = check_translation(
        "弗农·罗契这个版本很强。",
        locked_phrases=set(),
        direction="encn",
        source_text="Vernon Roche is a strong pick this patch.",
    )
    if any(i.startswith("ambiguous name:") for i in issues_ok):
        return ("FAIL", f"full name falsely flagged: {issues_ok}")
    return ("PASS", "Ambiguous rebuild: Roche both-variant resolve + accented extract + CN bare-name gate")


def _t_subprocess_utf8() -> tuple[str, str]:
    """run_utf8 pins UTF-8 on both sides of every child-process pipe.

    Windows regression (2026-09-01 user report): capture_output + text=True
    alone decodes child stdout with the platform locale — GBK on Chinese
    Windows — while our scripts emit UTF-8 (Chinese reference data, JSON
    envelopes), so prepare/finish crashed with UnicodeDecodeError. The
    first child writes raw UTF-8 bytes straight to the buffer, making the
    parent's decode choice the only variable (meaningful on any platform);
    the second asserts both halves of the env contract directly — the
    caller's env key survives layering AND the child's stdout encoding is
    forced to UTF-8 (reported by the child itself, so the assertion holds
    on GBK Windows and UTF-8 POSIX alike).
    """
    child_raw = "import sys; sys.stdout.buffer.write('中文锁定术语'.encode('utf-8'))"
    r = run_utf8([sys.executable, "-c", child_raw], timeout=30)
    if "中文锁定术语" not in (r.stdout or ""):
        return ("FAIL", f"parent decode not UTF-8: {r.stdout!r}")

    import os
    child_print = ("import os, sys; "
                   "print(os.environ.get('GWENT_TEST_MARKER', 'MISSING'), "
                   "sys.stdout.encoding)")
    custom_env = {**os.environ, "GWENT_TEST_MARKER": "1"}
    r2 = run_utf8([sys.executable, "-c", child_print], timeout=30, env=custom_env)
    out = (r2.stdout or "").strip()
    if "MISSING" in out or not out.startswith("1 "):
        return ("FAIL", f"caller env var lost under layering: {out!r}")
    if "utf-8" not in out.lower():
        return ("FAIL", f"child stdout encoding not forced: {out!r}")
    return ("PASS", "run_utf8: parent decodes UTF-8, child emits UTF-8 (env layered)")


def _t_lite_pack() -> tuple[str, str]:
    """prepare --lite: the chat pack drops article-grade sections; plain prepare keeps them.

    finish --lite never gates on balance direction / markdown format / official
    effect text / Phase C — a lite pack carrying them only pads what the model
    reads (and the Phase C checklist would ask the agent to self-check gates
    that never fire). The term lock content must be identical in both packs.
    """
    import os
    # Filter consistency: every LITE_STYLE label must exist in the full table
    # (a typo in a label would silently drop a style row from the lite pack),
    # and no label may repeat.
    for lite_labels, full_rows, name in (
        (translate.LITE_STYLE_ENC, translate.STYLE_ENC, "ENC"),
        (translate.LITE_STYLE_CN, translate.STYLE_CN, "CN"),
    ):
        full = {label for label, _ in full_rows}
        missing = [label for label in lite_labels if label not in full]
        if missing:
            return ("FAIL", f"LITE_STYLE_{name} label not in full style table: {missing}")
        if len(set(lite_labels)) != len(lite_labels):
            return ("FAIL", f"LITE_STYLE_{name} has duplicate labels")
    source_md = "Syndicate with double crossbreed is griefing, blue coin is unplayable into NG\n"
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "skill"
        shutil.copytree(
            SCRIPT_DIR.parent, repo,
            ignore=shutil.ignore_patterns(".git", ".scratch", "__pycache__", "*.pyc"),
        )
        offline_db = Path(td) / "empty-card-db"
        offline_db.mkdir()
        env = {**os.environ, "GWENT_CARD_DB": str(offline_db)}
        src = repo / "chat_source.md"
        src.write_text(source_md, encoding="utf-8")

        def run(args_: list[str]) -> subprocess.CompletedProcess:
            return run_utf8(
                [sys.executable, str(repo / "scripts" / "translate.py"), *args_],
                timeout=300, env=env, cwd=str(repo),
            )

        if not (repo / "references" / "card_names_4lang.json").exists():
            return ("FAIL", "card DB missing in this checkout — build first: "
                    "python scripts/build_card_names_reference.py --src ~/gwent-card-db "
                    "(or run install.sh)")

        # 1) lite prepare: ready, lite flag on, article sections gone, essentials kept
        r = run(["prepare", str(src), "--direction", "encn", "--lite", "--json"])
        if r.returncode != 0:
            return ("FAIL", f"prepare --lite exit {r.returncode}: {r.stdout[-200:]}")
        pdata = json.loads(r.stdout)["data"]
        if not pdata.get("ready"):
            return ("FAIL", f"lite prepare not ready: {pdata.get('card_db_count')} cards")
        if not pdata.get("lite"):
            return ("FAIL", "prepare --lite JSON missing lite=true")
        lite_pack = (repo / "chat_source.pack.md").read_text(encoding="utf-8")
        for gone in ("Balance Change Direction", "Markdown Format Preservation",
                     "Phase C Acceptance Checklist", "Official Effect Text"):
            if gone in lite_pack:
                return ("FAIL", f"lite pack still carries article-grade section: {gone}")
        for need in ("MANDATORY Term Lock Table", "blue coin", "NEXT STEP", "--lite"):
            if need not in lite_pack:
                return ("FAIL", f"lite pack missing essential: {need}")
        # style table is the filtered subset: chat rows present, article rows gone.
        # "Language" is the untranslated-output rule itself — the lite pack must
        # state it before the agent translates, not only the gate afterwards.
        for label in ("Language", "Tone", "Dash", "Colon", "Rhetoric"):
            if f"| {label} |" not in lite_pack:
                return ("FAIL", f"lite pack style table missing row: {label}")
        for label in ("Sentence length", "Style"):
            if f"| {label} |" in lite_pack:
                return ("FAIL", f"lite pack style table kept article-grade row: {label}")

        # 2) plain prepare on the same source keeps the article-grade sections
        r = run(["prepare", str(src), "--direction", "encn", "--json"])
        if r.returncode != 0:
            return ("FAIL", f"plain prepare exit {r.returncode}: {r.stdout[-200:]}")
        if json.loads(r.stdout)["data"].get("lite"):
            return ("FAIL", "plain prepare must not set lite=true")
        full_pack = (repo / "chat_source.pack.md").read_text(encoding="utf-8")
        for keep in ("Balance Change Direction", "Markdown Format Preservation",
                     "Phase C Acceptance Checklist", "| Sentence length |"):
            if keep not in full_pack:
                return ("FAIL", f"plain pack lost article-grade section: {keep}")
        # the lite trim must not touch the lock: the same terms stay mandatory
        for term in ("blue coin", "Syndicate", "Nilfgaard"):
            if term not in lite_pack:
                return ("FAIL", f"lite pack lost locked term: {term}")
    return ("PASS", "lite pack: article sections dropped, lock intact; plain pack unchanged")


def _t_lookup_card_db() -> tuple[str, str]:
    """lookup.py must search the 1381-card DB (plain card names live ONLY there).

    The markdown reference tables carry terms/slang/keywords but not plain card
    names; without the card-DB search a lookup for a plain card name finds
    nothing — which made the "look up suspicious proper nouns" rule weaker than
    advertised (flash's table-first fallback and lite's term rule both lean on it).
    """
    if not (SCRIPT_DIR.parent / "references" / "card_names_4lang.json").exists():
        return ("FAIL", "card DB missing in this checkout — build first: "
                "python scripts/build_card_names_reference.py --src ~/gwent-card-db "
                "(or run install.sh)")

    def lookup(q: str, *extra: str) -> dict:
        r = run_utf8(
            [sys.executable, str(SCRIPT_DIR / "lookup.py"), q, "--json", *extra],
            timeout=60)
        return json.loads(r.stdout)

    exact = lookup("Villentretenmerth")
    cards = [x for x in exact["data"]["results"] if x["file"] == "card_names_4lang.json"]
    if exact["exit_code"] != 0 or not cards:
        return ("FAIL", "exact EN card name not found in card DB")
    if cards[0]["row"].get("cn") != "维伦特瑞坦梅斯":
        return ("FAIL", f"wrong CN rendering: {cards[0]['row'].get('cn')}")

    cn = lookup("希里")
    cards = [x for x in cn["data"]["results"] if x["file"] == "card_names_4lang.json"]
    if not cards or cards[0]["score"] != 1.0 or cards[0]["row"].get("en") != "Ciri":
        return ("FAIL", "CN query did not exact-match Ciri in card DB")
    # merged sources: a CN query must hit BOTH the md tables and the card DB
    if not any(x["file"] == "ambiguous_names.md" for x in cn["data"]["results"]):
        return ("FAIL", "card DB hits crowded out markdown-table hits (merge broken)")
    return ("PASS", "lookup card DB: exact EN + CN queries hit the 1381-card corpus, md+DB merged")


def _t_repair_tracking() -> tuple[str, str]:
    """finish repair-regression tracking: baseline -> REGRESS across renamed
    output -> PASS clears the baseline.

    The strict-subset borrow (llm-translation-poc): a sloppy repair that fixes
    some violations while introducing new ones must be VISIBLE, and the
    baseline must key on the SOURCE so round 2 saved under a new filename is
    still tracked."""
    import os
    source_md = "Ciri and Scorch are strong. Iorveth sees play.\n"
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "skill"
        shutil.copytree(
            SCRIPT_DIR.parent, repo,
            ignore=shutil.ignore_patterns(".git", ".scratch", "__pycache__", "*.pyc"),
        )
        env = {**os.environ, "GWENT_CARD_DB": str(Path(td) / "unused")}
        src = repo / "repair_source.md"
        src.write_text(source_md, encoding="utf-8")

        def run(args_):
            return run_utf8(
                [sys.executable, str(repo / "scripts" / "translate.py"), *args_],
                timeout=300, env=env, cwd=str(repo),
            )

        if run(["prepare", str(src), "--direction", "encn"]).returncode != 0:
            return ("FAIL", "prepare failed")
        # R1: everything untranslated -> BLOCKED, baseline written
        bad1 = repo / "r1.md"
        bad1.write_text("这张卡很强。\n", encoding="utf-8")
        r = run(["finish", str(bad1), "--source", str(src), "--direction", "encn", "--json"])
        d1 = json.loads(r.stdout)["data"]
        if not d1["blocked"] or d1["repair_tracking"] is not None:
            return ("FAIL", f"R1 must BLOCK with no tracking: {d1.get('violations_total')}")
        if not (repo / "repair_source.gate.json").exists():
            return ("FAIL", "R1 did not write the gate baseline")
        # R2: fixed two names but introduced a new untranslated one -> REGRESS
        bad2 = repo / "r2.md"
        bad2.write_text("希里和烧灼都很强。Vernon Roche 很强。\n", encoding="utf-8")
        r = run(["finish", str(bad2), "--source", str(src), "--direction", "encn", "--json"])
        t = json.loads(r.stdout)["data"]["repair_tracking"]
        if not t or t["regressed_count"] < 1 or t["fixed_count"] < 1:
            return ("FAIL", f"R2 must show fixed+regressed across renamed file: {t}")
        # R3: fully correct -> PASS, baseline cleared
        good = repo / "r3.md"
        good.write_text("希里和烧灼都很强。伊欧菲斯能上场。\n", encoding="utf-8")
        r = run(["finish", str(good), "--source", str(src), "--direction", "encn", "--json"])
        d3 = json.loads(r.stdout)["data"]
        if d3["blocked"] or (repo / "repair_source.gate.json").exists():
            return ("FAIL", "R3 must PASS and clear the gate baseline")
    return ("PASS", "repair tracking: baseline -> REGRESS (renamed file) -> PASS clears")


def _t_new_format_checks() -> tuple[str, str]:
    """Source-aware structural checks: protected tokens (URL/code), bold total
    loss, severe omission; empty translation without a source."""
    from check_translation import check_translation
    src = ("Geralt: Igni costs 12 provisions. See https://example.com/a and `Deploy:`.\n"
           "\n**Balance** changed twice.\n\nLine three content here.\nLine four content here.\n")
    lossy = "这张卡很强，没提任何东西。"
    issues, _ = check_translation(lossy, direction="encn", source_text=src)
    cats = {i.split(":")[0] for i in issues}
    for need in ("protected token", "format", "completeness"):
        if need not in cats:
            return ("FAIL", f"lossy translation missed {need}: {sorted(cats)}")
    empty_issues, _ = check_translation("   \n", direction="encn")
    if not any(i.startswith("empty:") for i in empty_issues):
        return ("FAIL", f"empty translation not flagged: {empty_issues}")
    return ("PASS", "format checks: protected token / bold loss / omission / empty all fire")


def _t_block_encn() -> tuple[str, str]:
    wrong = _enforce("Ciri and Scorch are strong.", "这张卡很强，没提任何卡名。", "encn")
    right = _enforce("Ciri and Scorch are strong.", "希里和烧灼都很强。", "encn")
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
    wrong = _enforce("希里与烧灼是核心卡。", "This output drops every card name.", "cnen")
    right = _enforce("希里与烧灼是核心卡。", "Ciri and Scorch are core cards.", "cnen")
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
        crashed = check_term_authority_violations(tp, lock_path=bad, direction="encn")
        # --source on a missing file: term_enforcer exits 1 with a
        # "data": null error envelope (key present, value null).
        null_env = check_term_authority_violations(
            tp, source_path=Path("/tmp/definitely-not-exist-src.md"), direction="encn")
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
        crashed = check_context_lock_terms(tp, lock_path=bad, direction="encn")
        null_env = check_context_lock_terms(
            tp, source_path=Path("/tmp/definitely-not-exist-src.md"), direction="encn")
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
        r = run_utf8(
            [sys.executable, str(SCRIPT_DIR / "check_translation.py"),
             str(trans), "--source", str(src), "--fix", "--direction", "encn"],
            timeout=60)
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
        r = run_utf8(
            [sys.executable, str(SCRIPT_DIR / "completeness_guard.py"),
             str(trans), "--source", str(bad_source), "--direction", "encn", "--json"],
            timeout=120)
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
            res = _enforce("Ciri is strong.", "希里很强。", "encn")
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
    lock = _lock_from("Ciri is strong.", "encn")  # built while references are healthy
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
        r = run_utf8(
            [sys.executable, str(root / "scripts" / "check_translation.py"),
             str(tp), "--lock", str(lp), "--direction", "encn", "--json"],
            timeout=60)
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


def _t_subprocess_timeout_str() -> tuple[str, str]:
    """C1: run_utf8 normalizes TimeoutExpired.stdout/.stderr to str.

    POSIX raises TimeoutExpired with partial output as undecoded BYTES (only
    the Windows branch backfills decoded str); both run_script* handlers
    concatenate e.stdout into str diagnostics, so a child that wrote anything
    before hanging crashed the handler itself (TypeError) instead of
    reporting "[timeout]". Locks the single-point normalization in run_utf8.

    Platform scope: the bytes-vs-str distinction only exists on POSIX — on
    Windows this test passes with or without the normalization (the bug was
    never there), so this is a POSIX-side guard, not a cross-platform one.
    """
    child = ("import sys, time; "
             "print('partial输出', flush=True); "
             "print('err部分', file=sys.stderr, flush=True); "
             "time.sleep(30)")
    try:
        run_utf8([sys.executable, "-c", child], timeout=1)
    except subprocess.TimeoutExpired as e:
        if not isinstance(e.stdout, str) or not isinstance(e.stderr, str):
            return ("FAIL",
                    f"TimeoutExpired output not str: stdout={type(e.stdout).__name__}, "
                    f"stderr={type(e.stderr).__name__}")
        if "partial输出" not in e.stdout or "err部分" not in e.stderr:
            return ("FAIL",
                    f"partial output lost: stdout={e.stdout!r} stderr={e.stderr!r}")
        return ("PASS", "C1: TimeoutExpired stdout/stderr normalized to str, partial output intact")
    return ("FAIL", "run_utf8 did not raise TimeoutExpired for a sleeping child")


def _t_phase_c_ambiguous_direction() -> tuple[str, str]:
    """I1: encn-06 forwards the task direction into check_translation.

    The direction is a required parameter that is never inferred, so the
    ambiguous gate inside check_ambiguous_names can only run for the task's
    direction. Locks the forwarding: on heavily mixed text (English prose
    around a short Chinese fragment) bare "Roche" (two cards share the base
    name) must be flagged when the direction is encn.
    """
    text = "Roche is great. " * 40 + "罗契很强。"
    issues, _manual = run_phase_c_check(
        text, "encn", SCRIPT_DIR.parent / "references")
    if not any("ambiguous name:" in i for i in issues):
        return ("FAIL", f"encn-06 silent on mixed text with explicit encn: {issues}")
    return ("PASS", "I1: encn-06 ambiguous gate fires on mixed text under explicit encn")


def _t_direction_required() -> tuple[str, str]:
    """D1: every direction-taking command rejects a missing --direction (exit 2).

    Direction is the task's own parameter. It used to be inferred from the
    text by a character-ratio heuristic, which reads a Chinese source full of
    English card names as English — prepare then built an EN->CN pack and the
    gate pushed the translation toward Chinese. A missing direction must be an
    argument error, never a guess.
    """
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "source.md"
        src.write_text("Golden Nekker, Royal Decree, Roche: Cold Blood, Lacerate, "
                       "Geralt: Igni 这套很稳。\n", encoding="utf-8")
        lock = Path(td) / "lock.json"
        lock.write_text('{"document": "", "terms": {}}', encoding="utf-8")
        cases = [
            ("translate.py", ["prepare", str(src)]),
            ("translate.py", ["finish", str(src), "--source", str(src)]),
            ("translate.py", ["run", str(src)]),
            ("auto_pipeline.py", ["pre", str(src)]),
            ("auto_pipeline.py", ["scan", str(src)]),
            ("context_lock.py", ["build", str(src), "--output", str(Path(td) / "out.json")]),
            ("context_lock.py", ["check", str(src), "--lock", str(lock)]),
            ("term_enforcer.py", [str(src), "--source", str(src)]),
            ("check_translation.py", [str(src)]),
            ("phase_c_check.py", [str(src)]),
            ("completeness_guard.py", [str(src)]),
            ("diff_review.py", [str(src), str(src)]),
        ]
        for script, args_ in cases:
            r = run_utf8([sys.executable, str(SCRIPT_DIR / script), *args_], timeout=60)
            if r.returncode != 2 or "--direction" not in (r.stderr or ""):
                return ("FAIL", f"{script} {args_[0]}: missing --direction not rejected "
                                f"(exit {r.returncode}): {(r.stderr or r.stdout)[-160:]}")
        if src.with_name("source.pack.md").exists():
            return ("FAIL", "a pack was written although --direction was missing")

    # The doc guard judges commands where commands are written, and only there.
    import health_check

    def lacking(text: str) -> list[str]:
        return health_check._commands_lacking_direction(text)[0]

    # Each entry is a documented command without --direction and must be caught.
    # (The second one is the shape SKILL.md's own examples use: a code fence
    # inside a blockquote.)
    caught = [
        "```\npython scripts/translate.py prepare source.md\n```",
        "> ```bash\n> # 0. a comment line\n> python scripts/translate.py finish translated.txt --source source.md\n> ```",
        "run `context_lock.py check translated.txt --lock lock.json` first",
        '| 1 | `translate.py prepare source.md --type general` | x |',
        '```\n"$PY" scripts/auto_pipeline.py scan translated.txt\n```',
        "```\npy scripts/translate.py prepare source.md\n```",
        "```\npython3 -B scripts/translate.py prepare source.md # TODO pass --direction\n```",
        "```\npython scripts/translate.py prepare source.md\t# --direction\n```",
        "```\npython3 -m scripts.translate prepare source.md\n```",
        "```\n./scripts/check_translation.py translated.txt\n```",
        "```\npython scripts/translate.py prepare s.md --direction encn && "
        "python scripts/translate.py finish t.txt --source s.md\n```",
        "```\npython scripts/translate.py prepare source.md, then finish with the same --direction.\n```",
        "```\npython scripts/translate.py prepare source.md, then "
        "python scripts/translate.py finish t.txt --direction encn\n```",
        # A comma before the script name must neither crash the guard nor
        # hide the command: inside a token it is ignored, and after a prose
        # comma the rest of the line is judged as its own command.
        "```\n./skill,v2/scripts/translate.py prepare source.md\n```",
        "```\npython a,b/translate.py prepare source.md\n```",
        "```\npython a, b/translate.py prepare source.md\n```",
        # A comment that is itself a commented-out command is still a command,
        # and a commented-out command line is judged like any command line:
        # every command on it, indented or not, inside a fence or an indented block.
        "```\n# python scripts/translate.py prepare source.md\n```",
        "```\n# python scripts/translate.py prepare source.md --direction encn; "
        "python scripts/translate.py finish t.txt --source s.md\n```",
        "```\n    # python scripts/translate.py prepare source.md\n```",
        "Intro:\n\n    # python scripts/translate.py prepare source.md\n\nOutro.",
        # The module form is read on every command of a line, not only the first.
        "```\npython3 -m scripts.translate prepare s.md --direction encn && "
        "python3 -m scripts.translate finish t.txt --source s.md\n```",
        # An apostrophe that never closes is not a quote: the comment is stripped.
        "```\npython scripts/translate.py prepare O'Brien.md  # add --direction\n```",
        # Indented code blocks and backtick spans with a text prefix are commands too.
        "Intro:\n\n    python scripts/translate.py prepare source.md\n\nOutro.",
        "> Intro:\n>\n>     python scripts/translate.py prepare source.md",
        "the `old: python scripts/translate.py prepare source.md` call",
        # A 3-backtick line does not close a 4-backtick fence.
        "````\n```\n````\n\n```python\npython scripts/translate.py prepare source.md\n```",
    ]
    for text in caught:
        if not lacking(text):
            return ("FAIL", f"doc guard let a command without --direction through: {text[:70]!r}")
    # None of these states a violating command and none may be reported.
    allowed = [
        "Without --direction, python scripts/translate.py prepare exits with code 2.",
        "Before this fix, python scripts/translate.py prepare source.md guessed the direction.",
        "```\npython scripts/translate.py prepare \"my #1 deck.md\" --direction encn\n```",
        '```\npython scripts/context_lock.py add "English Term" "中文翻译" --lock /tmp/lock.json\n```',
        "run `translate.py finish` after translating",
        "```\npython scripts/backtranslate.py source.txt translated.txt back.txt\n```",
        '```\npython3 "$SK/scripts/translate.py" prepare /tmp/a.md --direction encn --lite && \\\n'
        "cat /tmp/a.pack.md\n```",
        # A reference that only names the script and its options is not a command.
        "use `check_translation.py --fix` to repair",
        # A comment that talks about a command is prose — whatever separators
        # it holds: the marker is read before the line is split into commands,
        # so a command after the separator is still inside the comment.
        "```\n# this replaces the old python scripts/translate.py prepare source.md call\n```",
        "```\n# step 1; python scripts/translate.py prepare source.md\n```",
        "```\n# step 1 && python scripts/translate.py finish t.txt --source s.md\n```",
        "```\n# step 1 | python scripts/translate.py finish t.txt --source s.md\n```",
        # A comma inside an argument does not end the command.
        "```\npython scripts/translate.py prepare source.md --date 2026-05,2026-06 --direction encn\n```",
        # A trailing comment runs to the end of the line, separators included:
        # a command it mentions is not judged, in a fence or an indented block.
        "```\npython scripts/translate.py prepare source.md --direction encn  # old form; "
        "python scripts/translate.py prepare source.md\n```",
        "```\npython scripts/translate.py prepare source.md --direction encn  # old form | "
        "python scripts/translate.py prepare source.md\n```",
        "Intro:\n\n    python scripts/translate.py prepare source.md --direction encn  # old form; "
        "python scripts/translate.py prepare source.md\n\nOutro.",
        "```\n# python scripts/translate.py prepare source.md --direction encn  # old form; "
        "python scripts/translate.py finish t.txt\n```",
        # An interpreter flag ending in a prose comma cuts the match short of
        # the script name: no readable command, so skipped — never crashed on.
        "```\npython -x, scripts/translate.py prepare source.md\n```",
    ]
    for text in allowed:
        if lacking(text):
            return ("FAIL", f"doc guard reported a non-violating text: {text[:70]!r} -> {lacking(text)}")
    return ("PASS", "D1: all 12 direction-taking commands reject a missing --direction (exit 2); "
                     "the doc guard judges commands where they are written")


def _t_direction_reaches_lock() -> tuple[str, str]:
    """D2: the stated direction selects how the source is extracted; the lock itself carries none.

    On MIXED_CN_SOURCE a CN->EN task must lock the Chinese side (皇家谕令 /
    黄金孽鬼像 → official English) while an EN->CN task locks the English side of
    the very same text. A build_lock that ignores `direction` and guesses from the
    text locks the English side for both and fails here.
    """
    cn_lock = _lock_from(MIXED_CN_SOURCE, "cnen")
    en_lock = _lock_from(MIXED_CN_SOURCE, "encn")
    cn_terms, en_terms = cn_lock.get("terms", {}), en_lock.get("terms", {})
    for cn, en in (("黄金孽鬼像", "Golden Nekker"), ("皇家谕令", "Royal Decree")):
        info = cn_terms.get(cn) or {}
        if info.get("canonical_en") != en or info.get("status") != "auto_locked":
            return ("FAIL", f"cnen lock lost {cn}->{en}: {info or sorted(cn_terms)}")
    if "Golden Nekker" not in en_terms or "皇家谕令" in en_terms:
        return ("FAIL", f"encn lock must be keyed by the English side: {sorted(en_terms)}")
    if "direction" in cn_lock or "direction" in en_lock:
        return ("FAIL", "lock still carries a direction field (a second source of truth beside --direction)")
    return ("PASS", "D2: --direction selects the extraction side on the misread mixed source; "
                     "the lock carries no direction of its own")


def _t_direction_mixed_sources() -> tuple[str, str]:
    """D3 (the reported bug), end to end on the misread mixed source.

    prepare --direction cnen must lock the Chinese side — so term authority has
    something to enforce — gate a correct English translation as PASS (it used
    to be BLOCKED with "expected 黄金孽鬼像"), and BLOCK the source returned
    untranslated, whether verbatim or with the card names swapped and the
    punctuation normalized. finish must refuse a snapshot prepared for another
    direction, with or without --allow-source-changed, and one that records no
    direction at all. The mirror case (EN->CN on an English source with Chinese
    card names) gates a correct Chinese translation as PASS and the source as-is
    as BLOCKED.
    """
    import os
    good_en = ("Royal Decree, Golden Nekker, Roche: Cold Blood, Lacerate, Geralt: Igni, "
               "Villen: Whitehall Launch, Oneiromancy and Royal Commentator with "
               "Golden Nekker and Royal Decree is really solid.\n")
    near_copy = ("Royal Decree, Golden Nekker, Roche: Cold Blood, Lacerate, Geralt: Igni, "
                 "Villen: Whitehall Launch, Oneiromancy, Royal Commentator 配上和很稳!\n")
    good_cn = "孽鬼跳松第一小局很强，用黄金孽鬼像检索皇家谕令。\n"
    with tempfile.TemporaryDirectory() as td:
        # scripts/ + references/ are self-contained (references resolve
        # relative to __file__), so the copy stays small.
        repo = Path(td) / "skill"
        shutil.copytree(SCRIPT_DIR, repo / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(SCRIPT_DIR.parent / "references", repo / "references")
        if not (repo / "references" / "card_names_4lang.json").exists():
            return ("FAIL", "card DB missing in this checkout — build first: "
                            "python scripts/build_card_names_reference.py --src ~/gwent-card-db "
                            "(or run install.sh)")
        env = {**os.environ, "GWENT_CARD_DB": str(Path(td) / "empty-card-db")}
        t = repo / "scripts" / "translate.py"

        def run(*args_: str) -> subprocess.CompletedProcess:
            return run_utf8([sys.executable, str(t), *args_], timeout=300, env=env, cwd=str(repo))

        def finish(translation: str, src: Path, direction: str, *extra: str) -> dict:
            out_file = repo / "out.md"
            out_file.write_text(translation, encoding="utf-8")
            r = run("finish", str(out_file), "--source", str(src), "--direction", direction,
                    "--lite", "--json", *extra)
            return json.loads(r.stdout)["data"]

        def untranslated(data: dict) -> list[str]:
            return [v["message"] for v in data.get("violations", []) if v.get("category") == "untranslated"]

        def refused(data: dict, reason: str) -> str:
            """Return "" when the snapshot was refused for `reason`, else a failure message."""
            if not data.get("blocked") or data.get("lock_reused"):
                return f"snapshot not refused: reused={data.get('lock_reused')} reason={data.get('block_reason')}"
            if reason not in (data.get("block_reason") or ""):
                return f"wrong reason: {data.get('block_reason')}"
            if "repair_tracking" not in data:
                return "early-exit JSON lacks the repair_tracking key of the normal path"
            return ""

        src = repo / "mixed_cn.md"
        src.write_text(MIXED_CN_SOURCE + "\n", encoding="utf-8")
        r = run("prepare", str(src), "--direction", "cnen", "--lite", "--json")
        pdata = json.loads(r.stdout)["data"]
        if r.returncode != 0 or not pdata.get("ready"):
            return ("FAIL", f"prepare cnen not ready: exit {r.returncode}: {r.stdout[-200:]}")
        if pdata.get("direction") != "cnen" or "direction_auto_detected" in pdata:
            return ("FAIL", f"prepare direction fields wrong: {pdata.get('direction')}")
        if pdata.get("term_counts", {}).get("locked", 0) < 2:
            return ("FAIL", f"cnen lock is empty on the mixed source, term authority would check "
                            f"nothing: {pdata.get('term_counts')}")
        pack = src.with_name("mixed_cn.pack.md").read_text(encoding="utf-8")
        if "**Direction**: CN -> EN" not in pack:
            return ("FAIL", "pack is not a CN->EN pack for the mixed Chinese source")
        sidecar_path = src.with_name("mixed_cn.lock.json")
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        if sidecar.get("_prepare_meta", {}).get("direction") != "cnen":
            return ("FAIL", f"prepare snapshot does not record the direction: {sidecar.get('_prepare_meta')}")

        # a correct English translation PASSes (used to be BLOCKED)
        fdata = finish(good_en, src, "cnen")
        if fdata.get("blocked"):
            return ("FAIL", f"correct EN translation BLOCKED: {fdata.get('violations', [])[:3]}")

        # untranslated output is BLOCKED: verbatim, and the realistic near-copy
        for name, out in (("verbatim", MIXED_CN_SOURCE + "\n"),
                          ("card names swapped, punctuation normalized", near_copy)):
            fdata = finish(out, src, "cnen")
            if not fdata.get("blocked") or not untranslated(fdata):
                return ("FAIL", f"untranslated output ({name}) not blocked: {fdata.get('violations', [])[:3]}")

        # finish for the other direction refuses the snapshot; --allow-source-changed cannot bypass that
        for extra in ((), ("--allow-source-changed",)):
            problem = refused(finish(good_en, src, "encn", *extra), "was prepared for CN->EN")
            if problem:
                return ("FAIL", f"other-direction finish {extra}: {problem}")

        # a snapshot that records no direction (made before directions were recorded, or by hand) is never reused
        sidecar_sha = sidecar["_prepare_meta"]["source_sha256"]
        sidecar["_prepare_meta"] = {"source_sha256": sidecar_sha}
        sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False), encoding="utf-8")
        problem = refused(finish(good_en, src, "cnen"), "records no direction")
        if problem:
            return ("FAIL", f"directionless snapshot: {problem}")

        # ...and one whose direction is not a direction name is refused the same way, not crashed on
        sidecar["_prepare_meta"] = {"source_sha256": sidecar_sha, "direction": ["cnen"]}
        sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False), encoding="utf-8")
        problem = refused(finish(good_en, src, "cnen"), "records no direction")
        if problem:
            return ("FAIL", f"malformed-direction snapshot: {problem}")

        # re-running prepare restores the PASS
        run("prepare", str(src), "--direction", "cnen", "--lite", "--json")
        fdata = finish(good_en, src, "cnen")
        if fdata.get("blocked") or not fdata.get("lock_reused"):
            return ("FAIL", f"re-prepare did not restore PASS with the snapshot reused: "
                            f"reused={fdata.get('lock_reused')} {fdata.get('violations', [])[:3]}")

        # mirror: EN->CN on an English source with Chinese card names
        src2 = repo / "mixed_en.md"
        src2.write_text(MIXED_EN_SOURCE + "\n", encoding="utf-8")
        r = run("prepare", str(src2), "--direction", "encn", "--lite", "--json")
        if r.returncode != 0:
            return ("FAIL", f"prepare encn not ready: exit {r.returncode}: {r.stdout[-200:]}")
        fdata = finish(good_cn, src2, "encn")
        if fdata.get("blocked"):
            return ("FAIL", f"correct CN translation BLOCKED: {fdata.get('violations', [])[:3]}")
        fdata = finish(MIXED_EN_SOURCE + "\n", src2, "encn")
        if not fdata.get("blocked") or not untranslated(fdata):
            return ("FAIL", f"untranslated EN source not blocked: {fdata.get('violations', [])[:3]}")

        # The repair loop must see progress, never a regression: one violation
        # per leftover run keeps the untouched runs' messages unchanged.
        src3 = repo / "repair.md"
        src3.write_text("这套卡组很稳。推荐大家试试。下把继续。\n", encoding="utf-8")
        run("prepare", str(src3), "--direction", "cnen", "--lite", "--json")
        fdata = finish("This deck is really solid. 推荐大家试试。下把继续。\n", src3, "cnen")
        first_round = untranslated(fdata)
        if len(first_round) != 2:
            return ("FAIL", f"two leftover runs must give two untranslated violations: {first_round}")
        fdata = finish("This deck is really solid. Give it a try. 下把继续。\n", src3, "cnen")
        tracking = fdata.get("repair_tracking") or {}
        if tracking.get("regressed_count") != 0 or tracking.get("fixed_count") != 1:
            return ("FAIL", f"fixing one leftover must read as progress, not a regression: {tracking}")
        if untranslated(fdata) != first_round[1:]:
            return ("FAIL", f"the untouched leftover's message changed: {untranslated(fdata)}")

        # Crossing the listing limit must still read as progress: runs that were
        # summed up last round and are listed this round are not regressions.
        # (Chinese numerals keep each run distinct: a digit would split a run
        # in two, and identical messages are deduplicated.)
        digits = "零一二三四五六七八九"

        def chinese(n: int) -> str:
            tens, ones = divmod(n, 10)
            return (digits[tens] if tens > 1 else "") + ("十" if tens else "") + (digits[ones] if ones or not tens else "")

        from check_translation import UNTRANSLATED_RUN_LISTING_LIMIT
        runs = [f"第{chinese(i)}段没有翻译" for i in range(UNTRANSLATED_RUN_LISTING_LIMIT + 5)]
        if len(set(runs)) != len(runs):
            return ("FAIL", "test data: leftover runs are not distinct")
        src4 = repo / "many.md"
        src4.write_text("".join(f"{run}。" for run in runs) + "\n", encoding="utf-8")
        run("prepare", str(src4), "--direction", "cnen", "--lite", "--json")
        round_one = finish("All of it is translated. " + " ".join(runs) + "!\n", src4, "cnen")
        if len(untranslated(round_one)) != UNTRANSLATED_RUN_LISTING_LIMIT + 1:
            return ("FAIL", f"above the limit: {UNTRANSLATED_RUN_LISTING_LIMIT} listed + 1 summary expected, "
                            f"got {len(untranslated(round_one))}")
        fdata = finish("All of it is translated. " + " ".join(runs[6:]) + "!\n", src4, "cnen")
        tracking = fdata.get("repair_tracking") or {}
        if tracking.get("regressed_count") != 0 or tracking.get("fixed_count", 0) < 6:
            return ("FAIL", f"crossing the listing limit must read as progress: {tracking}")
        remaining = len(runs) - 6
        if len(untranslated(fdata)) != remaining:
            return ("FAIL", f"{remaining} leftover runs are under the limit and are all listed: "
                            f"{len(untranslated(fdata))} listed")

        # The exemption is for the truncated listing only. When everything was
        # listed last round, an edit that adds leftovers is a regression.
        src5 = repo / "regress.md"
        src5.write_text("这套卡组很稳。推荐大家试试。下把继续。\n", encoding="utf-8")
        run("prepare", str(src5), "--direction", "cnen", "--lite", "--json")
        finish("This deck is really solid. 推荐大家试试。下把继续。\n", src5, "cnen")
        # (the original two leftovers stay, so nothing counts as fixed)
        worse = ("This deck is really solid. 推荐大家试试。下把继续。"
                 + " ".join(f"第{chinese(i)}段新添的中文" for i in range(40)))
        fdata = finish(worse, src5, "cnen")
        tracking = fdata.get("repair_tracking") or {}
        if tracking.get("regressed_count", 0) < 1 or tracking.get("fixed_count") != 0:
            return ("FAIL", f"an edit that adds leftovers must be reported as a regression: {tracking}")

        # diff_review forwards the stated direction instead of assuming one: the
        # same English output is a translation for a CN->EN pair and an
        # untranslated output for an EN->CN pair.
        pair_src = repo / "review_src.md"
        pair_src.write_text("黄金孽鬼像配皇家谕令很稳。\n", encoding="utf-8")
        pair_out = repo / "review_out.md"
        pair_out.write_text("Golden Nekker with Royal Decree is really solid.\n", encoding="utf-8")
        for direction, untranslated_expected in (("cnen", False), ("encn", True)):
            r = run_utf8([sys.executable, str(repo / "scripts" / "diff_review.py"), str(pair_src),
                          str(pair_out), "--direction", direction, "--json"],
                         timeout=60, env=env, cwd=str(repo))
            issue_types = {i["type"] for i in json.loads(r.stdout)["data"]["issues"]}
            if ("untranslated" in issue_types) != untranslated_expected:
                return ("FAIL", f"diff_review --direction {direction} judged the pair as the other "
                                f"direction: {sorted(issue_types)}")
    return ("PASS", "D3: mixed-language sources gate correctly for the stated direction; "
                     "other-direction and directionless snapshots refused")


def _t_untranslated_output() -> tuple[str, str]:
    """D4: an output still in the source language, or a copy of the source, is BLOCKED.

    Given the direction, the gate checks the reverse: does the output read as
    the TARGET language? CN->EN convicts on any Han character outside code and
    links, however many English card names surround it. EN->CN convicts on
    English prose — lowercase words of 4+ letters — because abbreviations,
    capitalized names and kept slang legitimately stay in a Chinese output.
    Code, links and link targets are excluded on both sides. A direction value
    that is not a known task direction is an error, never a silent default.
    """
    from check_translation import check_translation

    def flagged(text: str, direction: str, source: str | None) -> list[str]:
        issues, _ = check_translation(text, direction=direction, source_text=source)
        return [i for i in issues if i.startswith("untranslated:")]

    cn_src = "这卡太超模了，建议削到五人口。"
    en_src = "This card is way too strong, nerf it to 5 provision."
    # Community-tone short sentences with no function word at all — each one
    # passed the whole gate untranslated before prose evidence replaced the
    # function-word list.
    short_en = [
        "Brace yourselves, changes incoming.",
        "Moms gone wild again.",
        "Weekend ladder feels rough.",
        "New season, same problems.",
        "Lagged out twice today.",
        "Nerf incoming, brace yourselves.",
    ]
    must_flag = [
        ("CN->EN 中文原样交回", cn_src, "cnen", cn_src, "一字不差"),
        ("CN->EN 只改标点的原样交回", "这卡太超模了，建议削到五人口!", "cnen", cn_src, "中文原文留在"),
        ("CN->EN 卡名换成英文、行文保留",
         "Royal Decree with Golden Nekker 配上和很稳!", "cnen", MIXED_CN_SOURCE, "中文原文留在"),
        ("CN->EN 译文末尾留一整句中文",
         "Golden Nekker with Royal Decree is really solid. 推荐大家试试。", "cnen", MIXED_CN_SOURCE,
         "中文原文留在"),
        ("CN->EN 中文玩家 ID 未转写（英文输出里不应出现中文）",
         "昆特小霸王 played well.", "cnen", "昆特小霸王打得真好。", "中文原文留在"),
        ("EN->CN 英文原样交回", en_src, "encn", en_src, "一字不差"),
        ("EN->CN 英文行文夹中文卡名原样交回", MIXED_EN_SOURCE, "encn", MIXED_EN_SOURCE, "一字不差"),
        ("EN->CN 英文占优的长文",
         "This deck is really strong and it wins. " * 30 + "很强。", "encn", None, "仍是英文"),
        # A link followed by Chinese on the same line: Chinese puts no space
        # after a URL, so the link must not swallow the rest of the line.
        ("CN->EN 链接后跟中文，只改标点", "https://t.co/abc123，下把继续!", "cnen",
         "https://t.co/abc123，下把继续。", "中文原文留在"),
        ("CN->EN 链接后跟中文，原样交回", "https://t.co/abc123，下把继续。", "cnen",
         "https://t.co/abc123，下把继续。", "一字不差"),
        # A preserved span counts only when the source has it: wrapping leftover
        # Chinese in code or a link target must not buy an exemption.
        ("CN->EN 中文被包进反引号（源文没有）", "Royal Decree with Golden Nekker `配上和很稳`!",
         "cnen", MIXED_CN_SOURCE, "中文原文留在"),
        ("CN->EN 中文被包进链接目标（源文没有）", "Royal Decree with Golden Nekker [x](配上和很稳)",
         "cnen", MIXED_CN_SOURCE, "中文原文留在"),
        ("CN->EN 中文被包进代码围栏（源文没有）",
         "Royal Decree with Golden Nekker\n```\n配上和很稳\n```", "cnen", MIXED_CN_SOURCE,
         "中文原文留在"),
        # Short replies whose content words are capitalized or too short for a
        # lowercase-word count alone.
        ("EN->CN Good luck", "Good luck", "encn", "Good luck", "一字不差"),
        ("EN->CN Well played", "Well played", "encn", "Well played", "一字不差"),
        ("EN->CN Thanks.", "Thanks.", "encn", "Thanks.", "一字不差"),
        ("EN->CN Nice try!", "Nice try!", "encn", "Nice try!", "一字不差"),
        # Capitalized replies caught through a common reply opener or a short
        # function word plus sentence punctuation.
        ("EN->CN Cheers.", "Cheers.", "encn", "Cheers.", "一字不差"),
        ("EN->CN My bad.", "My bad.", "encn", "My bad.", "一字不差"),
        ("EN->CN How are you.", "How are you.", "encn", "How are you.", "一字不差"),
        ("EN->CN Come on.", "Come on.", "encn", "Come on.", "一字不差"),
        # A stray backtick must not pair with a later one and hide what lies
        # between (no source here, so nothing is exempt by the source).
        ("CN->EN 游离反引号后的五段中文", "Typo`s there.\n\n第一段中文。\n\n第二段中文。\n\n第三段中文。\n\n"
         "第四段中文。\n\n最后一段 use `code`\n", "cnen", None, "中文原文留在"),
        ("CN->EN 游离反引号后紧跟代码围栏", "Typo`s there.\n```\ncode\n```\n这一段中文没翻译。\n",
         "cnen", None, "中文原文留在"),
    ] + [(f"EN->CN 短句原样交回: {s}", s, "encn", None, "仍是英文") for s in short_en]
    long_cn = "R1 用 GN 检索，R2 用 BC 展开，NR 打头，SK 收尾。" * 40
    must_pass = [
        ("CN->EN 正确英文", "This card is Overpowered, nerf it to 5 provision.", "cnen", cn_src),
        ("CN->EN 保留玩家 ID", "Lerio2 played that one really well.", "cnen", "Lerio2 这把打得真好。"),
        ("CN->EN 代码块里的中文按格式规则原样保留",
         "Run this first:\n```\n# 初始化配置\nfoo = 1\n```\nThen play Golden Nekker.", "cnen", None),
        ("CN->EN 链接目标里的中文按格式规则原样保留",
         "See [Meta analysis](#本月环境) for details.", "cnen", None),
        ("EN->CN 正确中文", "孽鬼跳松第一小局很强，用黄金孽鬼像检索皇家谕令。", "encn", MIXED_EN_SOURCE),
        ("EN->CN 保留俚语 gg wp", "gg wp", "encn", "gg wp"),
        ("EN->CN 保留俚语 lol", "lol", "encn", "lol"),
        ("EN->CN 缩写密集的中文", "GN 和 NR 都很强，BC 也砍了。", "encn",
         "GN and NR are both strong, and BC got hit too."),
        ("EN->CN 玩家 ID 榜单", "Lerio2、awi3、MetallicDanny 都进了前十。", "encn",
         "Lerio2, awi3 and MetallicDanny all made top ten."),
        ("EN->CN 长文夹大量缩写", long_cn, "encn",
         "Tutor with GN in R1, develop with BC in R2, NR opens and SK closes. " * 40),
        ("EN->CN 只有链接", "https://example.com/how-to-play", "encn",
         "https://example.com/how-to-play"),
        ("EN->CN 不含汉字的纯 ID 名单", "Lerio2 awi3 MetallicDanny Krentabol", "encn",
         "Lerio2 awi3 MetallicDanny Krentabol"),
        ("EN->CN 含英文的代码块", "```\nrun_this_now\n```\n先这样配置。", "encn", None),
        ("CN->EN 链接后跟中文，正确译文", "https://t.co/abc123, see you next game.", "cnen",
         "https://t.co/abc123，下把继续。"),
        ("CN->EN 源文自带的代码块原样保留",
         "Run this:\n```\n# 初始化配置\nfoo = 1\n```\nThen play Golden Nekker.", "cnen",
         "先运行：\n```\n# 初始化配置\nfoo = 1\n```\n再带黄金孽鬼像。"),
        # Identifier-only outputs: kept as they are, never read as English prose.
        ("EN->CN 不带协议头的链接", "www.playgwent.com/decks/guide", "encn",
         "www.playgwent.com/decks/guide"),
        ("EN->CN 邮箱", "contact@gwent.community", "encn", "contact@gwent.community"),
        ("EN->CN 话题标签", "#gwent #meta", "encn", "#gwent #meta"),
        ("EN->CN @ 提及", "@krentabol @metallicdanny", "encn", "@krentabol @metallicdanny"),
        # Names, events, versions and scores followed by a full stop translate
        # to themselves; the full stop must not turn them into English prose.
        ("EN->CN 人名加句号", "Krentabol.", "encn", "Krentabol."),
        ("EN->CN 赛事名加句号", "Gwent Masters.", "encn", "Gwent Masters."),
        ("EN->CN 版本号加句号", "Season 12.", "encn", "Season 12."),
        ("EN->CN 比分加句号", "Lerio2 2:0 Krentabol.", "encn", "Lerio2 2:0 Krentabol."),
        ("EN->CN 对阵行加句号", "Lerio2 vs Krentabol.", "encn", "Lerio2 vs Krentabol."),
        # Slang interjections may stay; they are not prose to translate.
        ("EN->CN 俚语感叹 BRUH.", "BRUH.", "encn", "BRUH."),
        ("EN->CN 俚语感叹 RIP.", "RIP.", "encn", "RIP."),
        # Inline code may hold a backtick run of another length (CommonMark):
        # the whole span is preserved, so nothing of it is a leftover.
        ("CN->EN 双反引号内含单个反引号的行内代码",
         "The end ``配置 ` 文件`` here.", "cnen", "结尾``配置 ` 文件``。"),
        # The full stop after a link is translated, the link itself is kept.
        ("EN->CN www 链接后的句号由半角变全角", "www.example.com/x。", "encn", "More at www.example.com/x."),
        # A correct Chinese translation with a stray backtick is not English prose.
        ("EN->CN 正确中文译文含游离反引号", "这里是正确的中文译文。\n\nTypo`s there.\n\nGG\n",
         "encn", "Here is the correct translation.\n\nTypo`s there.\n\nGG\n"),
    ]
    for name, text, direction, source, expect in must_flag:
        hits = flagged(text, direction, source)
        if not hits or expect not in hits[0]:
            return ("FAIL", f"{name}: expected a '{expect}' violation, got {hits}")
    for name, text, direction, source in must_pass:
        hits = flagged(text, direction, source)
        if hits:
            return ("FAIL", f"{name}: falsely flagged: {hits}")

    # The other half of the link case: Chinese puts no space after a URL, so a
    # link match that runs on to the end of the line would make the link
    # protection check reject the CORRECT translation of such a source.
    issues, _ = check_translation("https://t.co/abc123, see you next game.", direction="cnen",
                                  source_text="详见https://t.co/abc123，这套很稳。")
    link_issues = [i for i in issues if i.startswith("protected token")]
    if link_issues:
        return ("FAIL", f"link protection rejected a correct translation: {link_issues}")

    # A whole untranslated article must not flood the agent's context: beyond
    # the listing limit the leftover runs are summed up in ONE count-free entry,
    # so its key is stable from round to round.
    from check_translation import UNTRANSLATED_RUN_LISTING_LIMIT
    many = "。".join(f"第{i}段中文没有翻译" for i in range(UNTRANSLATED_RUN_LISTING_LIMIT + 10))
    hits = flagged(many, "cnen", None)
    if len(hits) != UNTRANSLATED_RUN_LISTING_LIMIT + 1:
        return ("FAIL", f"{UNTRANSLATED_RUN_LISTING_LIMIT + 10} leftover runs should give "
                        f"{UNTRANSLATED_RUN_LISTING_LIMIT} listed + 1 summary, got {len(hits)}")
    if any("更多段落" in h for h in hits[:-1]) or "更多段落" not in hits[-1]:
        return ("FAIL", f"the summary entry must be the single last one: {hits[-1][:60]}")
    if any(ch.isdigit() for ch in hits[-1]):
        return ("FAIL", f"the summary entry must not carry a count: {hits[-1]}")

    # Inside such a span only the surrounding prose is a leftover — never the
    # second half of the inline code, which an equal-length pairing used to lose.
    hits = flagged("译文结尾``配置 ` 文件``结束。", "cnen", "结尾``配置 ` 文件``。")
    if {h.split("「")[1].split("」")[0] for h in hits} != {"译文结尾", "结束"}:
        return ("FAIL", f"inline code with an inner backtick run must be preserved as a whole: {hits}")

    # A direction that is not a known task direction is an error at the library
    # level too — the CLI's argparse choices do not protect import callers.
    for bad in ("", "cn-en", "ENCN", None):
        try:
            check_translation("This is English text.", direction=bad)
        except ValueError:
            continue
        return ("FAIL", f"check_translation accepted the invalid direction {bad!r}")
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td) / "translated.txt"
        tp.write_text("这张卡很强。", encoding="utf-8")
        try:
            enforce_terms(tp, {"terms": {}}, "ENCN")
        except ValueError:
            pass
        else:
            return ("FAIL", "enforce_terms accepted the invalid direction 'ENCN'")

        # ...and so do the two lock builders, which decide which side of the
        # source gets extracted.
        from _shared import build_lock_from_source
        from context_lock import build_lock
        source = Path(td) / "source.md"
        source.write_text(MIXED_CN_SOURCE, encoding="utf-8")
        for builder in (lambda: build_lock(str(source), str(Path(td) / "lock.json"), "ENCN"),
                        lambda: build_lock_from_source(source, "ENCN")):
            try:
                builder()
            except ValueError:
                continue
            return ("FAIL", "a lock builder accepted the invalid direction 'ENCN'")
    return ("PASS", f"D4: {len(must_flag)} untranslated shapes BLOCKED, {len(must_pass)} legitimate "
                     "outputs not flagged; invalid directions rejected")


def _t_direction_is_taken_from_the_argument() -> tuple[str, str]:
    """D5: every checker acts on the stated direction, not on what the text looks like.

    The pre-fix gate read the direction off the text, so an output's own language
    could override the task's. Each command is therefore driven with a direction
    that contradicts its input: an English-only output gated as EN->CN is
    untranslated, the EN->CN half of the Phase C checklist runs on it, and a
    Chinese-keyed lock enforced as EN->CN is violated. A checker that re-guesses
    the direction from the text returns the opposite verdict and fails here.
    """
    def run(script: str, *args_: str) -> tuple[int, dict]:
        result = run_utf8([sys.executable, str(SCRIPT_DIR / script), *args_, "--json"], timeout=120)
        return result.returncode, json.loads(result.stdout)["data"]

    english = "This card is way too strong, nerf it to 5 provision.\n"
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "out.md"
        out.write_text(english, encoding="utf-8")

        code, data = run("check_translation.py", str(out), "--direction", "encn")
        categories = {issue["category"] for issue in data["issues"]}
        if code != 1 or "untranslated" not in categories:
            return ("FAIL", f"check_translation --direction encn did not treat English-only output "
                            f"as untranslated: exit {code} {sorted(categories)}")

        code, data = run("auto_pipeline.py", "scan", str(out), "--direction", "encn")
        if code != 1 or data.get("untranslated_count", 0) < 1:
            return ("FAIL", f"scan --direction encn did not report the untranslated output: "
                            f"exit {code} count={data.get('untranslated_count')}")

        # The guard must flag it as untranslated specifically — a guard that
        # crashes inside its terminology check is also "blocked", and must not pass here.
        code, data = run("completeness_guard.py", str(out), "--direction", "encn", "--lite",
                         "--verbose-terms")
        terminology = next((c for c in data["checks"] if c["name"] == "terminology"), {})
        categories = {issue.get("category") for issue in terminology.get("issues", [])}
        if code != 1 or "untranslated" not in categories:
            return ("FAIL", f"guard --direction encn did not flag English-only output as "
                            f"untranslated: exit {code} {sorted(str(c) for c in categories)}")

        parens = Path(td) / "parens.md"
        parens.write_text("Geralt: Igni (8 power) is strong.\n", encoding="utf-8")
        code, data = run("phase_c_check.py", str(parens), "--direction", "encn")
        rule_ids = {issue["rule_id"] for issue in data["automated_issues"]}
        if code != 1 or "encn-08" not in rule_ids:
            return ("FAIL", f"phase_c --direction encn did not run the EN->CN half of the checklist: "
                            f"exit {code} {sorted(rule_ids)}")

        lock = Path(td) / "lock.json"
        lock.write_text(json.dumps(_lock_from("希里与烧灼是核心卡。", "cnen"), ensure_ascii=False),
                        encoding="utf-8")
        good = Path(td) / "good.md"
        good.write_text("Ciri and Scorch are core cards.\n", encoding="utf-8")
        code_cnen, _ = run("term_enforcer.py", str(good), "--lock", str(lock), "--direction", "cnen")
        code_encn, _ = run("term_enforcer.py", str(good), "--lock", str(lock), "--direction", "encn")
        if code_cnen != 0 or code_encn != 1:
            return ("FAIL", f"term_enforcer did not follow --direction on the same lock and output: "
                            f"cnen exit {code_cnen}, encn exit {code_encn}")
    return ("PASS", "D5: checkers act on the stated direction when the text suggests the other one")


def _t_health_section_crash_is_a_fail() -> tuple[str, str]:
    """R4-1: a check that raises is one FAIL, not a dead health check.

    The doc guard crashed three times on its way here (each time on a comma
    before a script name), and each crash took the whole health check down
    with a traceback instead of reporting its other sections. A crashing
    section is now reported as failed — with the traceback on stderr, where it
    does not get in the way of the `--json` envelope — and the rest still run.
    """
    import health_check

    def boom() -> list[tuple[str, str]]:
        raise RuntimeError("injected")

    failed = [("FAIL", "Injected: 检查自身抛出异常 RuntimeError: injected")]
    stderr = io.StringIO()
    with contextlib.redirect_stderr(stderr):
        results = health_check._section_results("Injected", boom)
    if results != failed:
        return ("FAIL", f"a crashing section must be exactly one FAIL that names it: {results}")
    if "RuntimeError: injected" not in stderr.getvalue() or "in boom" not in stderr.getvalue():
        return ("FAIL", f"the traceback of a crashing section must reach stderr: {stderr.getvalue()!r}")
    if health_check._section_results("Healthy", lambda: [("PASS", "fine")]) != [("PASS", "fine")]:
        return ("FAIL", "a section that runs must be reported as it is")

    # With stderr closed, print() falls back to stdout: the traceback must not
    # get in the way of the envelope there.
    out, real_stderr = io.StringIO(), sys.stderr
    sys.stderr = None
    try:
        with contextlib.redirect_stdout(out):
            results = health_check._section_results("Injected", boom)
    finally:
        sys.stderr = real_stderr
    if results != failed or out.getvalue():
        return ("FAIL", f"with stderr closed the traceback leaked or the FAIL changed: "
                        f"{results} {out.getvalue()[:80]!r}")

    # health_check exits through SystemExit: the boundary must let it pass.
    def quit() -> None:
        raise SystemExit(3)

    try:
        health_check._section_results("Quits", quit)
    except SystemExit as exc:
        if exc.code != 3:
            return ("FAIL", f"SystemExit came through with another code: {exc.code}")
    else:
        return ("FAIL", "the boundary swallowed SystemExit")

    # main() wires every section through the boundary. A stand-in that runs
    # nothing counts the sections it is handed; the two slow sections are
    # stubbed so that broken wiring cannot run them (one of them is this suite).
    import inspect

    real, routed = health_check._section_results, []
    stubs = (health_check.run_test_cases, health_check._run_rebuild_behavior_tests)
    health_check._section_results = lambda name, func: routed.append(name) or [("PASS", name)]
    health_check.run_test_cases = health_check._run_rebuild_behavior_tests = lambda *_: []
    argv, no_color = sys.argv, health_check._no_color
    sys.argv = ["health_check.py", "--json"]
    out, code = io.StringIO(), None
    try:
        with contextlib.redirect_stdout(out):
            try:
                health_check.main()
            except SystemExit as exc:
                code = exc.code
    finally:
        health_check._section_results, sys.argv = real, argv
        health_check.run_test_cases, health_check._run_rebuild_behavior_tests = stubs
        health_check._no_color = no_color
    call_sites = sum(1 for part in inspect.getsource(health_check.main).splitlines()
                     if "= run_section(" in part)
    passed = json.loads(out.getvalue())["data"]["pass_count"]
    if len(routed) != call_sites or code != 0 or passed != call_sites:
        return ("FAIL", f"main() must route its {call_sites} sections through the boundary: "
                        f"routed {len(routed)}, passed {passed}, exit {code}")
    return ("PASS", "R4-1: a crashing check is one FAIL with its traceback on stderr; "
                     "the other sections still run")


_TESTS = [
    _t_en_extraction,
    _t_cn_extraction,
    _t_false_lock_guard,
    _t_subsume_guard,
    _t_ambiguous_base_priority,
    _t_ambiguous_rebuild,
    _t_subprocess_utf8,
    _t_format_issue_shapes,
    _t_lock_terms_filter,
    _t_violations_aggregation,
    _t_card_db_cache,
    _t_parse_ta_envelope,
    _t_pipeline,
    _t_lite_pack,
    _t_block_encn,
    _t_block_cnen,
    _t_cjk_absorb,
    _t_true_unknown,
    _t_lookup_card_db,
    _t_repair_tracking,
    _t_new_format_checks,
    _t_h1_guard_fail_closed,
    _t_h1_guard_fail_closed_phase_c,
    _t_h2_fix_keeps_ta,
    _t_m9_guard_lock_build_fail,
    _t_m5_degradation_signal,
    _t_m5_consumer_propagation,
    _t_subprocess_timeout_str,
    _t_phase_c_ambiguous_direction,
    _t_direction_required,
    _t_direction_reaches_lock,
    _t_direction_mixed_sources,
    _t_untranslated_output,
    _t_direction_is_taken_from_the_argument,
    _t_health_section_crash_is_a_fail,
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
