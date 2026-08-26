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
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared import detect_direction, format_issue, json_output, source_is_chinese

SCRIPTS_DIR = Path(__file__).parent

# Sub-process timeouts (seconds). pre and guard each chain several sibling scripts.
PRE_TIMEOUT = 240
GUARD_TIMEOUT = 300
LEARN_TIMEOUT = 120
EFFECT_TIMEOUT = 120  # official-effect verbatim pass (informational; same budget as learn)


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

# Balance change direction guidance — injected into the pack so the agent sees
# the buff/nerf direction rules inline (Gwent-specific: power/provision may be
# reversed for disloyal units and leaders). Mirrors style_reference.md.
PACK_BALANCE_GUIDE = [
    "## [JUDGE] Balance Change Direction（平衡调整增强削弱判断）",
    "",
    "翻译平衡调整（patch/buff/nerf）时必须准确判断增强/削弱方向。昆特牌设计特殊，方向不一定按数值直觉。",
    "",
    "**方向词：** `buff/buffed` = 增强；`nerf/nerfed` = 削弱；`change/adjust/tweak/rework` = 中性改动（别硬补方向）。",
    "",
    "**判断规则：**",
    "- 一般单位：战力+1=增强，战力−1=削弱；人口−1=增强，人口+1=削弱。",
    "- 间谍单位（Disloyal/不忠）：战力方向反 —— 战力−1=增强，战力+1=削弱（间谍战力算对方的，减战力对自己有利）。",
    "- 领袖卡（Leader，无战力只改人口）：人口方向反 —— 人口+1=增强，人口−1=削弱（人口高=能带更多牌）。",
    "",
    "**原则：** 原文明确 buff/nerf → 照原文方向译；只给数值 → 按规则判断方向**不要翻反**；无法判断 → 照翻事实不硬补。",
    "",
    "下方「官方效果」已按卡牌类型标注：[领袖·人口反向]/[间谍单位·战力反向]/[单位]，据此应用上述规则。",
    "",
]

# Markdown format preservation guidance — injected into the pack so the agent
# keeps the source's markdown structure 1:1. Mirrors style_reference.md.
PACK_FORMAT_GUIDE = [
    "## [JUDGE] Markdown Format Preservation（Markdown 格式保留）",
    "",
    "原文是 Markdown 时，译文必须 1:1 保留结构与标记，**只译文字不动标记**：",
    "- **逐行对应**：原文每行对应译文一行，不增减行、不合并/拆分、不改换行与空行。",
    "- **标题**：`#` 数量一致，不改层级（`##` 还是 `##`）。",
    "- **列表**：`-`/`*`/`+` 标记与缩进一致，项数一致。",
    "- **表格**：`|` 列数一致，表头分隔行（`|---|`）原样保留，只译单元格文字。",
    "- **粗体/斜体**：`**xxx**`/`*xxx*` 标记保留在对应文字上。",
    "- **引用/代码/链接**：`>` 保留；`` `xxx` `` 与 ` ``` ` 围栏保留且代码内容不译；`[文字](url)` 只译文字，`---` 分隔线保留。",
    "",
]

def _parse_json_envelope(stdout: str) -> dict | None:
    """Parse a JSON envelope from a script's stdout.

    Sub-scripts keep stdout pure JSON (their [WARN] diagnostics go to
    stderr), so a plain json.loads is the whole contract. A parse failure
    returns None and the caller treats the script as crashed — fail-closed,
    never a guess at "probably fine" output.
    """
    try:
        obj = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


def _aggregate_violations(checks: list[dict]) -> list[dict]:
    """Collect the agent-actionable details of every failed guard check.

    Term authority entries carry term / expected_official / severity /
    offending_quote under "violations"; the other checks carry their own
    structured issue lists under "issues". Each aggregated entry is tagged
    with its source check so a BLOCKED report can be fixed without
    re-running the checkers by hand.
    """
    # residue_scan is a strict subset of terminology's issues (derived from the
    # same detector run) — aggregating it would duplicate every residue entry.
    # phase_c also re-runs the residue detector, so a further content-level
    # dedupe by message keeps one entry per independent problem.
    out: list[dict] = []
    seen: set[str] = set()
    for c in checks:
        if c.get("passed") or c.get("name") == "residue_scan":
            continue
        for i in (c.get("violations", []) or []) + (c.get("issues", []) or []):
            entry = {**i, "check": c.get("name", "?")} if isinstance(i, dict)                 else {"check": c.get("name", "?"), "message": str(i)}
            key = str(entry.get("message", "")) + "|" + str(entry.get("term", ""))
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
    return out


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


