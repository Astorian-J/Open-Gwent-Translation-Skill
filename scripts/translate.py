#!/usr/bin/env python3
"""translate.py — Deterministic two-stage translation pipeline orchestrator.

The problem this solves: agents translating Gwent articles routinely skip the
SKILL.md workflow (no pre-processing, no final guard), producing translations
that *could* have been right but ship unverified, causing rework. translate.py
makes the deterministic shell around translation unavoidable:

    prepare  ->  [code] run pre-processing, build a "translation pack"
                       (no skipping: the pack is the only entry point)
        |
        v
    translate  ->  [LLM] the agent translates, guided by the pack
        |                  (the only non-deterministic step)
        v
    finish   ->  [code] run completeness_guard as a HARD gate (+ learn)
                       (no skipping: BLOCKED means the translation MUST NOT finalize)

Per SIMPLE-MCP-PLAN §2, translation itself stays with the LLM — this orchestrator
never calls an LLM API. It is a pure stdlib shell that reuses auto_pipeline.py
(pre) and completeness_guard.py (gate). No check logic is reimplemented here.

Usage:
    python scripts/translate.py prepare <source> [--date YYYY-MM] [--type general] [--direction encn|cnen] [--json]
    python scripts/translate.py finish  <translated> --source <source> [--direction encn|cnen] [--json]

Exit code:
    0 = PASS (prepare built a ready pack / finish gate passed)
    1 = BLOCKED (pre failed, gate failed, or the term-authority hole was hit)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import detect_direction, json_output

SCRIPTS_DIR = Path(__file__).parent

# Sub-process timeouts (seconds). pre and guard each chain several sibling scripts.
PRE_TIMEOUT = 240
GUARD_TIMEOUT = 300
LEARN_TIMEOUT = 120


# --- Embedded style rules & checklists (mirrors SKILL.md Phase B/C) ---
# Inlined so the pack is self-contained: the agent does not have to bounce back
# to SKILL.md while translating. Keep these in sync with SKILL.md.

STYLE_ENC = [
    ("Tone", "Bilibili player community tone, concise, punchy, allow slang"),
    ("Sentence length", "Break long English sentences into 2-3 short Chinese sentences"),
    ("Voice", 'Active voice. "对手不管她" not "未被解掉"'),
    ("Numbers", "Always Arabic numerals (5点, 12人口, R3, 4P)"),
    ("Parentheses", "Chinese brackets （）, not English ()"),
    ("Verbs", "Oral Chinese: 塞进/拍下/骗出/处理掉/赚翻/撑过/不管她/改回去"),
    ("Rhetoric", "比喻/夸张/反讽/嘲讽：先识别意图，译意图不译字面，留住咬人味"),
    ("Style", "Apply user's style fingerprint preferences when available"),
]

STYLE_CN = [
    ("Tone", "Casual but natural English. Not stiff or academic. Like a native player talking"),
    ("Sentence length", "Combine short Chinese sentences into flowing English prose"),
    ("Voice", 'Maintain active voice. "If left unanswered" not "If not dealt with by opponent"'),
    ("Numbers", 'Arabic numerals. "5 power, 12 provision", "R3", not "Round Three"'),
    ("Parentheses", "English parentheses (), not Chinese （）"),
    ("Slang", 'Preserve community slang: "nerf sponge", "abusive combo", "braindead deck"'),
    ("Rhetoric", "Preserve figurative intent & sarcasm; do not flatten irony or drain hyperbole"),
    ("Style", "Match the source's register (casual guide vs. formal analysis)"),
]

CHECKLIST_ENC = [
    'No "费/费用" in formal provision contexts (use 人口)',
    '"X for Y" -> "Y人口X战力" (not reversed, not identical numbers)',
    "Passive voice converted to active",
    "Arabic numerals throughout",
    "No English residue: all card names translated to Chinese",
    "Ambiguous card names include full subtitle",
    "Abbreviations expanded on first use (BC, OP, CA, etc.)",
    "Chinese parentheses （） used, not English ()",
    'Chinese colon "：" in card names',
    "Term authority compliance: all locked terms used with official translations",
    "Context lock terms used consistently throughout",
]

CHECKLIST_CN = [
    '"人口" -> "provision" (formal); "cost" only for SY Tribute',
    '"Y人口X战力" -> "X for Y" (correct order)',
    "No Chinese residue: all Chinese card names translated to English",
    "English parentheses () used, not Chinese （）",
    'English colon ":" in card names (e.g. "Geralt: Igni")',
    'Community slang preserved: 气宗->"no unit", 互口岛->"armor abuse"',
    'Oral verbs mapped naturally: 赚翻->"generates huge value", 撑过->"survives"',
    "Tone: casual but not broken English. Reads like a native player wrote it",
]


def _parse_json_envelope(stdout: str) -> dict | None:
    """Parse a JSON envelope from a script's stdout, tolerating leading non-JSON text.

    completeness_guard prints a `[WARN] context lock build failed ...` line to
    stdout when build_lock_from_source raises (the exact "silent pass" scenario
    this orchestrator exists to catch). That [WARN] prefixes the JSON envelope,
    so a plain json.loads fails on the mixed output. We scan for the first '{'
    that raw_decodes into a complete object (raw_decode ignores trailing text).
    """
    decoder = json.JSONDecoder()
    for i, ch in enumerate(stdout):
        if ch == "{":
            try:
                obj, _ = decoder.raw_decode(stdout[i:])
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(obj, dict):
                return obj
    return None


def run_script_json(script_name: str, args: list[str], timeout: int) -> tuple[bool, dict | None, str]:
    """Run a sibling script with --json appended; return (returncode_zero, parsed_envelope, raw).

    ok=False is NOT always fatal — a gate legitimately exits 1 with valid JSON when
    it BLOCKS. Callers must inspect parsed["data"], not ok, to decide pass/fail.
    parsed is None only when the script crashed without emitting JSON.
    """
    script = SCRIPTS_DIR / script_name
    if not script.exists():
        return False, None, f"{script_name} not found"

    try:
        result = subprocess.run(
            [sys.executable, str(script), *args, "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raw = (e.stdout or "") + ("\n[stderr] " + e.stderr if e.stderr else "")
        return False, None, raw + f"\n[timeout] {script_name} exceeded {timeout}s"

    raw = result.stdout.strip()
    if result.stderr:
        raw += "\n[stderr] " + result.stderr.strip()

    parsed = None
    if result.returncode in (0, 1) and result.stdout:
        parsed = _parse_json_envelope(result.stdout)

    return result.returncode == 0, parsed, raw


def _join_list(value) -> str:
    """Render a lock-table field that may be a list or a scalar as a cell string."""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v)
    return str(value) if value else ""


def build_pack(source_path: Path, direction: str, date: str | None,
               article_type: str, pre_data: dict, lock_built: bool) -> str:
    """Assemble the Markdown translation pack from auto_pipeline pre's JSON output."""
    ta = pre_data.get("term_authority", {}) or {}
    locked = ta.get("locked_terms", []) or []
    ambiguous = ta.get("ambiguous_terms", []) or []
    pending = ta.get("pending_terms", []) or []
    card_refs = pre_data.get("card_references", []) or []
    effects = pre_data.get("official_effects", []) or []
    slang = pre_data.get("slang_hints", []) or []

    is_encn = direction == "encn"
    dir_label = "EN -> CN" if is_encn else "CN -> EN"
    dir_note = "Bilibili player community tone" if is_encn else "Casual natural English"
    style_rules = STYLE_ENC if is_encn else STYLE_CN
    checklist = CHECKLIST_ENC if is_encn else CHECKLIST_CN

    L: list[str] = []
    L.append("# Gwent Translation Pack")
    L.append("")
    L.append(f"- **Source**: `{source_path}`")
    L.append(f"- **Direction**: {dir_label} ({dir_note})")
    L.append(f"- **Date**: {date or 'auto'}")
    L.append(f"- **Type**: {article_type}")
    L.append("- **Generated by**: `translate.py prepare`")
    L.append("")
    L.append("> Read this pack BEFORE translating. Use locked terms exactly;")
    L.append("> copy official effect text verbatim; do not translate literally.")
    L.append("")

    if not lock_built:
        L.append("> WARNING: context lock failed to build — the MANDATORY term lock")
        L.append("> table below is EMPTY. Translate cautiously and re-run prepare.")
        L.append("")

    # Style rules
    L.append("## Style Rules (风格规则)")
    L.append("")
    L.append("| Dimension | Rule |")
    L.append("|-----------|------|")
    for dim, rule in style_rules:
        L.append(f"| {dim} | {rule} |")
    L.append("")

    # Mandatory term lock table
    L.append("## MANDATORY Term Lock Table (强制术语锁表 — 用这些精确中文，勿字面直译)")
    L.append("")
    if locked:
        L.append("| English | Chinese | Aliases | Abbrevs |")
        L.append("|---------|---------|---------|---------|")
        for t in locked:
            L.append(
                f"| {t.get('canonical_en', '')} | {t.get('chinese', '')} "
                f"| {_join_list(t.get('aliases'))} | {_join_list(t.get('abbrevs'))} |"
            )
    else:
        L.append("_(none — see warning above if lock failed)_")
    L.append("")

    # Ambiguous names
    if ambiguous:
        L.append("## Ambiguous Names (歧义名 — 必须用全副标题，如 Geralt: Igni)")
        L.append("")
        for a in ambiguous:
            en = a.get("canonical_en") or a.get("extracted", "")
            variants = a.get("variants", []) or []
            if variants:
                vstr = "; ".join(f'{v.get("en", "")}->{v.get("cn", "")}' for v in variants)
            else:
                vstr = a.get("type", "")
            L.append(f"- **{en}** — {vstr}")
        L.append("")

    # Pending terms
    if pending:
        L.append("## Pending Terms (待定词 — 参考库没有，凭判断翻；复现就记入)")
        L.append("")
        for p in pending:
            L.append(f"- {p.get('extracted', '')} ({p.get('status', '')})")
        L.append("")

    # Card quick reference
    if card_refs:
        L.append("## Card Name Quick Reference (卡名快查)")
        L.append("")
        L.append("| English | Chinese |")
        L.append("|---------|---------|")
        for c in card_refs:
            L.append(f"| {c.get('english', '')} | {c.get('chinese', '')} |")
        L.append("")

    # Official effect text
    if effects:
        L.append("## Official Effect Text (官方效果 — 逐字照抄，勿改写)")
        L.append("")
        for e in effects:
            L.append(f"### {e.get('english', '')} -> {e.get('chinese', '')}")
            L.append("")
            L.append(e.get("official_ability", "") or "")
            L.append("")

    # Slang hints
    if slang:
        L.append("## Slang / Jargon Hints (俚语提示 — 按意向译，勿字面)")
        L.append("")
        L.append("| English | Intended CN | Note |")
        L.append("|---------|-------------|------|")
        for s in slang:
            L.append(
                f"| {s.get('english', '')} | {s.get('intended_cn', '')} | {s.get('note', '')} |"
            )
        L.append("")

    # Phase C acceptance checklist
    L.append("## Phase C Acceptance Checklist (验收清单 — 翻完逐条自检)")
    L.append("")
    for item in checklist:
        L.append(f"- [ ] {item}")
    L.append("")

    # Next-step hard rule
    L.append("## NEXT STEP (铁律)")
    L.append("")
    L.append("1. Translate the **full source** following the style rules + locked terms above.")
    L.append("2. Save the translation to a file (e.g. `translated.txt`).")
    L.append("3. Run the hard gate — the translation is NOT final until it PASSes:")
    L.append("")
    L.append("   ```bash")
    L.append(
        f"   python scripts/translate.py finish translated.txt "
        f"--source {source_path.name} --direction {direction}"
    )
    L.append("   ```")
    L.append("")
    L.append("> `finish` runs ALL checks. **BLOCKED = do not finalize.** Fix and re-run until PASS.")
    L.append("")

    return "\n".join(L)


