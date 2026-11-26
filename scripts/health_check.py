#!/usr/bin/env python3
"""
Gwent Translation Skill Health Check.
Verifies all components are present and functional.

Usage:
    python health_check.py [--verbose]
"""

import ast
import argparse
import json
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from _shared import json_output, parse_markdown_table, run_utf8


_no_color = False


def color(status: str) -> str:
    """Return color code for terminal output."""
    if _no_color or not sys.stdout.isatty():
        return ""
    colors = {
        "PASS": "\033[32m",   # Green
        "FAIL": "\033[31m",   # Red
        "WARN": "\033[33m",   # Yellow
        "INFO": "\033[36m",   # Cyan
        "RESET": "\033[0m",
    }
    return colors.get(status, "")


def check_file_exists(path: Path, desc: str) -> tuple[str, str]:
    """Check if a file exists."""
    if path.exists():
        return "PASS", f"{desc}: {path.name}"
    else:
        return "FAIL", f"{desc}: {path.name} (missing)"


def check_reference_files(ref_dir: Path) -> list[tuple[str, str]]:
    """Check all reference files."""
    results = []

    required_refs = [
        ("correction_guide.md", "Correction rules"),
        ("style_reference.md", "Style examples"),
        ("terminology_map.md", "Terminology map"),
        ("reverse_terminology_map.md", "Reverse terminology map (CN→EN)"),
        ("keywords_map.md", "Keyword translations"),
        ("card_overrides.md", "Card name overrides (aliases/renamed)"),
        ("ambiguous_names.md", "Ambiguous names"),
        ("competitive_terms.md", "Competitive terms"),
        ("common_pitfalls.md", "Common pitfalls"),
        ("category_map.md", "Category map"),
        ("card_attributes_map.md", "Card attributes (rarity/faction) map"),
        ("version_map.md", "Version map"),
        ("style_fingerprint.md", "Style fingerprint"),
        ("cn_fuzzy_fixes.md", "Chinese fuzzy fixes"),
        ("pending_terms.template.md", "Pending terms template (tracked; install.sh seeds the buffer from it)"),
        ("changelog.md", "Changelog"),
        ("phase_c_checklist.md", "Phase C checklist"),
        ("slang_map.md", "Slang & jargon map"),
    ]

    for fname, desc in required_refs:
        status, msg = check_file_exists(ref_dir / fname, desc)
        results.append((status, msg))

    return results


def check_scripts(script_dir: Path) -> list[tuple[str, str]]:
    """Check all script files."""
    results = []

    required_scripts = [
        ("check_translation.py", "Terminology checker"),
        ("learn.py", "Learning system"),
        ("context_lock.py", "Context lock"),
        ("format_skeleton.py", "Format skeleton"),
        ("diff_review.py", "Diff review"),
        ("backtranslate.py", "Back-translation"),
        ("term_enforcer.py", "Term authority enforcer"),
        ("auto_pipeline.py", "Auto pipeline"),
        ("completeness_guard.py", "Completeness guard"),
        ("phase_c_check.py", "Phase C checker"),
    ]

    for fname, desc in required_scripts:
        fpath = script_dir / fname
        status, msg = check_file_exists(fpath, desc)

        if status == "PASS":
            # Check syntax without executing to avoid side effects
            try:
                ast.parse(fpath.read_text(encoding="utf-8"))
                results.append(("PASS", f"{desc}: {fname} (syntax OK)"))
            except SyntaxError as e:
                results.append(("FAIL", f"{desc}: {fname} (syntax error: {e})"))
        else:
            results.append((status, msg))

    return results


def check_skill_file(skill_path: Path) -> list[tuple[str, str]]:
    """Check SKILL.md structure."""
    results = []

    if not skill_path.exists():
        results.append(("FAIL", "SKILL.md: missing"))
        return results

    text = skill_path.read_text(encoding="utf-8")

    # Check required sections
    required_sections = [
        "## Overview",
        "## When to Use",
        "## Translation Workflow",
        "## Quick Reference",
    ]

    for section in required_sections:
        if section in text:
            results.append(("PASS", f"SKILL.md: Contains {section}"))
        else:
            results.append(("FAIL", f"SKILL.md: Missing {section}"))

    # Check the workflow steps actually documented in SKILL.md (Step 1/2/3 of
    # the translate.py pipeline). This replaces a dead "### Phase" count — the
    # Phase A-E structure no longer exists in SKILL.md.
    step_headings = [
        "### Step 1: Prepare",
        "### Step 2: Translate",
        "### Step 3: Finish",
    ]
    missing_steps = [s for s in step_headings if s not in text]
    if missing_steps:
        results.append(("FAIL", f"SKILL.md: Missing workflow steps {missing_steps}"))
    else:
        results.append(("PASS", "SKILL.md: 3 workflow steps (Prepare/Translate/Finish) defined"))

    # Check for special modes
    if "Diff Review Mode" in text:
        results.append(("PASS", "SKILL.md: Diff Review Mode documented"))
    if "Back-Translation" in text:
        results.append(("PASS", "SKILL.md: Back-Translation documented"))

    return results


def check_data_integrity(ref_dir: Path) -> list[tuple[str, str]]:
    """Check data integrity in reference files."""
    results = []

    # Card name data is split: generated 4lang table (build-time) + hand overrides.
    json4 = ref_dir / "card_names_4lang.json"
    if json4.exists():
        try:
            import json
            n = len(json.loads(json4.read_text(encoding="utf-8")))
            results.append(("PASS", f"card_names_4lang.json: {n} 卡牌名（4 语种）"))
        except Exception as exc:  # noqa: BLE001
            results.append(("FAIL", f"card_names_4lang.json: 解析失败 ({exc})"))
    else:
        results.append(("WARN", "card_names_4lang.json: 未构建（运行 "
                        "python3 scripts/build_card_names_reference.py 生成）"))

    # Check terminology_map.md has tables
    term_file = ref_dir / "terminology_map.md"
    if term_file.exists():
        text = term_file.read_text(encoding="utf-8")
        rows = parse_markdown_table(text, min_columns=2)
        table_count = len(rows)
        results.append(("PASS", f"terminology_map.md: {table_count} rows found"))

    # pending_terms.md is gitignored runtime data (learn.py review inbox);
    # legitimate to be missing (fresh install pending seed, git-archive deploys),
    # so presence is INFO/WARN, never a required FAIL.
    pending_file = ref_dir / "pending_terms.md"
    if pending_file.exists():
        lines = pending_file.read_text(encoding="utf-8").split("\n")
        pending_count = sum(1 for l in lines if l.startswith("### "))
        results.append(("INFO", f"pending_terms.md: {pending_count} terms pending review"))
    else:
        results.append(("WARN", "pending_terms.md missing (runtime data; seeded from template by install.sh)"))

    # Check changelog has entries
    changelog = ref_dir / "changelog.md"
    if changelog.exists():
        text = changelog.read_text(encoding="utf-8")
        version_count = text.count("## ")
        results.append(("INFO", f"changelog.md: {version_count} versions recorded"))

    return results


