#!/usr/bin/env python3
"""Build references/card_names_4lang.json — card names in 4 languages.

card_names_4lang.json is a BUILD-TIME artifact and is NOT committed to the repo.
Like effect_text.json, it holds card names derived from the gwent.one card data
(see NOTICE). The repo ships the build tool only; the data is read from a local
gwent-card-db mirror (default) or fetched from the public api.gwent.one with
``--fetch`` at install/build time.

This is the foundation table for the skill rebuild: every later extraction /
cross-check query reads this 4-language name table. It is name-only (no ability
text), keyed by ``card_id`` so a card can be looked up in all four languages at
once.

Two modes (mirrors build_effect_reference.py; mode reuse, not code copy):

  1. Offline / fast (DEFAULT if a local card-db mirror exists):
        python3 scripts/build_card_names_reference.py
        python3 scripts/build_card_names_reference.py --src /path/to/gwent-card-db
        GWENT_CARD_DB=/path python3 scripts/build_card_names_reference.py
     Reads tables/cards_{en,cn,ru,pl}.json, joins by card_id, writes
     card_names_4lang.json atomically.

  2. Online (fallback for fresh installs / GitHub clones):
        python3 scripts/build_card_names_reference.py --fetch
        python3 scripts/build_card_names_reference.py --fetch --version latest
     Pulls en/cn/ru/pl single-language endpoints from api.gwent.one (slow,
     ~3 min total, CN-reachable), joins by card_id, writes card_names_4lang.json.

Output schema (identical for both modes, keyed by card_id):

    { "<card_id>": {
        "card_id": 112101,
        "en": "Ciri",
        "cn": "希里",
        "ru": "Цири",
        "pl": "Ciri"
    } }
"""

import argparse
import json
import os
import socket
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_SRC = Path(os.path.expanduser("~/gwent-card-db"))
OUT = Path(__file__).resolve().parent.parent / "references" / "card_names_4lang.json"

# The four languages this table carries. EN is the join driver / source of truth
# for the card_id set; the others are looked up by card_id.
LANGS = ("en", "cn", "ru", "pl")

# api.gwent.one online fetch config (mirrors build_effect_reference.py).
API_BASE = "https://api.gwent.one/"
API_VERSION = "14.6.0"  # pinned; --version latest overrides (schema may drift)
LANG_FETCH_TIMEOUT = 120  # per-language socket-level timeout (per connect/recv op)
MIN_HEALTHY_CARDS = 1000  # truncation guard: a too-small payload hard-fails
USER_AGENT = "gwent-translation-skill/build_card_names_reference"


