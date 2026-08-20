#!/usr/bin/env python3
"""Build references/card_meta.json — card type / leader / disloyal flags.

card_meta.json IS committed to the repo (unlike card_names_4lang.json and
effect_text.json, which are gitignored build-time artifacts). It holds only
structural facts derived from the gwent.one card data (see NOTICE) — card
type, leader-ability flag, disloyal flag — keyed by lowercased English name
so translate.py can look a card up by the EN name in the source and annotate
injected official-effect entries with the right Balance Change Direction tag
(leader=provision-reversed, disloyal=power-reversed, unit=normal). This script
is the reproducible source of that committed table: run it after an upstream
data update, then diff and commit the result.

Two modes (mirrors build_card_names_reference.py; mode reuse, not code copy):

  1. Offline / fast (DEFAULT if a local card-db mirror exists):
        python3 scripts/build_card_meta.py
        python3 scripts/build_card_meta.py --src /path/to/gwent-card-db
        GWENT_CARD_DB=/path python3 scripts/build_card_meta.py
     Reads tables/cards_en.json (EN only: the key is the EN name, and
     type/category/keyword_html are language-independent facts), writes
     card_meta.json atomically.

  2. Online (fallback for fresh installs / GitHub clones):
        python3 scripts/build_card_meta.py --fetch
        python3 scripts/build_card_meta.py --fetch --version latest
     Pulls the EN single-language endpoint from api.gwent.one (slow, ~1.5 min,
     CN-reachable), writes card_meta.json with the same schema.

Derivation rules (identical for both modes):

  - type: the card's own type, except ``type=Ability`` + ``category=Leader``
    which is a leader ability and is emitted as ``type="Leader"`` with
    ``"is_leader": true`` (the is_leader key is sparse — present only on
    leader abilities, matching the committed table).
  - is_disloyal: the card's keyword glossary (keyword_html) carries the
    Disloyal keyword entry. This catches cards whose ability text omits the
    explicit "Disloyal." line (Braathens, Artaud Terranova, The Eternal
    Eclipse) — a plain ability-text match would miss them.
  - duplicate names: the 3 Shupe variants each appear 6x (one Special + five
    Unit tokens); the last row wins (the Unit token), matching the committed
    table. Every collision is reported in the build summary.

Output schema (identical for both modes, keyed by en_name.lower()):

    { "<en_name_lower>": {
        "type": "Unit",            # Unit | Special | Artifact | Stratagem | Ability | Leader
        "is_disloyal": false,
        "is_leader": true          # sparse: only present on Leader entries
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
OUT = Path(__file__).resolve().parent.parent / "references" / "card_meta.json"

# api.gwent.one online fetch config (mirrors build_card_names_reference.py).
API_BASE = "https://api.gwent.one/"
API_VERSION = "14.6.0"  # pinned; --version latest overrides (schema may drift)
LANG_FETCH_TIMEOUT = 120  # socket-level timeout (per connect/recv op)
MIN_HEALTHY_CARDS = 1000  # truncation guard: a too-small payload hard-fails
USER_AGENT = "gwent-translation-skill/build_card_meta"

# Every type value the emit step may produce. "Leader" is derived locally
# (Ability + Leader category); the rest come from the card data verbatim.
KNOWN_TYPES = {"Unit", "Special", "Artifact", "Stratagem", "Ability", "Leader"}

# The Disloyal glossary span in keyword_html — matched as a keyword entry, not
# a bare substring, so "non-Disloyal" inside another keyword's explanation can
# never false-positive.
_DISLOYAL_SPAN = 'keyword">Disloyal:'


def _report_counts(out: dict, skipped: int, collisions: dict, source: str) -> None:
    """Print the standard build summary (shared by online + offline modes)."""
    leaders = sum(1 for v in out.values() if v.get("is_leader"))
    disloyal = sum(1 for v in out.values() if v["is_disloyal"])
    print(f"写出 {len(out)} 张卡（{leaders} 领袖能力 / {disloyal} 间谍，"
          f"{skipped} 跳过） [{source}] -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    if collisions:
        print(f"[WARN] {len(collisions)} 个重名（保留最后一行，注意核对）:")
        for name, (dropped_id, kept_id) in list(collisions.items())[:10]:
            print(f"    {name}: 丢弃 card_id={dropped_id}，保留 card_id={kept_id}")
        if len(collisions) > 10:
            print(f"    ... ({len(collisions) - 10} more)")


def _write_out(out: dict) -> None:
    """Atomically write card_meta.json (tempfile + os.replace) so a crashed
    half-write can never leave a corrupt file that _load_card_meta would
    otherwise parse and silently drop type tags across the pipeline."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(OUT.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # indent=0 (newlines, no indent) matches the committed table's
            # established format, so a rebuild after an upstream data update
            # diffs clean: only real data changes show up, never formatting.
            json.dump(out, f, ensure_ascii=False, indent=0)
        os.replace(tmp, OUT)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _validate(out: dict) -> None:
    """Hard-fail on a malformed or suspiciously small output.

    card_meta.json feeds the Balance Change Direction tags; a truncated payload
    or a schema drift would silently strip those tags from every pack. Fail
    loud instead of shipping a partial/misshapen table."""
    if len(out) < MIN_HEALTHY_CARDS:
        print(f"错误：输出仅 {len(out)} 张卡（预期 {MIN_HEALTHY_CARDS}+），"
              f"疑似数据截断，拒绝写出残表。", file=sys.stderr)
        sys.exit(1)
    bad = []
    for key, entry in out.items():
        fields = set(entry.keys())
        if fields - {"type", "is_disloyal", "is_leader"}:
            bad.append((key, f"未知字段 {sorted(fields)}"))  # unknown keys
        elif not {"type", "is_disloyal"} <= fields:
            bad.append((key, "缺少必填字段 type/is_disloyal"))
        elif entry["type"] not in KNOWN_TYPES:
            bad.append((key, f"未知 type {entry['type']!r}"))
        elif not isinstance(entry["is_disloyal"], bool):
            bad.append((key, "is_disloyal 非 bool"))
        elif ("is_leader" in entry) != (entry["type"] == "Leader"):
            bad.append((key, "is_leader 与 type=Leader 不一致"))
    if bad:
        print(f"错误：{len(bad)} 条条目 shape 校验失败（疑似上游 schema 漂移）:",
              file=sys.stderr)
        for key, why in bad[:10]:
            print(f"    {key}: {why}", file=sys.stderr)
        sys.exit(1)