def check_phase_c_checklist(ref_dir: Path) -> list[tuple[str, str]]:
    """Validate phase_c_checklist.md structure and regex patterns."""
    results = []
    checklist = ref_dir / "phase_c_checklist.md"
    if not checklist.exists():
        results.append(("FAIL", "phase_c_checklist.md: missing"))
        return results

    text = checklist.read_text(encoding="utf-8")
    rows = parse_markdown_table(text, min_columns=5)
    if not rows:
        results.append(("WARN", "phase_c_checklist.md: no rule rows parsed"))
        return results

    required_keys = {"id", "description", "check_type", "pattern", "issue_message"}
    regex_types = {"regex", "regex_forbidden", "regex_required"}
    seen_ids: set[str] = set()
    regex_ok_count = 0
    regex_fail_count = 0

    for idx, row in enumerate(rows, start=1):
        missing = required_keys - set(row.keys())
        if missing:
            results.append((
                "FAIL",
                f"phase_c_checklist.md row {idx}: missing columns {', '.join(sorted(missing))}",
            ))
            continue

        rid = row.get("id", "").strip()
        if not rid:
            results.append(("FAIL", f"phase_c_checklist.md row {idx}: empty rule ID"))
            continue
        if rid in seen_ids:
            results.append(("FAIL", f"phase_c_checklist.md: duplicate rule ID '{rid}'"))
        seen_ids.add(rid)

        check_type = row.get("check_type", "").strip().lower()
        if check_type not in {
            "regex",
            "regex_forbidden",
            "regex_required",
            "reference",
            "manual",
        }:
            results.append((
                "WARN",
                f"phase_c_checklist.md: rule '{rid}' has unknown check_type '{check_type}'",
            ))

        pattern = row.get("pattern", "").strip()
        if check_type in regex_types:
            raw = pattern.strip("`")
            raw = raw.replace("\\|", "|")
            if not raw:
                results.append((
                    "FAIL",
                    f"phase_c_checklist.md: rule '{rid}' has empty regex pattern",
                ))
                regex_fail_count += 1
                continue
            try:
                re.compile(raw)
                regex_ok_count += 1
            except re.error as e:
                results.append((
                    "FAIL",
                    f"phase_c_checklist.md: rule '{rid}' invalid regex: {e}",
                ))
                regex_fail_count += 1

    results.append((
        "INFO",
        f"phase_c_checklist.md: {len(rows)} rules, {regex_ok_count} valid regex patterns",
    ))
    if regex_fail_count == 0 and len(seen_ids) == len(rows):
        results.append(("PASS", "phase_c_checklist.md: structure and regex patterns valid"))

    return results


# Faction abbreviation -> expected canonical EN (lower). Invariant:
# card_attributes_map faction spellings must stay byte-aligned with
# terminology_map / reverse_terminology_map so each abbreviation attaches to the
# AUTHORITATIVE entry (first-wins), not a parallel non-authoritative one.
_FACTION_ABBREV_EXPECTED = {
    "NR": "northern realms", "NG": "nilfgaard", "MO": "monsters",
    "SK": "skellige", "ST": "scoia'tael", "SY": "syndicate", "NE": "neutral",
}


def check_term_authority_invariants(script_dir: Path) -> list[tuple[str, str]]:
    """C2 guard: faction abbreviations resolve to the right canonical, and no
    faction other than Neutral is sourced from card_attributes_map.md (which
    would mean a spelling drift created a parallel, non-authoritative entry that
    dilutes the user's "强制用既定译法" guarantee)."""
    results = []
    try:
        from _shared import get_term_authority
        ta = get_term_authority()
    except Exception as exc:  # noqa: BLE001
        results.append(("FAIL", f"TermAuthority invariants: 无法加载 ({exc})"))
        return results

    bad = []
    for abbr, expected in _FACTION_ABBREV_EXPECTED.items():
        r = ta.resolve(abbr)
        if not r or r["canonical_en"].lower() != expected:
            bad.append(f"{abbr}->{r['canonical_en'] if r else 'NONE'}")
    if bad:
        results.append(("FAIL", f"阵营缩写解析错: {', '.join(bad)}"))
    else:
        results.append(("PASS", "7 阵营缩写 (NR/NG/MO/SK/ST/SY/NE) 解析正确"))

    # H3 回归守护：competitive_terms.md 缩写列用分号分隔（Provision 的 "Porv; cost; p"），
    # 旧代码 abbrev.split(",") 会得到整坨 ["Porv; cost; p"]，三个子别名都 resolve 不到。
    r = ta.resolve("Provision")
    prov_abbrevs = {a.lower() for a in (r.get("abbrevs", []) if r else [])}
    if {"porv", "cost", "p"} <= prov_abbrevs:
        results.append(("PASS", "Provision 分号缩写 (Porv; cost; p) 正确切分"))
    else:
        results.append(("FAIL", f"H3 回归: Provision 缩写切分错，得 {sorted(prov_abbrevs)}"))

    drifted = [
        e["canonical_en"] for e in ta._entries.values()
        if e.get("type") == "faction"
        and e.get("source") == "card_attributes_map.md"
        and e["canonical_en"].lower() != "neutral"
    ]
    if drifted:
        results.append(("FAIL", f"阵营名从 card_attributes 取得权威来源（拼写漂移）: {', '.join(drifted)}"))
    else:
        results.append(("PASS", "已有阵营名权威来源正常（terminology/reverse/competitive）"))
    return results