def cmd_prepare(args: argparse.Namespace) -> None:
    source_path = Path(args.source)
    if not source_path.exists():
        if args.json:
            json_output(None, errors=[f"source file not found: {args.source}"], exit_code=1)
        print(f"Error: source file not found: {args.source}")
        sys.exit(1)

    direction = args.direction or "encn"  # EN->CN is the common case; banner + style table
    article_type = args.type

    # Run auto_pipeline pre (Phase A, reused wholesale).
    pre_args = ["pre", str(source_path), "--type", article_type]
    if args.date:
        pre_args.extend(["--date", args.date])
    _ok, parsed, raw = run_script_json("auto_pipeline.py", pre_args, PRE_TIMEOUT)

    if not parsed or "data" not in parsed:
        if args.json:
            json_output(None, errors=[f"auto_pipeline pre failed to return JSON: {raw}"], exit_code=1)
        print("=" * 60)
        print("TRANSLATE — PREPARE")
        print("=" * 60)
        print(f"\n[ERROR] auto_pipeline pre did not return usable output:\n{raw}")
        sys.exit(1)

    pre_data = parsed["data"]
    pre_exit_code = parsed.get("exit_code", 1)
    lock_built = bool(pre_data.get("lock_built", False))
    skeleton_extracted = bool(pre_data.get("skeleton_extracted", False))

    pack_path = source_path.with_name(source_path.stem + ".pack.md")
    pack_content = build_pack(source_path, direction, args.date, article_type, pre_data, lock_built)
    try:
        pack_path.write_text(pack_content, encoding="utf-8")
    except OSError as e:
        if args.json:
            json_output(None, errors=[f"failed to write pack: {e}"], exit_code=1)
        print(f"Error: failed to write pack to {pack_path}: {e}")
        sys.exit(1)

    ready = lock_built and skeleton_extracted and pre_exit_code == 0

    data = {
        "command": "prepare",
        "source": str(source_path),
        "direction": direction,
        "date": args.date or "auto",
        "type": article_type,
        "pack_path": str(pack_path),
        "pre_exit_code": pre_exit_code,
        "lock_built": lock_built,
        "skeleton_extracted": skeleton_extracted,
        "term_counts": {
            "locked": pre_data.get("term_authority", {}).get("locked_count", 0),
            "ambiguous": pre_data.get("term_authority", {}).get("ambiguous_count", 0),
            "pending": pre_data.get("term_authority", {}).get("pending_count", 0),
        },
        "ready": ready,
    }

    if args.json:
        json_output(data, exit_code=0 if ready else 1)

    # Human-readable
    print("=" * 60)
    print("TRANSLATE — PREPARE")
    print("=" * 60)
    print(f"\nSource:    {source_path}")
    print(f"Direction: {'EN->CN' if direction == 'encn' else 'CN->EN'}")
    print(f"Pack:      {pack_path}")
    print(f"Lock:      {'built' if lock_built else 'FAILED (pack written with empty lock table)'}")
    print(f"Skeleton:  {'extracted' if skeleton_extracted else 'failed'}")
    print(f"Terms:     {data['term_counts']['locked']} locked, "
          f"{data['term_counts']['ambiguous']} ambiguous, "
          f"{data['term_counts']['pending']} pending")
    print("")
    if ready:
        print("[PASS] Pack ready. Read it, translate the source, then run:")
        print(f"  python scripts/translate.py finish <translated> "
              f"--source {source_path.name} --direction {direction}")
    else:
        print("[WARN] Pack written but incomplete (see above). Translate cautiously,")
        print("       and investigate the failed pre-step before finalizing.")
    sys.exit(0 if ready else 1)


