#!/usr/bin/env python3
"""
Gwent Translation Auto-Pipeline.

ONE command to rule them all. Run this before and after translation
to ensure all preprocessing and postprocessing steps are executed.

Usage (Pre-translation):
    python auto_pipeline.py pre source.md --date 2026-05 --type meta

Usage (Post-translation, after you have translated.txt):
    python auto_pipeline.py post source.md translated.txt

This script chains all sub-scripts automatically so the agent
does not need to remember individual steps.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import detect_direction, json_output, terms_summary, TermAuthority


# Scripts that already support --json in Phase 1.
JSON_CAPABLE_SCRIPTS = {
    "check_translation.py",
    "health_check.py",
    "phase_c_check.py",
    "learn.py",
    "context_lock.py",
    "format_skeleton.py",
}

# Cap on how many official card effects the pre-translation report injects
# (both human and JSON output). The full set lives in references/effect_text.json
# for on-demand lookup; capping bounds agent context for card-heavy articles.
OFFICIAL_EFFECTS_CAP = 20

# Cap on how many slang hints the pre-translation report injects. Slang density
# is low in practice, but capping bounds agent context and keeps the hint list
# focused on this article's actual slang.
SLANG_HINTS_CAP = 15


def get_script_dir() -> Path:
    return Path(__file__).parent


def build_card_lookup_table(source_path: Path) -> list[tuple[str, str]]:
    """Build a quick reference table of card names found in the source text.

    Returns: list of (english_name, chinese_name) tuples.
    """
    from _shared import (
        extract_abbreviations,
        extract_capitalized_phrases,
        extract_card_names,
        extract_card_names_no_colon,
        extract_terms_from_markdown,
        get_card_names_index,
    )

    source_text = source_path.read_text(encoding="utf-8")

    # Extract candidate card names from source
    candidates = set()
    for name in extract_card_names(source_text):
        candidates.add(name.strip())
    for name in extract_card_names_no_colon(source_text, max_words=5, min_length=4):
        candidates.add(name.strip())
    for name in extract_terms_from_markdown(source_text):
        candidates.add(name.strip())
    for name in extract_capitalized_phrases(source_text, max_words=3, min_length=4):
        candidates.add(name.strip())

    # Load card names (cards-only, from the 4lang table + card_overrides.md).
    card_map = get_card_names_index()

    # Match candidates against card database
    results = []
    seen = set()
    unresolved: list[str] = []
    for cand in sorted(candidates):
        key = cand.lower()
        if key in card_map:
            en, cn = card_map[key]
            if en.lower() not in seen:
                seen.add(en.lower())
                results.append((en, cn))
            continue
        # Partial match: collect ALL cards that contain or are contained by this candidate.
        # This surfaces ambiguous base names (e.g. "Geralt" matches all 6 variants).
        partial_hits = [
            (db_en, db_cn)
            for db_key, (db_en, db_cn) in card_map.items()
            if key in db_key or db_key in key
        ]
        if partial_hits:
            for db_en, db_cn in partial_hits:
                if db_en.lower() not in seen:
                    seen.add(db_en.lower())
                    results.append((db_en, db_cn))
        else:
            unresolved.append(cand)

    # Aggressive variant matching (reverse-containment + edit distance) for
    # variants the candidate/partial matchers miss (Double-Bladed Dagur, Froth,
    # Schirru). Delegates to TermAuthority so card_references stays in sync with
    # the lock produced by context_lock (get_all_for_text).
    from _shared import get_term_authority
    ta = get_term_authority()
    for canon_en, _variant in ta._aggressive_card_matches(source_text, unresolved):
        rec = card_map.get(canon_en.lower())
        if rec and rec[0].lower() not in seen:
            seen.add(rec[0].lower())
            results.append(rec)

    return results


def build_term_authority_report(lock_file: Path) -> dict:
    """Build the mandatory term authority report from a context lock file.

    The lock file is produced by context_lock.py build and contains terms
    with status: auto_locked, ambiguous, or pending.
    """
    default = {
        "locked_count": 0,
        "ambiguous_count": 0,
        "pending_count": 0,
        "locked_terms": [],
        "ambiguous_terms": [],
        "pending_terms": [],
    }
    if not lock_file.exists():
        return default

    try:
        lock = json.loads(lock_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default

    locked_terms: list[dict] = []
    ambiguous_terms: list[dict] = []
    pending_terms: list[dict] = []

    for term, info in lock.get("terms", {}).items():
        status = info.get("status", "pending")
        if status == "auto_locked":
            canonical = info.get("canonical_en", term)
            entry = {
                "canonical_en": canonical,
                "chinese": info.get("cn", ""),
            }
            # extracted 仅当与 canonical_en 不同时保留(缩写/别名展开，agent
            # 需知道源文形式对应)；相同时冗余，省 token。砍 type/source_ref
            # (agent 翻译不需要)；空 aliases/abbrevs 不输出。
            # 注意：校验脚本(term_enforcer 等)走 TermAuthority 对象+lock 文件，
            # 不读这里的 JSON 字段，所以精简不影响翻译校验准确性。
            if term != canonical:
                entry["extracted"] = term
            aliases = info.get("aliases", [])
            if aliases:
                entry["aliases"] = aliases
            abbrevs = info.get("abbrevs", [])
            if abbrevs:
                entry["abbrevs"] = abbrevs
            locked_terms.append(entry)
        elif status == "ambiguous":
            ambiguous_terms.append({
                "extracted": term,
                "canonical_en": info.get("canonical_en", term),
                "type": info.get("type", ""),
                "source_ref": info.get("source_ref", ""),
                "variants": info.get("variants", []),
            })
        else:
            pending_terms.append({"extracted": term, "status": status})

    return {
        "locked_count": len(locked_terms),
        "ambiguous_count": len(ambiguous_terms),
        "pending_count": len(pending_terms),
        "locked_terms": locked_terms,
        "ambiguous_terms": ambiguous_terms,
        "pending_terms": pending_terms,
    }


def run_script(name: str, args: list[str], json_mode: bool = False) -> tuple[bool, str, dict | None]:
    """Run a sub-script and return (success, output, parsed_json).

    If json_mode is True and the script is in JSON_CAPABLE_SCRIPTS, --json is
    appended and the stdout is parsed as JSON when possible.
    """
    script = get_script_dir() / name
    if not script.exists():
        return False, f"Script not found: {script}", None
    cmd = [sys.executable, str(script)] + args
    if json_mode and name in JSON_CAPABLE_SCRIPTS:
        cmd.append("--json")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired as e:
        output = e.stdout or ""
        if e.stderr:
            output += "\n[stderr] " + e.stderr
        output += "\n[timeout] Script exceeded 120s and was terminated."
        return False, output, None

    output = result.stdout
    if result.stderr:
        output += "\n[stderr] " + result.stderr

    parsed = None
    if json_mode and name in JSON_CAPABLE_SCRIPTS and result.stdout:
        try:
            parsed = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass

    return result.returncode == 0, output, parsed


def pre_translation(source_path: Path, date: str | None, article_type: str, json_mode: bool = False, verbose_terms: bool = False) -> tuple[str | dict, bool]:
    """Run all preprocessing steps. Returns a report and overall success."""
    all_ok = True
    # 清理上次 pre 遗留的陈旧临时文件（>1 小时），避免 /tmp 长期累积。不能清理本次/
    # 并发刚创建的：skeleton/lock 路径会返回给调用方，供后续 completeness_guard
    # --lock / format_skeleton restore 跨进程复用（故不能用 TemporaryDirectory 包本函数）。
    _now = time.time()
    for _pat in ("gwent_skeleton_*.json", "gwent_lock_*.json"):
        for _stale in Path(tempfile.gettempdir()).glob(_pat):
            try:
                if _now - _stale.stat().st_mtime > 3600:
                    _stale.unlink()
            except OSError:
                pass
    skeleton_file = Path(tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="gwent_skeleton_", delete=False
    ).name)
    lock_file = Path(tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", prefix="gwent_lock_", delete=False
    ).name)

    # Step 1: Format skeleton
    ok, out, _ = run_script(
        "format_skeleton.py",
        ["extract", str(source_path), "--output", str(skeleton_file)],
        json_mode=json_mode,
    )
    skeleton_extracted = ok
    if not ok:
        all_ok = False

    # Step 2: Context lock
    ok, out, _ = run_script(
        "context_lock.py",
        ["build", str(source_path), "--output", str(lock_file)],
        json_mode=json_mode,
    )
    lock_built = ok
    if not ok:
        all_ok = False

    # Step 3: Build term authority report from lock file
    term_authority = build_term_authority_report(lock_file)

    # Step 4: Build card name quick reference table
    quick_ref = build_card_lookup_table(source_path)

    # Step 5: Official effect text for cards in the source — inject so the agent
    # copies the official CN ability verbatim when quoting effects. Long
    # sentences can't be locked by term_enforcer, so this is the enforcement
    # lever for effect text. See references/effect_text.json.
    authority = TermAuthority()
    official_effects = []
    for en, _cn in quick_ref:
        rec = authority.get_official_ability(en)
        if rec and rec.get("cn_ability"):
            official_effects.append({
                "english": en,
                "chinese": rec.get("cn_name", ""),
                "official_ability": rec["cn_ability"],
            })

    # Step 6: Slang/jargon hints for terms found in the source — inject the
    # intended CN register so the agent translates community tone (加强版 for
    # "on steroids") instead of literal gibberish (类固醇). Prevention layer;
    # check_translation warns if a detected slang is translated literally.
    source_text = source_path.read_text(encoding="utf-8")
    slang_hits = authority.get_slang_for_text(source_text)

    if json_mode:
        card_refs = [{"english": en, "chinese": cn} for en, cn in quick_ref]
        ta_report = term_authority
        # Default --json emits COUNTS + a top-N sample of the big lists so a
        # card-heavy article cannot flood agent context; --verbose-terms returns
        # the full lists. Counts (card_references_found / *_count) stay complete.
        if not verbose_terms:
            card_refs = terms_summary(card_refs, False)
            ta_report = {
                **term_authority,
                "locked_terms": terms_summary(term_authority["locked_terms"], False),
                "ambiguous_terms": terms_summary(term_authority["ambiguous_terms"], False),
                "pending_terms": terms_summary(term_authority["pending_terms"], False),
            }
        data = {
            "command": "pre",
            "source": str(source_path),
            "date": date or "auto",
            "type": article_type,
            "skeleton_extracted": skeleton_extracted,
            "skeleton_path": str(skeleton_file),
            "lock_built": lock_built,
            "lock_path": str(lock_file),
            "card_references_found": len(quick_ref),
            "card_references": card_refs,
            "official_effects": official_effects[:OFFICIAL_EFFECTS_CAP],
            "official_effects_total": len(official_effects),
            "slang_hints": slang_hits[:SLANG_HINTS_CAP],
            "slang_hints_total": len(slang_hits),
            "term_authority": ta_report,
        }
        return data, all_ok

    lines = [
        "=" * 60,
        "GWENT TRANSLATION PIPELINE — PRE-TRANSLATION",
        "=" * 60,
        "",
        f"Source: {source_path}",
        f"Date: {date or 'auto'}",
        f"Type: {article_type}",
        "",
    ]

    lines.append("[1/3] Extracting format skeleton...")
    if skeleton_extracted:
        lines.append(f"    [OK] Skeleton saved to: {skeleton_file}")
    else:
        lines.append(f"    [WARN] Format extraction skipped or failed: {out.strip()}")
    lines.append("")

    lines.append("[2/3] Building context lock...")
    if lock_built:
        lines.append(f"    [OK] Lock table saved to: {lock_file}")
        if "terms" in out:
            lines.append(f"    {out.strip()}")
    else:
        lines.append(f"    [WARN] Context lock skipped or failed: {out.strip()}")
    lines.append("")

    lines.append("[3/3] Building mandatory term lock table...")
    lines.append(f"    [OK] {term_authority['locked_count']} locked, "
                 f"{term_authority['ambiguous_count']} ambiguous, "
                 f"{term_authority['pending_count']} pending")
    lines.append("")

    if term_authority["locked_terms"]:
        lines.append("    MANDATORY TERM LOCK TABLE")
        lines.append("    Use these exact translations. Do not translate literally.")
        lines.append("")
        lines.append("    | Canonical EN | Chinese |")
        lines.append("    |--------------|---------|")
        for item in term_authority["locked_terms"][:30]:
            extras = ""
            if item.get("extracted"):
                extras += f" (源文: {item['extracted']})"
            aliases = ", ".join(item.get("aliases", []))
            abbrevs = ", ".join(item.get("abbrevs", []))
            if aliases:
                extras += f" aliases={aliases}"
            if abbrevs:
                extras += f" abbrevs={abbrevs}"
            lines.append(f"    | {item['canonical_en']} | {item['chinese']}{extras} |")
        if len(term_authority["locked_terms"]) > 30:
            lines.append(
                f"    | ... ({len(term_authority['locked_terms']) - 30} more) | ... |"
            )
        lines.append("")

    if term_authority["ambiguous_terms"]:
        lines.append("    AMBIGUOUS NAMES — disambiguate with full subtitle")
        for item in term_authority["ambiguous_terms"][:10]:
            variants = " / ".join(v["cn"] for v in item.get("variants", []) if v.get("cn"))
            lines.append(f"    - {item['extracted']} ({item['canonical_en']}): {variants}")
        if len(term_authority["ambiguous_terms"]) > 10:
            lines.append(f"    - ... ({len(term_authority['ambiguous_terms']) - 10} more)")
        lines.append("")

    if term_authority["pending_terms"]:
        lines.append("    PENDING TERMS — not in reference database")
        for item in term_authority["pending_terms"][:10]:
            lines.append(f"    - {item['extracted']}")
        if len(term_authority["pending_terms"]) > 10:
            lines.append(f"    - ... ({len(term_authority['pending_terms']) - 10} more)")
        lines.append("")

    if quick_ref:
        lines.append("    Card name quick reference:")
        lines.append("    | English | Chinese |")
        lines.append("    |---------|---------|")
        for en, cn in quick_ref[:20]:
            lines.append(f"    | {en} | {cn} |")
        if len(quick_ref) > 20:
            lines.append(f"    | ... ({len(quick_ref) - 20} more) | ... |")
        lines.append("")
    else:
        lines.append("    [INFO] No additional card names detected in source")
        lines.append("")

    if official_effects:
        lines.append("    OFFICIAL EFFECT TEXT (引用效果时逐字照抄，勿改写)")
        lines.append("    | Card | Chinese | Official ability |")
        lines.append("    |------|---------|------------------|")
        for eff in official_effects[:OFFICIAL_EFFECTS_CAP]:
            ability = " ".join(eff["official_ability"].split())
            lines.append(f"    | {eff['english']} | {eff['chinese']} | {ability} |")
        if len(official_effects) > OFFICIAL_EFFECTS_CAP:
            lines.append(f"    | ... ({len(official_effects) - OFFICIAL_EFFECTS_CAP} more; "
                         f"全部见 effect_text.json) | ... | ... |")
        lines.append("")

    if slang_hits:
        lines.append("    SLANG / JARGON HINTS (按意向译，勿字面硬译)")
        lines.append("    | English | 意向译 | 字面禁译 |")
        lines.append("    |---------|---------|---------|")
        for rec in slang_hits[:SLANG_HINTS_CAP]:
            lines.append(f"    | {rec['english']} | {rec['intended_cn']} | {rec['literal_forbidden']} |")
        if len(slang_hits) > SLANG_HINTS_CAP:
            lines.append(f"    | ... ({len(slang_hits) - SLANG_HINTS_CAP} more) | ... | ... |")
        lines.append("")

    lines.append("-" * 50)
    lines.append("Pre-translation complete.")
    lines.append("")

    lines.append("=" * 60)
    lines.append("MANDATORY NEXT STEP — DO NOT SKIP")
    lines.append("")
    lines.append("1. Perform the translation using the quick reference above")
    lines.append("2. Save translation to a file (e.g., translated.txt)")
    lines.append("3. Run: python auto_pipeline.py post source.md translated.txt")
    lines.append("")
    lines.append("You must run 'post' after translation. Do not finalize")
    lines.append("the translation without running post first.")
    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines), all_ok


def post_translation(source_path: Path, translated_path: Path, direction: str | None = None, json_mode: bool = False) -> tuple[str | dict, bool]:
    """Run all postprocessing steps. Returns a report and overall success."""
    all_ok = True
    text = translated_path.read_text(encoding="utf-8")
    direction = direction or detect_direction(text)

    # Step 1: Check terminology
    check_ok, check_out, check_parsed = run_script(
        "check_translation.py",
        [str(translated_path), "--direction", direction],
        json_mode=json_mode,
    )
    if not check_ok:
        all_ok = False
    terminology_issue_count = check_parsed.get("data", {}).get("issue_count", 0) if check_parsed else 0

    # Step 2: Diff review (if user provided their own translation — not applicable here)
    # Skip auto diff-review; only run if explicitly requested

    # Step 3: Learn new terms
    learn_ok, learn_out, learn_parsed = run_script(
        "learn.py",
        [str(source_path), str(translated_path), "--auto"],
        json_mode=json_mode,
    )
    if not learn_ok:
        all_ok = False
    if learn_parsed and "data" in learn_parsed:
        new_terms_learned = learn_parsed["data"].get("added_to_pending", 0)
    else:
        new_terms_learned = 0
        if "Discovered" in learn_out and "potential new term" in learn_out:
            try:
                new_terms_learned = int(learn_out.split("Discovered ")[1].split(" potential new term")[0])
            except (IndexError, ValueError):
                pass

    # Step 4: Health check
    health_ok, health_out, _ = run_script(
        "health_check.py",
        [],
        json_mode=json_mode,
    )
    if not health_ok:
        all_ok = False
    health_check_passed = health_ok

    if json_mode:
        data = {
            "command": "post",
            "source": str(source_path),
            "translated": str(translated_path),
            "direction": direction,
            "terminology_issue_count": terminology_issue_count,
            "new_terms_learned": new_terms_learned,
            "health_check_passed": health_check_passed,
        }
        return data, all_ok

    lines = [
        "=" * 60,
        "GWENT TRANSLATION PIPELINE — POST-TRANSLATION",
        "=" * 60,
        "",
        f"Source:      {source_path}",
        f"Translated:  {translated_path}",
        f"Direction:   {'EN->CN' if direction == 'encn' else 'CN->EN'}",
        "",
    ]

    lines.append("[1/3] Running terminology check...")
    lines.append(check_out)
    lines.append("")

    lines.append("[2/3] Learning new terms...")
    lines.append(learn_out)
    lines.append("")

    lines.append("[3/3] Skill health check...")
    for line in health_out.split("\n"):
        if "PASS" in line or "FAIL" in line or "All checks" in line:
            lines.append(line)
    lines.append("")

    lines.append("=" * 60)
    lines.append("MANDATORY NEXT STEP — DO NOT SKIP")
    lines.append("")
    lines.append("Run: python scripts/completeness_guard.py")
    lines.append("")
    lines.append("You must run the guard BEFORE finalizing the translation.")
    lines.append("Do not ignore guard output.")
    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines), all_ok


def scan_translation(
    translated_path: Path,
    direction: str | None = None,
    json_mode: bool = False,
) -> tuple[str | dict, bool]:
    """Standalone scan mode: check a translated file for untranslated card names.

    Direction-aware final defense line. For EN->CN output it reports English
    card names left untranslated; for CN->EN output it reports Chinese card
    names left untranslated. Direction is auto-detected from the file when
    not given, and passed through to check_translation.py so both sides agree.
    """
    text = translated_path.read_text(encoding="utf-8")
    direction = direction or detect_direction(text)

    ok, out, parsed = run_script(
        "check_translation.py",
        [str(translated_path), "--direction", direction],
        json_mode=json_mode,
    )

    residue_categories = {"english_residue", "chinese_residue"}
    residues = []
    if parsed and parsed.get("data"):
        for issue in parsed["data"].get("issues", []):
            if issue.get("category") in residue_categories:
                residues.append(issue)
    else:
        # Fallback for non-JSON mode or parse failure.
        residues = [
            {"message": line.strip()}
            for line in out.split("\n")
            if "English residue" in line or "Chinese residue" in line
        ]

    if json_mode:
        data = {
            "command": "scan",
            "translated": str(translated_path),
            "direction": direction,
            "residue_count": len(residues),
            "residues": residues,
        }
        return data, len(residues) == 0

    # Residues are always in the SOURCE language; the fix is to translate
    # them into the target language of this direction.
    source_lang = "English" if direction == "encn" else "Chinese"
    target_lang = "Chinese" if direction == "encn" else "English"

    lines = [
        "=" * 60,
        "GWENT TRANSLATION — RESIDUE SCAN",
        "=" * 60,
        "",
        f"File:      {translated_path}",
        f"Direction: {'EN->CN' if direction == 'encn' else 'CN->EN'}",
        "",
    ]

    if residues:
        lines.append(f"[WARN] Found {len(residues)} {source_lang} residue(s):")
        lines.append("")
        for issue in residues:
            lines.append(f"  {issue.get('message', issue)}")
        lines.append("")
        lines.append("-" * 50)
        lines.append(f"Action required: Replace the above {source_lang} card names")
        lines.append(f"with their {target_lang} translations before finalizing.")
        lines.append("")
        lines.append("[BLOCKED] After fixing, re-run: python auto_pipeline.py scan translated.txt")
    else:
        lines.append(f"[PASS] No {source_lang} residue found. Translation is clean.")
        lines.append("")
        lines.append("If you have not yet run post-processing:")
        lines.append("  python auto_pipeline.py post source.md translated.txt")

    lines.append("")
    return "\n".join(lines), len(residues) == 0


def main():
    parser = argparse.ArgumentParser(description="Gwent Translation Auto-Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pre = subparsers.add_parser("pre", help="Pre-translation preprocessing")
    pre.add_argument("source", help="Source file to translate")
    pre.add_argument("--date", help="Article date (YYYY-MM)")
    pre.add_argument("--type", choices=["meta", "bc-proposal", "card-analysis", "patch-notes", "general"],
                     default="general", help="Article type")
    pre.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    pre.add_argument("--verbose-terms", action="store_true", help="Emit full term/violation lists (default: counts + top 5)")

    post = subparsers.add_parser("post", help="Post-translation checks")
    post.add_argument("source", help="Original source file")
    post.add_argument("translated", help="Translated file")
    post.add_argument("--direction", choices=["encn", "cnen"], help="Translation direction (auto-detected if omitted)")
    post.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")

    scan = subparsers.add_parser("scan", help="Scan translated file for untranslated card names")
    scan.add_argument("translated", help="Translated file to scan")
    scan.add_argument("--direction", choices=["encn", "cnen"], help="Translation direction (auto-detected if omitted)")
    scan.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")

    args = parser.parse_args()
    json_mode = args.json

    if args.command == "scan":
        translated_path = Path(args.translated)
        if not translated_path.exists():
            if json_mode:
                json_output(None, errors=[f"Translated file not found: {args.translated}"], exit_code=1)
            print(f"Error: Translated file not found: {args.translated}")
            sys.exit(1)
        report, ok = scan_translation(translated_path, direction=args.direction, json_mode=json_mode)
        if json_mode:
            json_output(report, exit_code=0 if ok else 1)
        print(report)
        sys.exit(0 if ok else 1)

    source_path = Path(args.source)
    if not source_path.exists():
        if json_mode:
            json_output(None, errors=[f"Source file not found: {args.source}"], exit_code=1)
        print(f"Error: Source file not found: {args.source}")
        sys.exit(1)

    if args.command == "pre":
        report, ok = pre_translation(source_path, args.date, args.type, json_mode=json_mode, verbose_terms=args.verbose_terms)
        if json_mode:
            json_output(report, exit_code=0 if ok else 1)
        print(report)
        sys.exit(0 if ok else 1)
    elif args.command == "post":
        translated_path = Path(args.translated)
        if not translated_path.exists():
            if json_mode:
                json_output(None, errors=[f"Translated file not found: {args.translated}"], exit_code=1)
            print(f"Error: Translated file not found: {args.translated}")
            sys.exit(1)
        report, ok = post_translation(source_path, translated_path, direction=args.direction, json_mode=json_mode)
        if json_mode:
            json_output(report, exit_code=0 if ok else 1)
        print(report)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