def check_ambiguous_names(ref_dir: Path) -> list[tuple[str, str]]:
    """ambiguous_names.md must match card_names_4lang.json verbatim.

    The file is hand-curated and drifted for months (phantom EN names like
    'Dana Meadbh'/'Regis: Rebirth', renamed cards, one header that failed
    the base-name regex and silently attached its rows to the previous
    group) because nothing cross-checked it against the card database.
    This invariant closes that hole. Beyond per-variant EN existence + CN
    verbatim match and header-parse accounting, two reconciliation guards
    cover the silent-loss blind spots the review found:

      - row-level: a malformed row swallowed by BOTH parsers (each accepts
        a slightly different column shape) used to pass; now the raw
        accepted-row count must equal both parsers' variant totals
      - second parser: check_translation.load_ambiguous_names (CN-keyed,
        powers the CN bare-name gate) requires "versions" in the header —
        a header losing that word used to silently drop the whole group
        from the CN gate while health stayed green

    Clue-column faction tokens (NR/NG/.../Neutral) are checked against the
    card's real faction when gwent-card-db is available (GWENT_CARD_DB env
    or ~/gwent-card-db); otherwise that sub-check degrades to INFO.

    card_names_4lang.json is a build-time artifact (CDPR data, not
    committed); when missing the whole check degrades to INFO, mirroring
    check_effect_text."""
    results = []
    db_path = ref_dir / "card_names_4lang.json"
    md_path = ref_dir / "ambiguous_names.md"
    if not md_path.exists():
        # required_refs already FAILs a missing file; avoid double-counting
        # (same idiom as check_card_overrides_quality).
        return results
    if not db_path.exists():
        results.append(("INFO", "ambiguous_names: card_names_4lang.json 未构建，跳过对照"
                        "（运行 build_card_names_reference.py 后自动核验）"))
        return results
    try:
        import json
        en2cn = {c["en"]: c["cn"]
                 for c in json.loads(db_path.read_text(encoding="utf-8")).values()
                 if c.get("en")}
    except Exception as exc:  # noqa: BLE001
        results.append(("WARN", f"ambiguous_names: card_names_4lang.json 解析失败 ({exc})"))
        return results

    from _shared import get_term_authority
    ta = get_term_authority()

    bad = []
    for base, variants in ta._ambiguous.items():
        for v in variants:
            if v["en"] not in en2cn:
                bad.append(f"幽灵卡名 [{base}] {v['en']}")
            elif en2cn[v["en"]] != v["cn"]:
                bad.append(f"CN漂移 [{base}] {v['en']} '{v['cn']}' != '{en2cn[v['en']]}'")

    header_count = sum(
        1 for line in md_path.read_text(encoding="utf-8").split("\n")
        if line.startswith("## ") and "(" in line
    )
    if header_count != len(ta._ambiguous):
        bad.append(f"表头解析失败: 文件 {header_count} 个组头只加载了 {len(ta._ambiguous)} 组"
                   "（行会挂到上一组）")

    ta_total = sum(len(v) for v in ta._ambiguous.values())

    # Second-parser reconciliation: the CN-keyed loader behind the CN
    # bare-name gate must see exactly the same groups and rows.
    from check_translation import load_ambiguous_names
    amb2 = load_ambiguous_names()
    if len(amb2) != len(ta._ambiguous):
        bad.append(f"check_translation 解析器组数 {len(amb2)} != _shared {len(ta._ambiguous)}"
                   "（CN 门禁表头需含 'versions'）")
    p2_total = sum(len(v) for v in amb2.values())
    if p2_total != ta_total:
        bad.append(f"解析器变体总数不一致: check_translation {p2_total} vs _shared {ta_total}")

    # Row-level reconciliation: count EVERY data line (starts with '|',
    # not a separator/header row) — NOT rows the parsers happen to accept.
    # Counting by parser acceptance lets a row collapsed below the parsers'
    # column threshold vanish from all counters at once and pass silently.
    raw_rows = 0
    for line in md_path.read_text(encoding="utf-8").split("\n"):
        s = line.strip()
        if s.startswith("|") and "---" not in s and "Full Name" not in s:
            raw_rows += 1
    if raw_rows != ta_total:
        bad.append(f"表格行数 {raw_rows} != 加载变体数 {ta_total}（畸形行被解析器静默吞下）")

    # Clue-column faction tokens must equal the card's real faction.
    import os
    gdb = Path(os.environ.get("GWENT_CARD_DB") or Path.home() / "gwent-card-db") / "tables" / "cards_en.json"
    if gdb.exists():
        try:
            fac_of = {c["name"]: c["faction"]
                      for c in json.loads(gdb.read_text(encoding="utf-8"))}
            fac_map = {"NR": "Northern Realms", "NG": "Nilfgaard", "MO": "Monster",
                       "SK": "Skellige", "ST": "Scoiatael", "SY": "Syndicate",
                       "NE": "Neutral", "Neutral": "Neutral"}
            import re as _re
            # (?<![Nn]on-) skips ability-text compounds like "non-Neutral
            # units" — a hyphen is a word boundary, so the faction token
            # inside such a compound is not a faction claim about the card.
            fac_re = _re.compile(r"(?<![Nn]on-)\b(NR|NG|MO|SK|ST|SY|NE|Neutral)\b")
            for base, variants in ta._ambiguous.items():
                for v in variants:
                    real = fac_of.get(v["en"])
                    if not real:
                        continue
                    for m in fac_re.finditer(v["clue"]):
                        if fac_map[m.group(1)] != real:
                            bad.append(f"线索阵营错 [{base}] {v['en']}: '{m.group(1)}' 实为 {real}")
        except Exception as exc:  # noqa: BLE001
            results.append(("WARN", f"ambiguous_names: 线索阵营校验失败 ({exc})"))
    else:
        results.append(("INFO", "ambiguous_names: 线索阵营词校验需 gwent-card-db"
                        "（GWENT_CARD_DB 或 ~/gwent-card-db），未找到已跳过"))

    if bad:
        shown = "; ".join(bad[:8])
        extra = f"（共 {len(bad)} 处）" if len(bad) > 8 else ""
        results.append(("FAIL", "ambiguous_names.md 与卡库不一致: " + shown + extra))
    else:
        results.append(("PASS", f"ambiguous_names.md: {len(ta._ambiguous)} 组 {ta_total} 行"
                        "与卡库逐字一致，双解析器对齐"))
    return results