def cmd_finish(args: argparse.Namespace) -> None:
    translated_path = Path(args.translated)
    source_path = Path(args.source)

    if not translated_path.exists():
        if args.json:
            json_output(None, errors=[f"translated file not found: {args.translated}"], exit_code=1)
        print(f"Error: translated file not found: {args.translated}")
        sys.exit(1)
    if not source_path.exists():
        if args.json:
            json_output(None, errors=[f"source file not found: {args.source}"], exit_code=1)
        print(f"Error: source file not found: {args.source}")
        sys.exit(1)

    direction = args.direction
    direction_warning = None
    if not direction:
        try:
            text = translated_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            if args.json:
                json_output(None, errors=[f"failed to read translated file: {e}"], exit_code=1)
            print(f"Error: failed to read translated file {translated_path}: {e}")
            sys.exit(1)
        direction = detect_direction(text)
        direction_warning = (
            f"--direction not given; auto-detected as {direction} from the translation "
            f"(unreliable on mixed text — pass --direction explicitly for a trustworthy gate)"
        )

    # Hard gate: completeness_guard with --source (mandatory, so the lock is built and
    # term_authority actually runs) and --direction (so residue scanning targets the right lang).
    guard_args = [str(translated_path), "--source", str(source_path), "--direction", direction]
    _ok, parsed, raw = run_script_json("completeness_guard.py", guard_args, GUARD_TIMEOUT)

    if not parsed or "data" not in parsed:
        data = {
            "command": "finish",
            "translated": str(translated_path),
            "source": str(source_path),
            "direction": direction,
            "blocked": True,
            "block_reason": f"completeness_guard did not return JSON: {raw}",
            "guard": None,
            "learn": None,
        }
        if args.json:
            json_output(data, errors=[data["block_reason"]], exit_code=1)
        print("=" * 60)
        print("TRANSLATE — FINISH (HARD GATE)")
        print("=" * 60)
        print(f"\n[ERROR] completeness_guard did not return usable output:\n{raw}")
        sys.exit(1)

    guard_data = parsed["data"]
    guard_exit_code = parsed.get("exit_code", 1)
    all_passed = bool(guard_data.get("all_passed", False))
    checks = guard_data.get("checks", []) or []

    # --- Plug the "silent pass" hole (the safety core of this design) ---
    # completeness_guard.py swallows build_lock_from_source exceptions (returns
    # lock_path=None, prints [WARN], keeps going). With no lock, the term_authority
    # check returns status="skipped" -> passed=True, so the guard reports all_passed=True
    # WITHOUT ever checking terminology. We refuse to trust that: for EN->CN, the
    # term_authority check MUST have actually run (status=="ran"), or we BLOCK.
    # (CN->EN legitimately returns "not_applicable" — that is correct, not a hole.)
    block_reason: str | None = None
    if not all_passed:
        failed = [c for c in checks if not c.get("passed")]
        block_reason = "guard checks failed: " + "; ".join(
            c.get("message", c.get("name", "?")) for c in failed
        )
    elif direction == "encn":
        ta_check = next((c for c in checks if c.get("name") == "term_authority"), None)
        # Fail-closed: if the term_authority check is missing entirely OR did not actually
        # run, refuse to trust the guard's PASS. The whole point of this orchestrator is to
        # catch the silent-pass hole, so absence of the signal must block (not pass).
        if ta_check is None or ta_check.get("status") != "ran":
            status = ta_check.get("status") if ta_check else "missing"
            block_reason = (
                "context lock could not be built from source; term authority unverifiable "
                f"(status={status}). The guard reported PASS, but terminology "
                "was NOT actually checked. Treat as BLOCKED."
            )

    blocked = block_reason is not None

    # Learn only after a genuine PASS; never let it affect the gate.
    learn_result = None
    if not blocked:
        _lok, lparsed, _lraw = run_script_json(
            "learn.py", [str(source_path), str(translated_path), "--auto"], LEARN_TIMEOUT
        )
        if lparsed and "data" in lparsed:
            learn_result = lparsed["data"]

    data = {
        "command": "finish",
        "translated": str(translated_path),
        "source": str(source_path),
        "direction": direction,
        "direction_warning": direction_warning,
        "guard_exit_code": guard_exit_code,
        "guard_all_passed": all_passed,
        "guard": guard_data,
        "blocked": blocked,
        "block_reason": block_reason,
        "learn": learn_result,
    }

    exit_code = 1 if blocked else 0

    if args.json:
        json_output(data, exit_code=exit_code)

    # Human-readable
    print("=" * 60)
    print("TRANSLATE — FINISH (HARD GATE)")
    print("=" * 60)
    print(f"\nTranslated: {translated_path}")
    print(f"Source:     {source_path}")
    print(f"Direction:  {'EN->CN' if direction == 'encn' else 'CN->EN'}")
    if direction_warning:
        print(f"Note:       {direction_warning}")
    print("")

    if not blocked:
        learned = 0
        if learn_result and isinstance(learn_result, dict):
            learned = learn_result.get("added_to_pending", 0)
        print("[PASS] Guard: all checks passed.")
        print(f"       Learn: recorded {learned} new term(s).")
        print("")
        print("[PASS] TRANSLATION READY — you may finalize.")
    else:
        if not all_passed:
            print("[BLOCKED] Guard checks failed:")
            for c in checks:
                if not c.get("passed"):
                    print(f"   - {c.get('message', c.get('name', '?'))}")
        else:
            # The hole: guard said PASS but we overridden to BLOCKED.
            print("[BLOCKED] Guard reported PASS, BUT term authority was not actually checked")
            print("          (context lock could not be built from source).")
        print("")
        print("[BLOCKED] DO NOT FINALIZE. Fix the issue(s) above and re-run:")
        print(f"  python scripts/translate.py finish {translated_path.name} "
              f"--source {source_path.name} --direction {direction}")

    sys.exit(exit_code)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="translate.py — deterministic two-stage translation pipeline (prepare / finish)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prep = subparsers.add_parser("prepare", help="Run pre-processing and build a translation pack")
    prep.add_argument("source", help="Source file to translate")
    prep.add_argument("--date", help="Article date (YYYY-MM)")
    prep.add_argument(
        "--type",
        choices=["meta", "bc-proposal", "card-analysis", "patch-notes", "general"],
        default="general",
        help="Article type (default: general)",
    )
    prep.add_argument(
        "--direction", choices=["encn", "cnen"],
        help="Direction for the pack banner + style table (default: encn)",
    )
    prep.add_argument("--json", action="store_true", help="Output structured JSON")

    fin = subparsers.add_parser("finish", help="Run the hard gate (guard + learn) on a translation")
    fin.add_argument("translated", help="Translated file to verify")
    fin.add_argument(
        "--source", required=True,
        help="Original source file (REQUIRED — needed to build the term lock for the gate)",
    )
    fin.add_argument("--direction", choices=["encn", "cnen"], help="Translation direction (auto-detected if omitted)")
    fin.add_argument("--json", action="store_true", help="Output structured JSON")

    args = parser.parse_args()
    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "finish":
        cmd_finish(args)


if __name__ == "__main__":
    main()