def _report_counts(out: dict, skipped: int, source: str) -> None:
    """Print the standard build summary (shared by online + offline modes)."""
    print(f"写出 {len(out)} 张卡 × {len(LANGS)} 语种（{skipped} 跳过）"
          f" [{source}] -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    # Names are stripped by the builders; re-assert none slipped through so a
    # regression in the strip logic surfaces immediately rather than silently
    # leaking trailing whitespace into the downstream lookup keys.
    dirty = [
        v["card_id"] for v in out.values()
        if any(v[lang] != v[lang].strip() for lang in LANGS)
    ]
    if dirty:
        print(f"[WARN] {len(dirty)} 张卡 name 仍有首尾空白（应为已 strip）:"
              f" {dirty[:5]}{'...' if len(dirty) > 5 else ''}")


def _write_out(out: dict) -> None:
    """Atomically write card_names_4lang.json (tempfile + os.replace) so a
    crashed half-write can never leave a corrupt file that a downstream loader
    would otherwise parse and silently disable 4-lang lookups across the
    pipeline."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(OUT.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        os.replace(tmp, OUT)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _require_all_cards(out: dict, check: bool = False) -> None:
    """Hard-fail on a suspiciously small output.

    The card data has 1381 cards and is 100% complete in every language. A
    truncated payload or a half-read mirror would silently shrink the table and
    make later extraction/cross-check queries silently miss cards — exactly the
    'empty table -> silent-pass' failure mode the brief warns against. Fail loud
    instead of shipping a partial table."""
    if len(out) < MIN_HEALTHY_CARDS:
        print(f"错误：输出仅 {len(out)} 张卡（预期 {MIN_HEALTHY_CARDS}+），"
              f"疑似数据截断，拒绝写出残表。", file=sys.stderr)
        sys.exit(3 if check else 1)


def build(src_dir: Path, check: bool = False) -> dict:
    """Offline build from a local gwent-card-db mirror
    (tables/cards_{en,cn,ru,pl}.json).

    The offline tables are download.py's flattened output, so card_id and name
    are already top-level fields (unlike the raw online response, which nests the
    id under card['id']['card']).
    """
    tables = src_dir / "tables"
    paths = {lang: tables / f"cards_{lang}.json" for lang in LANGS}
    missing = [p for p in paths.values() if not p.exists()]
    if missing:
        print(f"错误：找不到 card-db 数据（{[str(p) for p in missing]}）",
              file=sys.stderr)
        print("       用 --src 指向 card-db 根目录，或设 GWENT_CARD_DB 环境变量。",
              file=sys.stderr)
        print("       或用 --fetch 在线从 api.gwent.one 拉取（约 3 分钟，国内可达）。",
              file=sys.stderr)
        # check 模式下构建失败 exit 3（与 0/1/2 区分，见 main 的 except 块）。
        sys.exit(3 if check else 1)

    # Load every language keyed by card_id once. Names are stripped here so the
    # join below never re-introduces whitespace.
    by_lang: dict[str, dict[int, str]] = {}
    for lang in LANGS:
        cards = json.loads(paths[lang].read_text(encoding="utf-8"))
        by_lang[lang] = {
            c["card_id"]: (c.get("name") or "").strip() for c in cards
        }

    # EN drives the card_id set (source of truth). The data is verified to have
    # an identical card_id set across all four languages, but the join is
    # defensive: a card missing a name in another language is counted + reported
    # rather than silently dropped.
    out: dict[str, dict] = {}
    skipped = 0
    for card_id, en_name in by_lang["en"].items():
        names = {lang: by_lang[lang].get(card_id, "") for lang in LANGS}
        if not en_name or not all(names.values()):
            # Empty EN name or a name missing in any language = data anomaly;
            # the brief guarantees 100% completeness, so any non-zero skip count
            # is loud in the report and worth investigating.
            skipped += 1
            continue
        out[str(card_id)] = {
            "card_id": card_id,
            **names,
        }

    _require_all_cards(out, check=check)
    if not check:
        _write_out(out)
        _report_counts(out, skipped, f"offline {src_dir}")
    return out


def _fetch_lang(lang: str, version: str, timeout: int) -> dict[int, str]:
    """Fetch one language's full card payload from api.gwent.one and return it
    keyed by card_id.

    Single-language responses put the localized name at the CARD TOP LEVEL
    (card['name']) and the id at card['id']['card'] — unlike language=all which
    nests the localized fields under card[<lang>]. This is why online parsing
    reads the top level while the offline tables (already flattened by
    download.py) expose them directly. Probed for en/cn/ru/pl before batching.
    """
    url = f"{API_BASE}?key=data&language={lang}&version={version}&response=json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"api.gwent.one {lang} 返回 HTTP {exc.code}") from exc
    except (urllib.error.URLError, socket.timeout) as exc:
        raise RuntimeError(
            f"拉取 {lang} 数据失败 ({exc})；api.gwent.one 国内通常可达但较慢，请重试 --fetch"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{lang} 响应解析失败（可能传输不完整/超时截断），请重试 --fetch"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"{lang} 响应非 JSON 对象（结构异常），请重试 --fetch")
    resp = data.get("response")
    if not isinstance(resp, dict):
        raise RuntimeError(
            f"{lang} 响应缺少 response 对象（可能 API schema 漂移），请重试 --fetch"
        )
    cards = list(resp.values())
    if len(cards) < MIN_HEALTHY_CARDS:
        raise RuntimeError(
            f"{lang} 数据疑似截断（仅 {len(cards)} 条，预期 ~{MIN_HEALTHY_CARDS}+），请重试 --fetch"
        )

    out: dict[int, str] = {}
    for card in cards:
        card_id = card["id"]["card"]
        out[card_id] = (card.get("name") or "").strip()  # single-lang: top-level
    return out


def build_fetch(version: str = API_VERSION, check: bool = False) -> dict:
    """Online build: pull en/cn/ru/pl single-language payloads from
    api.gwent.one, join by card_id, emit card_names_4lang.json with the same
    schema as the offline build."""
    print(f"从 api.gwent.one 在线拉取卡牌数据（version={version}，"
          f"socket 操作最长 {LANG_FETCH_TIMEOUT}s/语言，实测总拉取约 3 分钟）...")
    by_lang: dict[str, dict[int, str]] = {}
    for lang in LANGS:
        by_lang[lang] = _fetch_lang(lang, version, LANG_FETCH_TIMEOUT)
        print(f"  {lang} {len(by_lang[lang])} 条")
    print(f"按 card_id join {len(LANGS)} 语种...")

    out: dict[str, dict] = {}
    skipped = 0
    for card_id, en_name in by_lang["en"].items():
        names = {lang: by_lang[lang].get(card_id, "") for lang in LANGS}
        if not en_name or not all(names.values()):
            skipped += 1
            continue
        out[str(card_id)] = {
            "card_id": card_id,
            **names,
        }

    _require_all_cards(out, check=check)
    if not check:
        _write_out(out)
        _report_counts(out, skipped, f"online api.gwent.one v{version}")
    return out


def _run_check(new_out: dict) -> None:
    """Diff a freshly built table against the installed one without writing.

    The HearthstoneJSON-style refresh discipline: a game patch should surface
    as an explicit added/removed/renamed diff, never as a silent overwrite of
    the lock table the whole pipeline leans on. Exit 1 when anything differs so
    automation can detect "new patch landed" from the exit code alone."""
    if not OUT.exists():
        print("现有 card_names_4lang.json 不存在——先完整构建一次再 --check。",
              file=sys.stderr)
        sys.exit(2)
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"现有 card_names_4lang.json 无法解析（{type(exc).__name__}）——"
              "重跑不带 --check 的构建命令重建。", file=sys.stderr)
        sys.exit(2)
    added = sorted(set(new_out) - set(old))
    removed = sorted(set(old) - set(new_out))
    changed = []
    for cid in sorted(set(old) & set(new_out)):
        diffs = [
            f"{lang}: 「{old[cid].get(lang, '')}」→「{new_out[cid].get(lang, '')}」"
            for lang in LANGS if old[cid].get(lang) != new_out[cid].get(lang)
        ]
        if diffs:
            changed.append(f"  {cid} ({new_out[cid].get('en', '?')}): " + "; ".join(diffs))

    print(f"对比结果: 新增 {len(added)} / 移除 {len(removed)} / 改名 {len(changed)}"
          f"（现有 {len(old)} 张, 新表 {len(new_out)} 张）")
    for label, items in (("新增", added), ("移除", removed)):
        for cid in items[:10]:
            # added 只在 new_out 里, removed 只在 old 里 — 任一侧缺失时落到另一侧
            name = (new_out.get(cid) or old.get(cid) or {}).get("en", "?")
            print(f"  [{label}] {cid}: {name}")
        if len(items) > 10:
            print(f"  [{label}] ... 还有 {len(items) - 10} 条")
    for line in changed[:20]:
        print(f"  [改名] {line}")
    if len(changed) > 20:
        print(f"  [改名] ... 还有 {len(changed) - 20} 条")

    if added or removed or changed:
        print("\n有差异（未写库）。确认后重跑不带 --check 的构建命令应用更新。")
        sys.exit(1)
    print("无差异，现有卡库已是最新。")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build references/card_names_4lang.json")
    ap.add_argument("--fetch", action="store_true",
                    help="在线从 api.gwent.one 拉取（无需本地 card-db，约 3 分钟）")
    ap.add_argument("--version", default=API_VERSION,
                    help=f"游戏版本（默认 {API_VERSION}，或 latest；latest 可能 schema 漂移）")
    ap.add_argument(
        "--src",
        default=os.environ.get("GWENT_CARD_DB", str(DEFAULT_SRC)),
        help="本地 card-db 根目录（离线模式，默认 $GWENT_CARD_DB 或 ~/gwent-card-db）",
    )
    ap.add_argument("--check", action="store_true",
                    help="只对比不写库：构建新表并与现有 card_names_4lang.json diff"
                         "（新增/移除/改名）；exit 0=无差异, 1=有差异, 2=现有库缺失/损坏,"
                         " 3=构建失败")
    args = ap.parse_args()

    try:
        if args.fetch:
            new_out = build_fetch(args.version, check=args.check)
        else:
            new_out = build(Path(args.src), check=args.check)
    except (RuntimeError, KeyError, TypeError, AttributeError, ValueError) as exc:
        print(f"错误：card_names_4lang.json 构建失败 "
              f"({type(exc).__name__}: {exc})", file=sys.stderr)
        print("（card_names_4lang.json 未生成）", file=sys.stderr)
        print("       可重试：python3 scripts/build_card_names_reference.py --fetch",
              file=sys.stderr)
        # check 模式下构建失败单独用 exit 3，与 0=无差异 / 1=有差异 /
        # 2=现有库缺失损坏 区分开——自动化不能把「没建成」当成「有差异」。
        sys.exit(3 if args.check else 1)
    if args.check:
        _run_check(new_out)


if __name__ == "__main__":
    main()