def check_effect_text(ref_dir: Path) -> list[tuple[str, str]]:
    """effect_text.json is a build-time artifact (CDPR data, NOT committed — see
    NOTICE), generated by build_effect_reference.py --fetch at install time. A
    missing file is NOT repo corruption: translation runs fine via graceful
    degrade (_load_effect_text returns empty; only official-effect verbatim
    injection is disabled). So a missing file is INFO with a build hint, not
    FAIL. The parse/count checks still run when the file exists so a
    truncated/corrupt build cannot silently disable effect injection."""
    results = []
    path = ref_dir / "effect_text.json"
    if not path.exists():
        results.append(("INFO", "effect_text.json: 未构建（运行 "
                        "python3 scripts/build_effect_reference.py --fetch 生成）。"
                        "基础翻译不受影响，仅官方卡牌效果逐字注入不可用。"))
        return results
    try:
        import json
        count = len(json.loads(path.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001
        results.append(("FAIL", f"effect_text.json: 解析失败 ({exc})"))
        return results
    if count >= 1000:  # aligned with build_effect_reference.py MIN_HEALTHY_CARDS
        results.append(("PASS", f"effect_text.json: 可解析，{count} 张卡官方效果"))
    else:
        results.append(("WARN", f"effect_text.json: 仅 {count} 条（预期 ~1366），可能损坏"))
    return results


def check_card_overrides_quality(ref_dir: Path) -> list[tuple[str, str]]:
    """Data-quality checks for the hand-maintained card overrides.

    Guards the two dirty points the rebuild fixed from regressing back in:
      - the stale `Unseen Elder -> Overwhelming Hunger` leader alias (it
        mis-resolved the unit card Unseen Elder=暗影长者 to the leader
        Overwhelming Hunger=无尽渴望);
      - the Dagon bidirectional EN aliases (`Dagon: The Promised One` old /
        `Dagon: Promised` db-new, both -> 达冈：应许者).
    Plus a strip check on the override tables.
    """
    results = []
    ov = ref_dir / "card_overrides.md"
    if not ov.exists():
        # required_refs already FAILs a missing file; avoid double-counting.
        return results
    text = ov.read_text(encoding="utf-8")

    # 1. Stale Unseen Elder -> Overwhelming Hunger alias must be gone.
    #    Only TABLE rows count (the explanatory note legitimately mentions both).
    stale = [
        l for l in text.split("\n")
        if l.strip().startswith("|")
        and "Unseen Elder" in l and "Overwhelming Hunger" in l
    ]
    if stale:
        results.append((
            "FAIL",
            "card_overrides.md: 过期别名 Unseen Elder→Overwhelming Hunger 仍在 "
            "（会把暗影长者误导向无尽渴望）",
        ))
    else:
        results.append((
            "PASS",
            "card_overrides.md: 无 Unseen Elder→Overwhelming Hunger 过期别名",
        ))

    # 2. Dagon bidirectional EN aliases present.
    has_old = "Dagon: The Promised One" in text
    has_new = "Dagon: Promised" in text
    if has_old and has_new:
        results.append((
            "PASS",
            "card_overrides.md: Dagon 双向 EN alias 在（The Promised One / Promised）",
        ))
    else:
        missing = [
            n for n, ok in [("Dagon: The Promised One", has_old), ("Dagon: Promised", has_new)]
            if not ok
        ]
        results.append(("WARN", f"card_overrides.md: Dagon alias 缺 {missing}"))

    # 3. Strip check: flag only NON-standard whitespace in cells (tabs, double
    #    spaces, missing pad) — a normally padded `| value |` cell is clean.
    dirty = 0
    for line in text.split("\n"):
        s = line.strip()
        if not s.startswith("|") or "---" in s:
            continue
        cells = s.split("|")
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        for c in cells:
            v = c.strip()
            if v and c != " " + v + " ":
                dirty += 1
    if dirty:
        results.append(("WARN", f"card_overrides.md: {dirty} 个单元格空白异常（含制表符/双空格/缺填充）"))
    else:
        results.append(("PASS", "card_overrides.md: 表格单元格空白正常"))

    return results


def check_reference_data_hygiene(ref_dir: Path) -> list[tuple[str, str]]:
    """Detect structural corruption in table-based reference files.

    Catches: column-count drift within a table, hidden control/zero-width
    characters sneaking in via copy-paste.

    Cannot catch: semantic errors (a well-formed but wrong CN gloss like the
    historical '店店士兵帝'). Those need human review — this check guards
    against format-level corruption only, not a substitute for review.
    """
    results = []
    # EN<->CN 翻译映射核心表(deck名/卡名/术语/关键词/类别/属性/黑话/歧义)，
    # 会进 TermAuthority 强制层、格式脏了直接影响翻译，故只扫这批；
    # 叙事/风格类(common_pitfalls/style_reference 等)不进强制层，不扫。
    targets = [
        "competitive_terms.md", "card_overrides.md", "terminology_map.md",
        "reverse_terminology_map.md", "keywords_map.md", "category_map.md",
        "card_attributes_map.md", "slang_map.md", "ambiguous_names.md",
    ]
    _DIRTY_CHARS = re.compile('[\u0000-\u0008\u000b\u000c\u000e-\u001f\u00a0\u00ad\u200b-\u200f\u2028\u2029\u2060\ufeff]')
    checked = 0
    total_issues = 0
    for fname in targets:
        path = ref_dir / fname
        if not path.exists():
            continue
        checked += 1
        lines = path.read_text(encoding="utf-8").split("\n")
        header_cols: int | None = None
        bad: list[str] = []
        for i, line in enumerate(lines, start=1):
            if "|" not in line or not line.strip().startswith("|"):
                header_cols = None  # non-table line ⇒ previous table ended
                continue
            non_sep = line.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")
            if not non_sep.strip():
                header_cols = None
                continue
            # 脏字符检查对所有表格行生效(含表头)，须在 header_cols 早返回之前，
            # 否则分隔行重置后首个数据行被当表头而漏检(审查 Important 修复)
            if _DIRTY_CHARS.search(line):
                bad.append(f"L{i}含隐藏控制/零宽字符")
            cols = line.count("|")
            if header_cols is None:
                header_cols = cols
                continue
            if cols != header_cols:
                bad.append(f"L{i}列数{cols}≠表头{header_cols}")
        if bad:
            total_issues += len(bad)
            preview = "; ".join(bad[:3]) + ("..." if len(bad) > 3 else "")
            results.append(("WARN", f"{fname}: {len(bad)} 处结构异常 — {preview}"))
    if total_issues == 0:
        results.append((
            "PASS",
            f"reference 数据卫生: {checked} 个表格文件结构正常(列数一致/无隐藏字符)",
        ))
    results.append((
        "INFO",
        "reference 数据卫生: 仅检测结构脏数据，译法语义错需人工核查(此检查识别不了)",
    ))
    return results


def run_test_cases(script_dir: Path) -> list[tuple[str, str]]:
    """Run basic test cases on scripts."""
    results = []

    # H1 回归守护：表格空单元格必须保留（剥首尾空元素），旧的 [c for c in cells if c]
    # 会删掉合法空单元格导致列错位 / restore 结构损坏。
    fmt_path = script_dir / "format_skeleton.py"
    if fmt_path.exists():
        try:
            import importlib.util
            _spec = importlib.util.spec_from_file_location("_fmt_h1", fmt_path)
            _mod = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_mod)
            _skel = _mod.extract_skeleton("| 1 |  | 3 |\n|---|---|---|\n| a | b | c |\n")
            _tables = [b for b in _skel.get("blocks", []) if b.get("type") == "table"]
            _row0 = _tables[0]["rows"][0] if _tables and _tables[0]["rows"] else []
            if len(_row0) == 3 and _row0[1] == "":
                results.append(("PASS", "format_skeleton: 空单元格保留（表格列不错位）"))
            else:
                results.append(("FAIL", f"H1 回归: 空单元格丢失，rows[0]={_row0}"))
        except Exception as e:  # noqa: BLE001
            results.append(("WARN", f"format_skeleton H1 测试失败 ({e})"))

    # Test check_translation.py with sample text
    check_script = script_dir / "check_translation.py"
    if check_script.exists():
        try:
            # Create test file
            test_content = "这张卡要12费用，出场率很高。"
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", encoding="utf-8", delete=False
            ) as tf:
                tf.write(test_content)
                test_file = Path(tf.name)
            try:
                result = run_utf8(
                    [sys.executable, str(check_script), str(test_file),
                     "--direction", "encn", "--json"],
                    timeout=10,
                )
                # Assert on the JSON envelope (exit code + parsed issue list),
                # not on human-readable wording like "forbidden term".
                try:
                    import json
                    data = json.loads(result.stdout)["data"]
                    issues = data["issues"]
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    issues = None
                if issues and result.returncode == 1:
                    results.append(("PASS", "check_translation.py: Detects errors correctly"))
                else:
                    results.append(("WARN", "check_translation.py: Unexpected test result"))
            finally:
                test_file.unlink(missing_ok=True)
        except Exception as e:
            results.append(("WARN", f"check_translation.py: Test failed ({e})"))

    # Test learn.py with sample text
    learn_script = script_dir / "learn.py"
    if learn_script.exists():
        try:
            # Syntax check via ast.parse (no execution, avoids side effects)
            ast.parse(learn_script.read_text(encoding="utf-8"))
            results.append(("PASS", "learn.py: Syntax OK"))
        except SyntaxError as e:
            results.append(("FAIL", f"learn.py: Syntax error ({e})"))
        except Exception as e:
            results.append(("WARN", f"learn.py: Test failed ({e})"))

    # Test English residue detection
    check_script = script_dir / "check_translation.py"
    if check_script.exists():
        try:
            test_content = "这张卡很强。Geralt 和 Ciri 都可以带。"
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", encoding="utf-8", delete=False
            ) as tf:
                tf.write(test_content)
                test_file = Path(tf.name)
            try:
                result = run_utf8(
                    [sys.executable, str(check_script), str(test_file), "--direction", "encn"],
                    timeout=10,
                )
                if "English residue" in result.stdout:
                    results.append(("PASS", "check_translation.py: English residue detection works"))
                else:
                    results.append(("WARN", "check_translation.py: English residue not detected in test"))
            finally:
                test_file.unlink(missing_ok=True)
        except Exception as e:
            results.append(("WARN", f"check_translation.py: Residue test failed ({e})"))

    # Test completeness_guard term_authority actually enforces CN->EN
    # (was a hard not_applicable skip; now runs term_enforcer on the English
    # output and blocks when a locked official English term is missing).
    guard_script = script_dir / "completeness_guard.py"
    if guard_script.exists():
        src_file = None
        test_file = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", encoding="utf-8", delete=False) as sf:
                sf.write("这是一篇讨论希里与烧灼强度的中文源文，关于天梯环境。\n")
                src_file = Path(sf.name)
            # English output that DROPS the locked official card names entirely.
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as tf:
                tf.write("This English output intentionally omits the locked card name.\n")
                test_file = Path(tf.name)
            result = run_utf8(
                [sys.executable, str(guard_script), str(test_file),
                 "--source", str(src_file), "--direction", "cnen", "--json"],
                timeout=30,
            )
            if ('"status": "ran"' in result.stdout
                    and '"blocked": true' in result.stdout
                    and '"name": "term_authority"' in result.stdout):
                results.append(("PASS", "completeness_guard.py: term_authority enforces CN->EN (status=ran, blocks missing EN)"))
            else:
                results.append(("WARN", "completeness_guard.py: CN->EN term_authority enforcement not active"))
        except Exception as e:
            results.append(("WARN", f"completeness_guard.py: Test failed ({e})"))
        finally:
            if src_file:
                src_file.unlink(missing_ok=True)
            if test_file:
                test_file.unlink(missing_ok=True)

    # Test slang reverse-scan warn (literal translation of source slang warns, non-blocking)
    check_script = script_dir / "check_translation.py"
    if check_script.exists():
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", encoding="utf-8", delete=False) as sf:
                sf.write("This card is broken.")
                src_file = Path(sf.name)
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as tf:
                tf.write("这张卡破碎了。")
                tr_file = Path(tf.name)
            try:
                result = run_utf8(
                    [sys.executable, str(check_script), str(tr_file),
                     "--source", str(src_file), "--direction", "encn"],
                    timeout=15,
                )
                # literal "破碎了" for "broken" should warn (non-blocking, exit 0)
                if "slang not preserved" in result.stdout and result.returncode == 0:
                    results.append(("PASS", "check_translation.py: slang reverse-scan warns (non-blocking)"))
                else:
                    results.append(("WARN", "check_translation.py: slang warn test unexpected"))
            finally:
                src_file.unlink(missing_ok=True)
                tr_file.unlink(missing_ok=True)
        except Exception as e:
            results.append(("WARN", f"check_translation.py: slang test failed ({e})"))

    return results