def _emit(records: list[dict], source: str) -> None:
    """Shared emit step: validate + write the meta table built from normalized
    records (name / type / category / keyword_html / card_id)."""
    out: dict[str, dict] = {}
    ids: dict[str, object] = {}  # key -> card_id, for collision reports
    collisions: dict[str, tuple[object, object]] = {}  # name -> (first dropped, kept)
    skipped = 0
    for rec in records:
        name = (rec.get("name") or "").strip()
        if not name:
            skipped += 1
            continue
        key = name.lower()
        if key in out:
            # Only the 3 Shupe Special/Unit variants collide; last row wins
            # (the Unit token), matching the committed table. Loud in report.
            first_dropped = collisions.get(name, (ids[key], None))[0]
            collisions[name] = (first_dropped, rec["card_id"])
        is_leader = rec["type"] == "Ability" and rec["category"] == "Leader"
        entry = {
            "type": "Leader" if is_leader else rec["type"],
            "is_disloyal": _DISLOYAL_SPAN in (rec.get("keyword_html") or ""),
        }
        if is_leader:
            entry["is_leader"] = True
        out[key] = entry
        ids[key] = rec["card_id"]

    _validate(out)
    _write_out(out)
    _report_counts(out, skipped, collisions, source)


def build(src_dir: Path) -> None:
    """Offline build from a local gwent-card-db mirror (tables/cards_en.json).

    The offline table is download.py's flattened output, so card_id / name /
    type / category / keyword_html are already top-level fields (unlike the
    raw online response, which nests the id under card['id']['card'] and the
    type under card['attributes']['type']).
    """
    en_path = src_dir / "tables" / "cards_en.json"
    if not en_path.exists():
        print(f"错误：找不到 card-db 数据（{en_path}）", file=sys.stderr)
        print("       用 --src 指向 card-db 根目录，或设 GWENT_CARD_DB 环境变量。",
              file=sys.stderr)
        print("       或用 --fetch 在线从 api.gwent.one 拉取（约 1.5 分钟，国内可达）。",
              file=sys.stderr)
        sys.exit(1)

    try:
        cards = json.loads(en_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(
            f"读取/解析 card-db 数据失败（{en_path}）: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    _emit(cards, f"offline {src_dir}")


def _fetch_cards(version: str, timeout: int) -> list[dict]:
    """Fetch the EN single-language payload from api.gwent.one and return it
    normalized to the offline table's flat shape (name / type / category /
    keyword_html top-level).

    Single-language responses put the localized fields at the CARD TOP LEVEL
    (card['name'], card['category'], card['keyword_html']) and keep the id at
    card['id']['card'] and the type at card['attributes']['type'] — the offline
    tables are this same payload flattened by download.py. Probed before
    batching (mirrors build_card_names_reference.py).
    """
    url = f"{API_BASE}?key=data&language=en&version={version}&response=json"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        data = json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"api.gwent.one en 返回 HTTP {exc.code}") from exc
    except (urllib.error.URLError, socket.timeout) as exc:
        raise RuntimeError(
            f"拉取 en 数据失败 ({exc})；api.gwent.one 国内通常可达但较慢，请重试 --fetch"
        ) from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"en 响应解析失败（可能传输不完整/超时截断），请重试 --fetch"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError("en 响应非 JSON 对象（结构异常），请重试 --fetch")
    resp = data.get("response")
    if not isinstance(resp, dict):
        raise RuntimeError(
            "en 响应缺少 response 对象（可能 API schema 漂移），请重试 --fetch"
        )
    cards = list(resp.values())
    if len(cards) < MIN_HEALTHY_CARDS:
        raise RuntimeError(
            f"en 数据疑似截断（仅 {len(cards)} 条，预期 ~{MIN_HEALTHY_CARDS}+），请重试 --fetch"
        )

    out: list[dict] = []
    for card in cards:
        out.append({
            "card_id": card["id"]["card"],
            "name": card.get("name"),
            "type": card["attributes"]["type"],
            "category": card.get("category") or "",
            "keyword_html": card.get("keyword_html") or "",
        })
    return out


def build_fetch(version: str = API_VERSION) -> None:
    """Online build: pull the EN single-language payload from api.gwent.one,
    normalize it to the offline flat shape, emit card_meta.json with the same
    schema as the offline build."""
    print(f"从 api.gwent.one 在线拉取卡牌数据（version={version}，"
          f"socket 操作最长 {LANG_FETCH_TIMEOUT}s，实测总拉取约 1.5 分钟）...")
    cards = _fetch_cards(version, LANG_FETCH_TIMEOUT)
    print(f"  en {len(cards)} 条")
    _emit(cards, f"online api.gwent.one v{version}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build references/card_meta.json")
    ap.add_argument("--fetch", action="store_true",
                    help="在线从 api.gwent.one 拉取（无需本地 card-db，约 1.5 分钟）")
    ap.add_argument("--version", default=API_VERSION,
                    help=f"游戏版本（默认 {API_VERSION}，或 latest；latest 可能 schema 漂移）")
    ap.add_argument(
        "--src",
        default=os.environ.get("GWENT_CARD_DB", str(DEFAULT_SRC)),
        help="本地 card-db 根目录（离线模式，默认 $GWENT_CARD_DB 或 ~/gwent-card-db）",
    )
    args = ap.parse_args()

    try:
        if args.fetch:
            build_fetch(args.version)
        else:
            build(Path(args.src))
    except (RuntimeError, KeyError, TypeError, AttributeError, ValueError) as exc:
        retry = ("可重试：python3 scripts/build_card_meta.py --fetch"
                 if args.fetch else
                 "检查 --src 路径与数据完整性，或改用 --fetch 在线拉取")
        print(f"错误：card_meta.json 构建失败 "
              f"({type(exc).__name__}: {exc})", file=sys.stderr)
        print("（card_meta.json 未更新，旧文件保持不动）", file=sys.stderr)
        print(f"       {retry}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
