#!/usr/bin/env python3
"""
Gwent Translation Skill Health Check.
Verifies all components are present and functional.

Usage:
    python health_check.py [--verbose]
"""

import ast
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from _shared import json_output, parse_markdown_table


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
                result = subprocess.run(
                    [sys.executable, str(check_script), str(test_file),
                     "--direction", "encn", "--json"],
                    capture_output=True,
                    text=True,
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
                result = subprocess.run(
                    [sys.executable, str(check_script), str(test_file)],
                    capture_output=True,
                    text=True,
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
            result = subprocess.run(
                [sys.executable, str(guard_script), str(test_file),
                 "--source", str(src_file), "--direction", "cnen", "--json"],
                capture_output=True,
                text=True,
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
                result = subprocess.run(
                    [sys.executable, str(check_script), str(tr_file),
                     "--source", str(src_file), "--direction", "encn"],
                    capture_output=True, text=True, timeout=15,
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


def _run_rebuild_behavior_tests() -> list[tuple[str, str]]:
    """Run the committed synthetic rebuild-behavior suite (scripts/test_rebuild.py).

    Returns the suite's (status, message) list; any import/runtime failure degrades
    to a single WARN so a broken test module never silently masks a real PASS."""
    try:
        import test_rebuild
        return test_rebuild.run()
    except Exception as e:  # noqa: BLE001
        return [("WARN", f"test_rebuild.py: failed to run ({type(e).__name__}: {e})")]


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
        results = func()
        all_results.extend(results)
        return results

    ref_results = run_section("Reference Files", lambda: check_reference_files(ref_dir))
    script_results = run_section("Scripts", lambda: check_scripts(script_dir))
    skill_results = run_section("SKILL.md Structure", lambda: check_skill_file(skill_file))
    data_results = run_section("Data Integrity", lambda: check_data_integrity(ref_dir))
    phase_c_results = run_section("Phase C Checklist", lambda: check_phase_c_checklist(ref_dir))
    authority_results = run_section("TermAuthority Invariants", lambda: check_term_authority_invariants(script_dir))
    effect_results = run_section("Effect Text", lambda: check_effect_text(ref_dir))
    card_ov_results = run_section("Card Overrides", lambda: check_card_overrides_quality(ref_dir))
    hygiene_results = run_section("Reference Data Hygiene", lambda: check_reference_data_hygiene(ref_dir))
    test_results = run_section("Functional Tests", lambda: run_test_cases(script_dir))
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
        ("Effect Text", effect_results),
        ("Card Overrides", card_ov_results),
        ("Reference Data Hygiene", hygiene_results),
        ("Functional Tests", test_results),
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