# 方向是必填的任务参数：任何环节都不得从文本推断它。这两个名字是当初把
# 「夹满英文卡名的中文源文」误判成英文的推断（prepare 做出 EN->CN 的 pack，门禁
# 把译文往中文推）；已物理删除，重新引入必须报错。
_DIRECTION_INFERENCE_NAMES = ("detect_direction", "source_is_chinese")
# 这两个文件会提到上述名字：本检查自己，以及断言它们不存在的回归用例。
_DIRECTION_SCAN_SKIP = {"health_check.py", "test_rebuild.py"}

# 展示命令用法的文档与清单。原始 bug 的直接诱因就是文档示例没带 --direction，
# 所以每一处写出来的命令调用都要查。
_DIRECTION_DOC_FILES = (
    "SKILL.md", "lite/SKILL.md", "lite/AGENTS.md", "AGENTS.md",
    "references/translation_workflow.md", "agent.json",
)
# 需要方向的脚本。context_lock 只有 add 子命令不需要。前面的 lookbehind 把
# backtranslate.py 这类恰好以同名结尾的脚本排除在外。
_DIRECTION_SCRIPTS = (
    "translate", "auto_pipeline", "context_lock", "term_enforcer", "check_translation",
    "phase_c_check", "completeness_guard", "diff_review",
)
_SCRIPT_NAME = rf"(?<![A-Za-z_])(?:{'|'.join(_DIRECTION_SCRIPTS)})\.py"
# 解释器的常见写法：python / python3 / python3.12 / py / python.exe，以及放在变量里的
# （"$PY"、${PYTHON}、$PYTHON）。前面不能紧挨着字母数字，免得 copy 之类单词的尾巴命中。
_INTERPRETER = (
    r"(?<![A-Za-z0-9_.$-])(?:"
    r"python[0-9.]*|py|python\.exe"
    r"|\"\$\{?[A-Za-z_]+\}?\"|\$\{[A-Za-z_]+\}|\$[A-Za-z_]+"
    r")"
)
# 一条命令的开头：可选的 `$` / `>` 提示符，可选的解释器（可带解释器参数，如
# python3 -B），可选的 `./`，然后是脚本路径。
_COMMAND_HEAD = (
    rf"(?:[$>]\s*)?(?:{_INTERPRETER}(?:\s+-\S+)*\s+)?(?:\./)?\S*?{_SCRIPT_NAME}[\"']?(?=\s)"
)
# 带参数只能出现在行首（行首空白之后，可带提示符）；代码块里的行本来就是命令，可以出现在
# 行内任何位置。
_COMMAND_AT_START = re.compile(rf"^\s*{_COMMAND_HEAD}")
_COMMAND_ANYWHERE = re.compile(_COMMAND_HEAD)
# 按模块方式运行：python3 -m scripts.translate prepare …
_MODULE_FORM = re.compile(r"-m\s+scripts\.translate(?!\.py)")
# 第一个参数是子命令的脚本：只写到子命令的引用（`translate.py finish`）没写出参数，
# 无从判断，不算命令。
_SUBCOMMAND_SCRIPTS = ("translate.py", "auto_pipeline.py", "context_lock.py")
# JSON 输出里已删除的字段。
_REMOVED_DIRECTION_FIELDS = ("direction_auto_detected", "direction_warning")