def _load_lock_terms(lock_path: str | None) -> list[dict]:
    """Read the FULL term lock from the context-lock file built by auto_pipeline pre.

    pre's JSON envelope trims `term_authority.locked_terms` down to a small subset
    (a token optimization), but the lock FILE written next to it holds every term
    that finish's term_authority will actually enforce. The translation pack must
    surface that complete set — otherwise the agent never sees mappings like
    终末之战 -> Ragh Nar Roog until finish rejects the translation, which forces a
    wasteful re-translate round (translate blind, then get corrected). Read the file.

    Returns a list of term dicts (each carrying canonical_en / cn / type / aliases /
    abbrevs). Empty list if the file is missing or unreadable; the caller falls back
    to the trimmed JSON subset in that case.
    """
    if not lock_path:
        return []
    try:
        data = json.loads(Path(lock_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    # Only enforced statuses belong in the MANDATORY table (same set as
    # context_lock's own enforcement filter): ambiguous entries carry an empty
    # official CN and pending entries are "translate by judgment" — rendering
    # either as a mandatory row with an empty Chinese cell contradicts the
    # pack's own ambiguous/pending sections.
    kept = ("confirmed", "auto_locked")
    terms = data.get("terms") or {}
    out: list[dict] = []
    if isinstance(terms, dict):
        for val in terms.values():
            if isinstance(val, dict) and val.get("status") in kept:
                out.append(dict(val))
    elif isinstance(terms, list):
        out = [t for t in terms if isinstance(t, dict) and t.get("status") in kept]
    return out


_CARD_DB_CACHE: tuple[int, bool] | None = None


def _card_db_status() -> tuple[int, bool]:
    """Return (card_count, ready) for the build-time card database.

    card_names_4lang.json is a build-time artifact (gitignored), built by
    build_card_names_reference.py. When it is missing or far below ~1381 cards,
    TermAuthority loads no card names and the lock is silently hollow — the agent
    then translates card names freely with no warning. Shared by build_pack (pack
    banner) and cmd_prepare (status line + ready flag).
    """
    global _CARD_DB_CACHE
    if _CARD_DB_CACHE is not None:
        return _CARD_DB_CACHE
    cards_json = SCRIPTS_DIR.parent / "references" / "card_names_4lang.json"
    count = 0
    if cards_json.exists():
        try:
            count = len(json.loads(cards_json.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError, ValueError):
            count = 0
    _CARD_DB_CACHE = (count, count >= 1000)
    return _CARD_DB_CACHE


_CARD_META_CACHE: dict | None = None


def _load_card_meta() -> dict:
    """Load references/card_meta.json (card type / leader / disloyal flags).

    Used to annotate injected official-effect entries with a direction-relevant
    type tag (leader=provision-reversed, disloyal=power-reversed, unit=normal),
    so the agent applies the Balance Change Direction rule correctly. Cached at
    module level after the first load. Gracefully degrades to an empty dict if the
    file is missing or unreadable — the pack still builds, just without type tags.
    """
    global _CARD_META_CACHE
    if _CARD_META_CACHE is not None:
        return _CARD_META_CACHE
    meta_json = SCRIPTS_DIR.parent / "references" / "card_meta.json"
    try:
        if meta_json.exists():
            _CARD_META_CACHE = json.loads(meta_json.read_text(encoding="utf-8"))
        else:
            _CARD_META_CACHE = {}
    except (json.JSONDecodeError, OSError, ValueError):
        _CARD_META_CACHE = {}
    return _CARD_META_CACHE


def _card_type_tag(english_name: str) -> str:
    """Return a balance-direction type tag for a card name, or '' if unknown.

    Precedence: leader (provision-reversed) > disloyal unit (power-reversed) >
    plain unit. The tag hints which Balance Change Direction sub-rule applies to
    this card's effect, matching the guidance injected into the pack.
    """
    meta = _load_card_meta()
    if not meta or not english_name:
        return ""
    entry = meta.get(english_name.lower().strip())
    if not entry:
        return ""
    if entry.get("is_leader"):
        return "[领袖·人口反向]"
    if entry.get("is_disloyal"):
        return "[间谍单位·战力反向]"
    if entry.get("type") == "Unit":
        return "[单位]"
    return ""


def _ensure_card_db() -> tuple[int, bool]:
    """Ensure card_names_4lang.json is built; auto-build on first run if missing.

    The 4lang DB is a build-time artifact (CDPR copyright, gitignored). On a fresh
    clone with no install.sh run, it is absent and the lock would be silently
    hollow. Auto-build it here instead of failing: prefer a local card-db
    (offline, fast), else fetch online (~3 min, once; cached afterward). This makes
    the skill work out-of-the-box — users need not know to run install.sh first.
    Returns (count, ready) after the attempt.
    """
    count, ready = _card_db_status()
    if ready:
        return count, ready

    print("=" * 60, file=sys.stderr)
    print("[AUTO] Card database (card_names_4lang.json) not built — building now", file=sys.stderr)
    print("[AUTO] First run only; ~3 min if fetching online, needs internet.", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    build_script = SCRIPTS_DIR / "build_card_names_reference.py"
    src_dir = os.environ.get("GWENT_CARD_DB") or str(Path.home() / "gwent-card-db")
    if Path(src_dir).is_dir():
        build_args = ["--src", src_dir]
        print(f"[AUTO] Using local card-db: {src_dir}", file=sys.stderr)
    else:
        build_args = ["--fetch"]
        print("[AUTO] No local card-db found; fetching from api.gwent.one ...", file=sys.stderr)
    try:
        result = subprocess.run(
            [sys.executable, str(build_script), *build_args],
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("[WARN] Auto-build timed out (5 min). Build manually:", file=sys.stderr)
        print("       python scripts/build_card_names_reference.py --fetch", file=sys.stderr)
        return _card_db_status()
    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "").strip()[:200]
        print(f"[WARN] Auto-build failed: {msg}", file=sys.stderr)
        print("[WARN] Build manually: python scripts/build_card_names_reference.py --fetch", file=sys.stderr)
        return _card_db_status()
    print("[AUTO] Card database built.", file=sys.stderr)
    global _CARD_DB_CACHE
    _CARD_DB_CACHE = None  # the file just changed on disk — re-read it fresh
    return _card_db_status()


def build_pack(source_path: Path, direction: str, date: str | None,
               article_type: str, pre_data: dict, lock_built: bool) -> str:
    """Assemble the Markdown translation pack from auto_pipeline pre's JSON output."""
    card_db_count, cards_ready = _card_db_status()

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
    L.append("> **分节标记 Section tags** — content sections below are tagged (NEXT STEP 除外):")
    L.append("> - **[COPY 照抄]** — 现成译文/对照表/官方文本：逐字使用，零创造空间。违反会被 finish 拦下或属事实错误。")
    L.append("> - **[JUDGE 判断]** — 规则与提示：按引导用自己的判断执行（风格、方向、格式、俚语）。")
    L.append("")
    L.append("> **专有名词铁律 Term rule**: 源文里的人名/卡牌名/关键词/机制词/地名，凡疑似昆特牌专有名词，")
    L.append("> 一律以 [COPY] 节的官方译名为准 — **禁止凭记忆自创译名**（自己「记得」的译名可能错）。")
    L.append("> 锁表没锁但你怀疑是卡牌名的词，先查证再翻：")
    L.append(f">   python {SCRIPTS_DIR / 'lookup.py'} \"<词>\" --plain")
    L.append("")

    if not lock_built:
        L.append("> WARNING: context lock failed to build — the MANDATORY term lock")
        L.append("> table below is EMPTY. Translate cautiously and re-run prepare.")
        L.append("")

    if not cards_ready:
        L.append("> **STOP — card database not ready**: `card_names_4lang.json` has only")
        L.append(f"> {card_db_count} cards (expected ~1381). The lock table below is INCOMPLETE")
        L.append("> — card names will NOT be extracted/locked, so they will be translated")
        L.append("> freely (unverified). Build it FIRST, then re-run prepare:")
        L.append(">   python scripts/build_card_names_reference.py   # then re-run prepare")
        L.append("")

    # Style rules
    L.append("## [JUDGE] Style Rules (风格规则)")
    L.append("")
    L.append("| Dimension | Rule |")
    L.append("|-----------|------|")
    for dim, rule in style_rules:
        L.append(f"| {dim} | {rule} |")
    L.append("")

    L.extend(PACK_BALANCE_GUIDE)
    L.extend(PACK_FORMAT_GUIDE)

    # Mandatory term lock table — show the SAME complete lock set that finish's
    # term_authority enforces. pre's JSON `locked_terms` is a token-trimmed subset;
    # the lock FILE has the full set. Fall back to the JSON subset only if the file
    # is unreadable. Cards sorted first (the agent most needs card-name mappings).
    full_terms = _load_lock_terms(pre_data.get("lock_path"))
    lock_rows = full_terms if full_terms else locked
    lock_rows = sorted(lock_rows, key=lambda t: (0 if t.get("type") == "card" else 1,))
    L.append("## [COPY] MANDATORY Term Lock Table (强制术语锁表 — 卡牌在前，照此译名，勿字面直译)")
    L.append("")
    if lock_rows:
        L.append("| English | Chinese | Aliases | Abbrevs |")
        L.append("|---------|---------|---------|---------|")
        for t in lock_rows:
            en = t.get("canonical_en", "")
            cn = t.get("cn") or t.get("chinese", "")
            L.append(
                f"| {en} | {cn} "
                f"| {_join_list(t.get('aliases'))} | {_join_list(t.get('abbrevs'))} |"
            )
    else:
        L.append("_(no enforced terms — the lock held only ambiguous/pending entries; see the sections below)_")
    L.append("")

    # Ambiguous names
    if ambiguous:
        L.append("## [COPY] Ambiguous Names (歧义名 — 按原文语境选一个版本，照抄其全名)")
        L.append("")
        L.append("原文只出现基础名时，按语境线索（括号内）判断是哪个版本，译文用全名：")
        L.append("")
        for a in ambiguous:
            en = a.get("canonical_en") or a.get("extracted", "")
            variants = a.get("variants", []) or []
            if variants:
                vstr = "; ".join(
                    f'{v.get("en", "")}->{v.get("cn", "")}'
                    + (f'（{v["clue"]}）' if v.get("clue") else "")
                    for v in variants
                )
            else:
                vstr = a.get("type", "")
            L.append(f"- **{en}** — {vstr}")
        L.append("")

    # Pending terms
    if pending:
        L.append("## [JUDGE] Pending Terms (待定词 — 参考库没有，凭判断翻；复现就记入)")
        L.append("")
        for p in pending:
            L.append(f"- {p.get('extracted', '')} ({p.get('status', '')})")
        L.append("")

    # Card quick reference
    if card_refs:
        L.append("## [COPY] Card Name Quick Reference (卡名快查 — 官方译名对照)")
        L.append("")
        L.append("| English | Chinese |")
        L.append("|---------|---------|")
        for c in card_refs:
            L.append(f"| {c.get('english', '')} | {c.get('chinese', '')} |")
        L.append("")

    # Official effect text. Each entry is annotated with a card type tag
    # ([领袖·人口反向]/[间谍单位·战力反向]/[单位]) so the agent applies the
    # Balance Change Direction rule correctly when translating effect text.
    if effects:
        L.append("## [COPY] Official Effect Text (官方效果 — 逐字照抄，勿改写)")
        L.append("")
        for e in effects:
            en = e.get("english", "")
            tag = _card_type_tag(en)
            header = f"### {en} -> {e.get('chinese', '')}"
            if tag:
                header += f" {tag}"
            L.append(header)
            L.append("")
            L.append(e.get("official_ability", "") or "")
            L.append("")

    # Slang hints
    if slang:
        L.append("## [JUDGE] Slang / Jargon Hints (俚语提示 — 按意向译，勿字面)")
        L.append("")
        L.append("| English | Intended CN | Note |")
        L.append("|---------|-------------|------|")
        for s in slang:
            L.append(
                f"| {s.get('english', '')} | {s.get('intended_cn', '')} | {s.get('note', '')} |"
            )
        L.append("")

    # Phase C acceptance checklist
    L.append("## [JUDGE] Phase C Acceptance Checklist (验收清单 — 翻完逐条自检)")
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
        f"   python {(SCRIPTS_DIR / 'translate.py').resolve()} finish translated.txt "
        f"--source {source_path.resolve()} --direction {direction}"
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

    # Direction: explicit --direction wins; otherwise auto-detect from the SOURCE
    # (a Chinese source means CN->EN). The old hard default "encn" silently built
    # EN->CN packs for Chinese sources. pre is direction-independent (context_lock
    # build auto-detects with the same source_is_chinese heuristic), so there is
    # no --direction to forward — the two cannot disagree by construction.
    direction_auto = args.direction is None
    if direction_auto:
        try:
            source_text = source_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            if args.json:
                json_output(None, errors=[f"failed to read source file: {e}"], exit_code=1)
            print(f"Error: failed to read source file {source_path}: {e}")
            sys.exit(1)
        direction = "cnen" if source_is_chinese(source_text) else "encn"
    else:
        direction = args.direction
    article_type = args.type

    # Ensure the card DB BEFORE pre (pre loads it via TermAuthority; a missing DB
    # would silently produce a hollow lock). Auto-builds on first run.
    card_db_count, cards_ready = _ensure_card_db()

    # effect_text is an enhancement layer (official ability text injection). If
    # missing, translation still works — just warn, don't auto-build (slow fetch).
    if not (SCRIPTS_DIR.parent / "references" / "effect_text.json").exists():
        print("[INFO] effect_text.json 缺失（官方效果逐字注入不可用，翻译照跑）。", file=sys.stderr)
        print("       想补跑: python scripts/build_effect_reference.py --fetch  (约 3 分钟)", file=sys.stderr)

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

    pack_path = source_path.with_name(source_path.stem + ".pack.md")
    pack_content = build_pack(source_path, direction, args.date, article_type, pre_data, lock_built)
    try:
        pack_path.write_text(pack_content, encoding="utf-8")
    except OSError as e:
        if args.json:
            json_output(None, errors=[f"failed to write pack: {e}"], exit_code=1)
        print(f"Error: failed to write pack to {pack_path}: {e}")
        sys.exit(1)

    # Bind the pack to its source: snapshot the lock next to the pack (same
    # naming convention), stamped with the source's content hash. finish
    # reuses this snapshot instead of rebuilding, and refuses to gate against
    # a source that changed after prepare (unless --allow-source-changed) —
    # closing the window where the agent translates pack A but the gate
    # rebuilds its lock from a mutated source.
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    lock_src = Path(pre_data.get("lock_path", "")) if pre_data.get("lock_path") else None
    lock_sidecar = source_path.with_name(source_path.stem + ".lock.json")
    if lock_src and lock_src.exists():
        try:
            lock_json = json.loads(lock_src.read_text(encoding="utf-8"))
            lock_json["_prepare_meta"] = {"source_sha256": source_sha}
            lock_sidecar.write_text(json.dumps(lock_json, ensure_ascii=False), encoding="utf-8")
        except (OSError, json.JSONDecodeError) as e:
            print(f"[WARN] lock sidecar not written ({e}); finish will rebuild from source", file=sys.stderr)
            lock_sidecar = None

    ready = lock_built and pre_exit_code == 0 and cards_ready

    data = {
        "command": "prepare",
        "source": str(source_path),
        "direction": direction,
        "direction_auto_detected": direction_auto,
        "date": args.date or "auto",
        "type": article_type,
        "pack_path": str(pack_path),
        "pre_exit_code": pre_exit_code,
        "lock_built": lock_built,
        "lock_sidecar": str(lock_sidecar) if lock_sidecar else None,
        "source_sha256": source_sha,
        "term_counts": {
            "locked": pre_data.get("term_authority", {}).get("locked_count", 0),
            "ambiguous": pre_data.get("term_authority", {}).get("ambiguous_count", 0),
            "pending": pre_data.get("term_authority", {}).get("pending_count", 0),
        },
        "ready": ready,
        "cards_ready": cards_ready,
        "card_db_count": card_db_count,
    }

    if args.json:
        json_output(data, exit_code=0 if ready else 1)

    # Human-readable
    print("=" * 60)
    print("TRANSLATE — PREPARE")
    print("=" * 60)
    print(f"\nSource:    {source_path}")
    print(f"Direction: {'EN->CN' if direction == 'encn' else 'CN->EN'}"
          f"{' (auto-detected from source)' if direction_auto else ''}")
    print(f"Pack:      {pack_path}")
    print(f"Lock:      {'built' if lock_built else 'FAILED (pack written with empty lock table)'}")
    print(f"CardDB:    {card_db_count} cards {'(READY)' if cards_ready else '(NOT READY — run build_card_names_reference.py, then re-run prepare)'}")
    print(f"Terms:     {data['term_counts']['locked']} locked, "
          f"{data['term_counts']['ambiguous']} ambiguous, "
          f"{data['term_counts']['pending']} pending")
    print("")
    if ready:
        print("[PASS] Pack ready. Read it, translate the source, then run:")
        print(f"  python {(SCRIPTS_DIR / 'translate.py').resolve()} finish <translated> "
              f"--source {source_path.resolve()} --direction {direction}")
    else:
        if not cards_ready:
            print(f"[WARN] Card database NOT ready ({card_db_count} cards). Lock table is INCOMPLETE")
            print("       — card names will not be verified. Build it, then re-run prepare:")
            print("           python scripts/build_card_names_reference.py")
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

    # Hard gate. Prefer the prepare-time lock snapshot (pack/lock binding):
    # reusing it guarantees the gate judges against the same term set the
    # agent translated from. A source that changed after prepare invalidates
    # the snapshot — refuse unless --allow-source-changed (the right fix is
    # re-running prepare so pack and gate stay in sync).
    lock_sidecar = source_path.with_name(source_path.stem + ".lock.json")
    lock_reused = False
    source_changed = False
    block_before_guard = None
    guard_args = [str(translated_path), "--direction", direction]
    if lock_sidecar.exists():
        try:
            sidecar_meta = json.loads(lock_sidecar.read_text(encoding="utf-8")).get("_prepare_meta", {})
        except (OSError, json.JSONDecodeError):
            sidecar_meta = {}
        current_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
        if sidecar_meta.get("source_sha256") and sidecar_meta["source_sha256"] != current_sha:
            source_changed = True
            if not args.allow_source_changed:
                block_before_guard = (
                    "source changed after prepare: the pack's term lock is stale. "
                    "Re-run prepare on the current source (or pass --allow-source-changed "
                    "to gate against a freshly rebuilt lock)."
                )
        if not source_changed:
            guard_args.extend(["--lock", str(lock_sidecar)])
            lock_reused = True
        # A changed source NEVER reuses the snapshot: --allow-source-changed
        # only bypasses the BLOCK above, and the gate then rebuilds its lock
        # from the CURRENT source — that is the documented contract.
    if not lock_reused:
        guard_args.extend(["--source", str(source_path)])
        # No prepare snapshot next to this source. Usually fine (prepare was
        # run elsewhere / old layout), but the #1 cause is a mistyped or
        # wrong --source — the gate would then verify against a DIFFERENT
        # article's terms. Name the snapshots that DO exist nearby so the
        # caller can spot the mismatch at a glance instead of debugging
        # weird violations later.
        siblings = sorted(source_path.parent.glob("*.lock.json"))
        if siblings and not lock_sidecar.exists():
            names = ", ".join(s.stem.replace(".lock", "") for s in siblings[:5])
            print(
                f"[WARN] no prepare snapshot for this source ({lock_sidecar.name} missing) — "
                f"the gate rebuilds its lock from the given file. Prepared sources here: {names}. "
                f"If that list doesn't include this source, fix --source.",
                file=sys.stderr,
            )
    # Always ask guard for the full violation lists. The fix loop consumes
    # finish's violations to repair the file in one pass — it needs every
    # entry with its expected_official, not a top-5 sample. Guard's default
    # top-N is a token guard for humans; machine-to-machine, the full list
    # is cheaper than a re-run.
    guard_args.append("--verbose-terms")
    if args.lite:
        guard_args.append("--lite")

    if block_before_guard:
        data = {
            "command": "finish",
            "translated": str(translated_path),
            "source": str(source_path),
            "direction": direction,
            "direction_warning": direction_warning,
            "blocked": True,
            "block_reason": block_before_guard,
            "lock_reused": False,
            "source_changed": True,
            "violations": [],
            "violations_total": 0,
            "guard_exit_code": None,
            "guard_all_passed": None,
            "guard": None,
            "learn": None,
            "effect_check": None,
        }
        if args.json:
            json_output(data, errors=[block_before_guard], exit_code=1)
        print("=" * 60)
        print("TRANSLATE — FINISH (HARD GATE)")
        print("=" * 60)
        print(f"\nTranslated: {translated_path}")
        print(f"Source:     {source_path}")
        print("")
        print(f"[BLOCKED] {block_before_guard}")
        sys.exit(1)
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
    # WITHOUT ever checking terminology. We refuse to trust that in EITHER
    # direction: the term_authority check MUST have actually run (status=="ran"),
    # or we BLOCK.
    block_reason: str | None = None
    if not all_passed:
        failed = [c for c in checks if not c.get("passed")]
        block_reason = "guard checks failed: " + "; ".join(
            c.get("message", c.get("name", "?")) for c in failed
        )
    else:
        # Fail-closed for BOTH directions: term_authority must have actually run
        # (status=="ran"). The CN->EN direction now enforces official English too
        # (it is no longer "not_applicable"), so a skipped/missing check in EITHER
        # direction means terminology was NOT verified — refuse to trust the
        # guard's PASS. Absence of the signal must block (not pass).
        ta_check = next((c for c in checks if c.get("name") == "term_authority"), None)
        if ta_check is None or ta_check.get("status") != "ran":
            status = ta_check.get("status") if ta_check else "missing"
            block_reason = (
                "context lock could not be built from source; term authority unverifiable "
                f"(status={status}). The guard reported PASS, but terminology "
                "was NOT actually checked. Treat as BLOCKED."
            )

    blocked = block_reason is not None

    # Agent-actionable details of every failed check, top-level, tagged with
    # the source check (see _aggregate_violations).
    violations = _aggregate_violations(checks)
    # Independent-problem total: per-check issue_count sums double-count the
    # same problem across overlapping checks (residue lives in terminology
    # AND phase_c), so the deduped aggregate is the honest number. The raw
    # per-check counts stay visible in guard.checks[].
    violations_total = len(violations)

    # Learn only after a genuine PASS; never let it affect the gate.
    learn_result = None
    if not blocked and not getattr(args, "lite", False):
        # Lite mode skips learn: chat snippets pollute the pending buffer
        # (see the BC34 noise rejections) and learn is article-grade.
        _lok, lparsed, _lraw = run_script_json(
            "learn.py", [str(source_path), "--auto"], LEARN_TIMEOUT
        )
        if lparsed and "data" in lparsed:
            learn_result = lparsed["data"]

    # Official-effect verbatim check — INFORMATIONAL ONLY, never blocks: tells
    # the agent which locked cards' official ability text was not copied
    # verbatim (the pack asked for verbatim injection; a miss is a quality
    # signal, not a gate failure). Runs in both PASS and BLOCK paths; skipped
    # in lite mode (chat snippets rarely quote effects verbatim).
    effect_check = None
    if not args.lite:
        _eok, eparsed, _eraw = run_script_json(
            "effect_verifier.py", [str(source_path), str(translated_path)], EFFECT_TIMEOUT
        )
        if eparsed and isinstance(eparsed.get("data"), dict):
            ed = eparsed["data"]
            effect_check = {
                "checked": ed.get("checked", 0),
                "not_found_count": len(ed.get("not_found", []) or []),
                # Bounded by the pack's OFFICIAL_EFFECTS_CAP (~20); emit in full —
                # an agent auditing effect fidelity wants the complete list.
                "not_found_terms": [i.get("english", "?") for i in ed.get("not_found", []) or []],
            }

    data = {
        "command": "finish",
        "translated": str(translated_path),
        "source": str(source_path),
        "direction": direction,
        "direction_warning": direction_warning,
        "guard_exit_code": guard_exit_code,
        "guard_all_passed": all_passed,
        "lock_reused": lock_reused,
        "source_changed": source_changed,
        "guard": guard_data,
        "blocked": blocked,
        "block_reason": block_reason,
        "violations": violations,
        "violations_total": len(violations),
        "learn": learn_result,
        "effect_check": effect_check,
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
        print("[PASS] Guard: all checks passed.")
        if lock_reused:
            print("       Lock: reused the prepare-time snapshot (pack/gate in sync).")
        if learn_result is not None:
            learned = learn_result.get("added_to_buffer", 0) if isinstance(learn_result, dict) else 0
            print(f"       Learn: recorded {learned} new term(s) to the auto buffer"
                  " (merge with: python scripts/learn.py --commit).")
        elif args.lite:
            print("       Learn: skipped (--lite: chat-length content).")
        if effect_check and effect_check["not_found_count"]:
            print(f"       Effect: {effect_check['not_found_count']} official effect(s)"
                  " not verbatim (informational — see JSON effect_check).")
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
        if violations or violations_total:
            shown = violations[:20]
            print("")
            print(f"Violations ({violations_total} total, showing {len(shown)}; full list in --json output):")
            for v in shown:
                print(f"   - [{v.get('check', '?')}] {format_issue(v)}")
        print("")
        print("[BLOCKED] DO NOT FINALIZE. Fix the issue(s) above and re-run:")
        print(f"  python {(SCRIPTS_DIR / 'translate.py').resolve()} finish {translated_path} "
              f"--source {source_path.resolve()} --direction {direction}")

    sys.exit(exit_code)


def cmd_run(args: argparse.Namespace) -> None:
    """One-shot orchestration around the two deterministic stages.

    Shells out to prepare/finish as sibling processes (same pattern as
    finish -> guard): each stage keeps its own output and exit semantics
    untouched, so run is pure glue.

    - Without --translated: run prepare, then print the exact finish command
      with paths pre-resolved — the copy-paste answer to hand-assembled
      paths (the #1 friction dsh reported).
    - With --translated: prepare + finish back to back — re-gating an
      existing translation (e.g. after a source edit) in one command.
    """
    source_path = Path(args.source)
    self_py = (SCRIPTS_DIR / "translate.py").resolve()

    prep_cmd = [sys.executable, str(self_py), "prepare", str(source_path)]
    if args.date:
        prep_cmd.extend(["--date", args.date])
    prep_cmd.extend(["--type", args.type])
    if args.direction:
        prep_cmd.extend(["--direction", args.direction])

    print("=" * 60)
    print("TRANSLATE — RUN (stage 1/2: prepare)")
    print("=" * 60)
    prep_rc = subprocess.run(prep_cmd).returncode
    if prep_rc != 0:
        print("\n[RUN] prepare failed — fix the reported problem and re-run.")
        sys.exit(prep_rc)

    # Same auto-detect rule prepare uses (Chinese source -> cnen), so the
    # printed finish command carries an explicit, trustworthy direction.
    direction = args.direction or (
        "cnen" if source_is_chinese(source_path.read_text(encoding="utf-8")) else "encn"
    )

    translated_path = Path(args.translated) if args.translated else None
    if translated_path is None:
        print()
        print("=" * 60)
        print("TRANSLATE — RUN (stage 2 is YOURS: translate)")
        print("=" * 60)
        print("")
        print("[RUN] Pack ready. Read the pack, translate the full source, save it,")
        print("then run EXACTLY this command (paths pre-resolved):")
        print("")
        print(f"  python {self_py} finish <translated> --source {source_path.resolve()} --direction {direction}")
        print("")
        print("With the translation already saved, the whole gate in one command:")
        print(f"  python {self_py} run {source_path.resolve()} --translated <translated> --direction {direction}")
        sys.exit(0)

    if not translated_path.exists():
        print(f"\n[RUN] translated file not found: {translated_path}")
        sys.exit(1)

    print()
    print("=" * 60)
    print("TRANSLATE — RUN (stage 2/2: finish gate)")
    print("=" * 60)
    fin_cmd = [
        sys.executable, str(self_py), "finish", str(translated_path),
        "--source", str(source_path.resolve()), "--direction", direction,
    ]
    if args.allow_source_changed:
        fin_cmd.append("--allow-source-changed")
    if args.lite:
        fin_cmd.append("--lite")
    sys.exit(subprocess.run(fin_cmd).returncode)


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
        help="Direction for the pack banner + style table (default: auto-detected from source)",
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
    fin.add_argument("--allow-source-changed", action="store_true",
                     help="Gate against a freshly rebuilt lock even when the source changed "
                          "after prepare (default: BLOCK until prepare is re-run)")
    fin.add_argument("--lite", action="store_true",
                     help="Lite mode (chat-length content): skips the Phase C style/format rules "
                          "(incl. bare-N费 provision wording, passive voice, Chinese numerals, brackets), "
                          "learn, and the effect audit — term locks/residue/term-authority still gate")

    runp = subparsers.add_parser(
        "run",
        help="prepare, then (with --translated) finish in one shot; without it, print the exact finish command",
    )
    runp.add_argument("source", help="Source file to translate")
    runp.add_argument("--translated", help="Existing translation file: gate it right after prepare")
    runp.add_argument("--date", help="Article date (YYYY-MM)")
    runp.add_argument(
        "--type",
        choices=["meta", "bc-proposal", "card-analysis", "patch-notes", "general"],
        default="general",
        help="Article type (default: general)",
    )
    runp.add_argument(
        "--direction", choices=["encn", "cnen"],
        help="Direction for the pack banner + style table (default: auto-detected from source)",
    )
    runp.add_argument("--allow-source-changed", action="store_true",
                     help="Forwarded to finish when --translated is given")
    runp.add_argument("--lite", action="store_true",
                      help="Forwarded to finish when --translated is given (chat-length gate)")

    args = parser.parse_args()
    if args.command == "prepare":
        cmd_prepare(args)
    elif args.command == "finish":
        cmd_finish(args)
    elif args.command == "run":
        cmd_run(args)


if __name__ == "__main__":
    main()