def _read_doc(path: Path) -> str | None:
    """Read a doc as UTF-8; None when it cannot be read (the caller reports it)."""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _first_outside_quotes(text: str, is_stop) -> int:
    """Index of the first character of `text` outside quotes with `is_stop(index, char)`, else -1.

    A quote character only opens a quoted stretch when the same character closes
    it later in the text: an apostrophe inside a name (O'Brien.md) is not a quote.
    """
    quote = ""
    for i, ch in enumerate(text):
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'`" and text.find(ch, i + 1) != -1:
            quote = ch
        elif is_stop(i, ch):
            return i
    return -1


def _strip_line_comment(segment: str) -> str:
    """Drop a trailing `# comment` that starts outside quotes."""
    i = _first_outside_quotes(
        segment, lambda i, ch: ch == "#" and i > 0 and segment[i - 1].isspace())
    return segment if i < 0 else segment[:i]


def _takes_direction(invocation: str) -> bool:
    if re.search(_SCRIPT_NAME, invocation).group(0) != "context_lock.py":
        return True
    return re.search(r"context_lock\.py[\"']?\s+add(\s|$)", invocation) is None


def _argument_span(invocation: str) -> str:
    """The invocation up to its first unquoted comma that ends the text or is followed by whitespace.

    What follows such a comma is prose or another command ("… prepare source.md,
    then finish with the same --direction") and must not vouch for this one. A
    comma inside an argument (2026-05,2026-06) leaves the command alone.
    """
    def prose_comma(i: int, ch: str) -> bool:
        return ch == "," and (i + 1 == len(invocation) or invocation[i + 1].isspace())

    i = _first_outside_quotes(invocation, prose_comma)
    return invocation if i < 0 else invocation[:i]


def _command_text(text: str) -> str:
    """`text` as the shell reads it: trailing comment dropped, module form as a path."""
    return _MODULE_FORM.sub("scripts/translate.py", _strip_line_comment(text))


def _judge_command_line(line: str, anywhere: bool = False) -> tuple[list[str], int]:
    """Judge the commands written on one line.

    Returns (violations, commands examined). Commands joined by && / || / ; / |
    are judged one by one, and a trailing `# comment` is removed first, so the
    flag must follow the invocation inside its own command segment and before
    its first prose comma. By default a command has to start the segment (after
    an optional prompt). With `anywhere` it may sit anywhere in the segment, as
    on the lines of a code block. A comment line counts only when it is itself
    a commented-out command — a command starts it once the marker is gone — and
    is then judged like any command line; a comment that merely talks about a
    command ("# this replaces the old python … call", "# step 1; python …") is
    prose. A trailing comment runs to the end of the line, separators included.
    """
    missing: list[str] = []
    examined = 0
    pattern = _COMMAND_ANYWHERE if anywhere else _COMMAND_AT_START
    uncommented = re.sub(r"^\s*#+\s?", "", line, count=1)
    if uncommented != line:
        if _COMMAND_AT_START.search(_command_text(uncommented)) is None:
            return missing, examined
        line, pattern = uncommented, _COMMAND_AT_START
    for segment in re.split(r"&&|\|\||[;|]", _command_text(line)):
        m = pattern.search(segment)
        if not m:
            continue
        invocation = _argument_span(segment[m.start():])
        found = re.search(_SCRIPT_NAME, invocation)
        if found is None:
            # A comma before the script name cut the invocation short.
            continue
        script = found.group(0)
        args = invocation[found.end():].strip("\"' ").split()
        # A reference that names only the script and options (`check_translation.py --fix`) is not a command.
        if not any(not arg.startswith("-") for arg in args):
            continue
        if len(args) < (2 if script in _SUBCOMMAND_SCRIPTS else 1):
            continue
        examined += 1
        if _takes_direction(invocation) and "--direction" not in invocation:
            missing.append(invocation.strip()[:70])
    return missing, examined


def _commands_lacking_direction(text: str) -> tuple[list[str], int]:
    """Judge the commands written in a document.

    Returns (violations, commands examined). Commands are judged where commands
    are written — fenced and indented code blocks and backtick spans. Prose is
    never judged: "Before this fix, python … prepare source.md guessed the
    direction" explains a command and must not read as one.
    """
    missing: list[str] = []
    examined = 0
    # The open fence, as (character, length); a fence is closed only by a line
    # of the same character, at least as long, and nothing else on it.
    fence: tuple[str, int] | None = None
    # 续行（行尾反斜杠）是同一条命令：先并回一行；引用块标记（行首的 `>`）不属于
    # 内容，先去掉，引用块里的代码块（SKILL.md 的命令示例就是这么写的）才认得出来
    for line in re.sub(r"^(?:\s*>)+\s?", "", text.replace("\\\n", " "), flags=re.M).split("\n"):
        stripped = line.lstrip()
        marker = re.match(r"([`~])\1{2,}", stripped)
        if fence is None:
            # An opening fence; the info string of a backtick fence holds no backtick.
            if marker and not (marker.group(1) == "`" and "`" in stripped[marker.end():]):
                fence = (marker.group(1), len(marker.group(0)))
                continue
        elif (marker and marker.group(1) == fence[0] and len(marker.group(0)) >= fence[1]
              and not stripped[marker.end():].strip()):
            fence = None
            continue
        if fence is not None:
            found, count = _judge_command_line(line, anywhere=True)
        elif line.startswith("    ") or line.startswith("\t"):
            found, count = _judge_command_line(line)
        else:
            found, count = [], 0
            for span in re.findall(r"`([^`\n]+)`", line):
                more, n = _judge_command_line(span, anywhere=True)
                found += more
                count += n
        missing += found
        examined += count
    return missing, examined


def _manifest_commands(node) -> tuple[list[str], int]:
    """Judge the commands stored as strings in a parsed agent.json."""
    missing: list[str] = []
    examined = 0
    items = node.values() if isinstance(node, dict) else node if isinstance(node, list) else ()
    for value in items:
        if isinstance(value, str):
            found, count = _judge_command_line(value)
            missing += found
            examined += count
        elif isinstance(value, (dict, list)):
            found, count = _manifest_commands(value)
            missing += found
            examined += count
    return missing, examined


def _duplicate_manifest_fields(base_dir: Path) -> tuple[list[str], str | None]:
    """Duplicate entries in agent.json's per-command `args` / `json_output` lists.

    Returns (duplicates, error). `error` is set when the manifest cannot be
    read, parsed or walked — a `commands` that is not a list of objects, an
    `args` / `json_output` that is present but null or not a list, an entry
    without a name — in which case `duplicates` is empty. A field a command
    simply does not have (the `run` wrapper declares no `json_output`) is fine.
    """
    text = _read_doc(base_dir / "agent.json")
    if text is None:
        return [], "unreadable"
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as e:
        return [], f"not valid JSON ({e})"
    commands = manifest.get("commands") if isinstance(manifest, dict) else None
    if not isinstance(commands, list) or not all(isinstance(c, dict) for c in commands):
        return [], '"commands" is not a list of objects'
    duplicates = []
    for command in commands:
        label = command.get("name", "?")
        for field in ("args", "json_output"):
            if field not in command:
                continue
            items = command[field]
            if not isinstance(items, list):
                return [], f"{label}.{field} is not a list"
            names = []
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    names.append(item["name"])
                elif isinstance(item, str):
                    names.append(item)
                else:
                    return [], f"{label}.{field} has an entry without a name"
            repeated = sorted({name for name in names if names.count(name) > 1})
            duplicates += [f"{label}.{field}: {name}" for name in repeated]
    return duplicates, None


def check_direction_contract(script_dir: Path) -> list[tuple[str, str]]:
    """方向是必填的任务参数：--direction 一律 required，且无按文本推断方向的代码。"""
    results = []
    optional: list[str] = []
    inferred: list[str] = []
    unreadable: list[str] = []
    direction_args = 0
    for path in sorted(script_dir.glob("*.py")):
        if path.name in _DIRECTION_SCAN_SKIP:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # check_scripts already reports the syntax error
            continue
        except (OSError, UnicodeDecodeError) as e:
            unreadable.append(f"{path.name} ({e})")
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "add_argument" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "--direction"):
                direction_args += 1
                if not any(keyword.arg == "required"
                           and isinstance(keyword.value, ast.Constant)
                           and keyword.value.value is True
                           for keyword in node.keywords):
                    optional.append(f"{path.name}:{node.lineno}")
            if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name in _DIRECTION_INFERENCE_NAMES):
                inferred.append(f"{path.name}:{node.lineno} def {node.name}")
            elif isinstance(node, ast.Name) and node.id in _DIRECTION_INFERENCE_NAMES:
                inferred.append(f"{path.name}:{node.lineno} {node.id}")
            elif isinstance(node, ast.alias) and node.name in _DIRECTION_INFERENCE_NAMES:
                inferred.append(f"{path.name}:{node.lineno} import {node.name}")
    if optional:
        results.append(("FAIL", f"方向回归: --direction 不是必填: {', '.join(optional)}"))
    elif direction_args == 0:
        results.append(("FAIL", "方向回归: 没有找到任何 --direction 参数，检查与脚本已脱节"))
    else:
        results.append(("PASS", f"所有 --direction 参数均为必填 ({direction_args} 处)"))
    if inferred:
        results.append(("FAIL", f"方向回归: 按文本推断方向的代码被重新引入: {inferred}"))
    else:
        results.append(("PASS", "无按文本推断方向的代码 (detect_direction / source_is_chinese 已移除)"))
    if unreadable:
        results.append(("WARN", f"无法读取脚本，方向契约未完整检查: {unreadable}"))
    return results


def check_direction_docs(base_dir: Path) -> list[tuple[str, str]]:
    """文档与 agent.json 同步方向契约：无已删字段、无重复项，写出的命令调用一律带 --direction。"""
    results = []
    docs: dict[str, str] = {}
    unreadable: list[str] = []
    paths = [base_dir / name for name in _DIRECTION_DOC_FILES]
    paths += sorted(base_dir.glob("README*.md"))
    for path in paths:
        if not path.exists():
            continue
        text = _read_doc(path)
        if text is None:
            unreadable.append(str(path.relative_to(base_dir)))
        else:
            docs[str(path.relative_to(base_dir))] = text

    stale = [f"{name}: {field}" for name, text in docs.items()
             for field in _REMOVED_DIRECTION_FIELDS if field in text]
    if stale:
        results.append(("FAIL", f"文档残留已删字段: {stale}"))
    else:
        results.append(("PASS", "文档无已删字段残留 (direction_auto_detected / direction_warning)"))

    duplicates, manifest_error = _duplicate_manifest_fields(base_dir)
    if manifest_error:
        results.append(("FAIL", f"agent.json 清单无法检查: {manifest_error}"))
    elif duplicates:
        results.append(("FAIL", f"agent.json 清单有重复项: {duplicates}"))
    else:
        results.append(("PASS", "agent.json 各命令的 args / json_output 无重复项"))

    missing: list[str] = []
    examined = 0
    for name, text in docs.items():
        if name == "agent.json":
            continue  # its commands are judged from the parsed manifest below
        found, count = _commands_lacking_direction(text)
        missing += [f"{name}: {invocation}" for invocation in found]
        examined += count
    # agent.json is a manifest, not prose: every string value in it is a
    # command or a description, so each string is judged on its own.
    if "agent.json" in docs and manifest_error is None:
        found, count = _manifest_commands(json.loads(docs["agent.json"]))
        missing += [f"agent.json: {invocation}" for invocation in found]
        examined += count
    if missing:
        results.append(("FAIL", f"文档里的命令调用缺 --direction: {missing}"))
    elif examined == 0:
        results.append(("FAIL", "没有在文档里找到任何需要方向的命令调用，检查与文档已脱节"))
    else:
        results.append(("PASS", f"文档里的命令调用均带 --direction (检查 {len(docs)} 个文件，"
                                f"{examined} 条命令)"))
    if unreadable:
        results.append(("WARN", f"无法读取文档，命令示例未完整检查: {unreadable}"))
    return results


def _run_rebuild_behavior_tests() -> list[tuple[str, str]]:
    """Run the committed synthetic rebuild-behavior suite (scripts/test_rebuild.py).

    Returns the suite's (status, message) list; any import/runtime failure degrades
    to a single WARN so a broken test module never silently masks a real PASS."""
    try:
        import test_rebuild
        return test_rebuild.run()
    except Exception as e:  # noqa: BLE001
        return [("WARN", f"test_rebuild.py: failed to run ({type(e).__name__}: {e})")]


def _section_results(name: str, func) -> list[tuple[str, str]]:
    """One section's results. A check that raises is a failed check, not a dead health check."""
    try:
        return func()
    except Exception as e:  # noqa: BLE001 - reported as the FAIL below, with its traceback on stderr
        if sys.stderr is not None:  # closed (`2>&-`): a print would fall back to stdout
            traceback.print_exc()
        return [("FAIL", f"{name}: 检查自身抛出异常 {type(e).__name__}: {e}")]


def main():
    parser = argparse.ArgumentParser(description="Gwent Translation Skill Health Check")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    parser.add_argument("--json", action="store_true", help="Output structured JSON for agent consumption")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color codes in output")
    args = parser.parse_args()

    global _no_color
    _no_color = args.no_color or os.environ.get("NO_COLOR", "").strip() != ""

    base_dir = Path(__file__).parent.parent
    ref_dir = base_dir / "references"
    script_dir = base_dir / "scripts"
    skill_file = base_dir / "SKILL.md"

    all_results = []

    def run_section(name: str, func) -> list[tuple[str, str]]:
        results = _section_results(name, func)
        all_results.extend(results)
        return results

    ref_results = run_section("Reference Files", lambda: check_reference_files(ref_dir))
    script_results = run_section("Scripts", lambda: check_scripts(script_dir))
    skill_results = run_section("SKILL.md Structure", lambda: check_skill_file(skill_file))
    data_results = run_section("Data Integrity", lambda: check_data_integrity(ref_dir))
    phase_c_results = run_section("Phase C Checklist", lambda: check_phase_c_checklist(ref_dir))
    authority_results = run_section("TermAuthority Invariants", lambda: check_term_authority_invariants(script_dir))
    ambiguous_results = run_section("Ambiguous Names", lambda: check_ambiguous_names(ref_dir))
    effect_results = run_section("Effect Text", lambda: check_effect_text(ref_dir))
    card_ov_results = run_section("Card Overrides", lambda: check_card_overrides_quality(ref_dir))
    hygiene_results = run_section("Reference Data Hygiene", lambda: check_reference_data_hygiene(ref_dir))
    test_results = run_section("Functional Tests", lambda: run_test_cases(script_dir))
    direction_results = run_section("Direction Contract", lambda: check_direction_contract(script_dir))
    direction_doc_results = run_section("Direction Docs", lambda: check_direction_docs(base_dir))
    rebuild_results = run_section("Rebuild Behavior Tests", lambda: _run_rebuild_behavior_tests())

    pass_count = sum(1 for s, _ in all_results if s == "PASS")
    fail_count = sum(1 for s, _ in all_results if s == "FAIL")
    warn_count = sum(1 for s, _ in all_results if s == "WARN")
    info_count = sum(1 for s, _ in all_results if s == "INFO")

    if args.json:
        data = {
            "pass_count": pass_count,
            "fail_count": fail_count,
            "warn_count": warn_count,
            "info_count": info_count,
            "results": [
                {"status": status, "message": msg}
                for status, msg in all_results
            ],
        }
        json_output(data, exit_code=1 if fail_count > 0 else 0)

    print(f"Gwent Translation Skill Health Check")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Base dir: {base_dir}")
    print()

    sections = [
        ("Reference Files", ref_results),
        ("Scripts", script_results),
        ("SKILL.md Structure", skill_results),
        ("Data Integrity", data_results),
        ("Phase C Checklist", phase_c_results),
        ("TermAuthority Invariants", authority_results),
        ("Ambiguous Names", ambiguous_results),
        ("Effect Text", effect_results),
        ("Card Overrides", card_ov_results),
        ("Reference Data Hygiene", hygiene_results),
        ("Functional Tests", test_results),
        ("Direction Contract", direction_results),
        ("Direction Docs", direction_doc_results),
        ("Rebuild Behavior Tests", rebuild_results),
    ]

    for name, results in sections:
        print("=" * 50)
        print(name)
        print("=" * 50)
        for status, msg in results:
            print(f"  [{color(status)}{status}{color('RESET')}] {msg}")
        print()

    # Summary
    print("=" * 50)
    print("Summary")
    print("=" * 50)
    print(f"  PASS: {pass_count}")
    if fail_count:
        print(f"  {color('FAIL')}FAIL{color('RESET')}: {fail_count}")
    if warn_count:
        print(f"  {color('WARN')}WARN{color('RESET')}: {warn_count}")
    if info_count:
        print(f"  INFO: {info_count}")
    print()

    if fail_count == 0:
        print(f"  {color('PASS')}All checks passed!{color('RESET')}")
    else:
        print(f"  {color('FAIL')}{fail_count} critical issue(s) found{color('RESET')}")

    sys.exit(1 if fail_count > 0 else 0)


if __name__ == "__main__":
    main()
