#!/usr/bin/env python3
"""Build references/effect_text.json — official card effect text (EN + CN).

effect_text.json is a BUILD-TIME artifact and is NOT committed to the repo. It
holds CDPR-authored official card ability text, which is third-party
copyrighted content (see NOTICE). The repo ships the build tool only; the data
is fetched from the public api.gwent.one at install/build time.

Two modes:

  1. Online (default for fresh installs / GitHub clones):
        python3 scripts/build_effect_reference.py --fetch
        python3 scripts/build_effect_reference.py --fetch --version latest
     Pulls EN + CN single-language endpoints from api.gwent.one (slow, ~3 min,
     but CN-reachable), joins by card_id, writes effect_text.json atomically.

  2. Offline / fast (if a local card-db mirror exists):
        python3 scripts/build_effect_reference.py
        python3 scripts/build_effect_reference.py --src /path/to/gwent-card-db
        GWENT_CARD_DB=/path python3 scripts/build_effect_reference.py
     Reads tables/cards_{en,cn}.json from a local gwent-card-db checkout.

Output schema (identical for both modes, keyed by lowercased English name so
the pipeline can look up a card's official CN ability by the EN name in the
source):

    { "<en_name_lower>": {
        "en": "Ciri",
        "cn_name": "希里",
        "cn_ability": "部署：对 3 个敌军单位造成 1 点伤害。\\n...",
        "card_id": 112101
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
OUT = Path(__file__).resolve().parent.parent / "references" / "effect_text.json"

# api.gwent.one online fetch config.
API_BASE = "https://api.gwent.one/"
API_VERSION = "14.6.0"  # pinned; --version latest overrides (schema may drift)
LANG_FETCH_TIMEOUT = 120  # per-language socket-level timeout (per connect/recv op); total fetch measured ~86s/lang
MIN_HEALTHY_CARDS = 1000  # guard against truncated payloads
USER_AGENT = "gwent-translation-skill/build_effect_reference"


def _report_counts(out: dict, skipped: int, duplicates: list, source: str) -> None:
    """Print the standard build summary (shared by online + offline modes)."""
    with_ability = sum(1 for v in out.values() if v["cn_ability"])
    print(f"写出 {len(out)} 张卡（{with_ability} 含官方效果，{skipped} 跳过）"
          f" [{source}] -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    if duplicates:
        print(f"[WARN] {len(duplicates)} 个重名（保留首个版本，注意核对）:")
        for name, kept_id, drop_id in duplicates[:10]:
            print(f"    {name}: 保留 card_id={kept_id}，跳过 card_id={drop_id}")
        if len(duplicates) > 10:
            print(f"    ... ({len(duplicates) - 10} more)")


def _write_out(out: dict) -> None:
    """Atomically write effect_text.json (tempfile + os.replace) so a crashed
    half-write can never leave a corrupt file that _load_effect_text would
    otherwise parse and silently disable effect injection across the pipeline."""
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


def build(src_dir: Path) -> None:
    """Offline build from a local gwent-card-db mirror (tables/cards_{en,cn}.json).

    The offline tables are download.py's flattened output, so card_id / name /
    ability are already top-level fields (unlike the raw online response).
    """
    tables = src_dir / "tables"
    en_path = tables / "cards_en.json"
    cn_path = tables / "cards_cn.json"
    if not en_path.exists() or not cn_path.exists():
        print(f"错误：找不到 card-db 数据（{en_path} / {cn_path}）", file=sys.stderr)
        print("       用 --src 指向 card-db 根目录，或设 GWENT_CARD_DB 环境变量。",
              file=sys.stderr)
        print("       或用 --fetch 在线从 api.gwent.one 拉取（约 3 分钟，国内可达）。",
              file=sys.stderr)
        sys.exit(1)

    en_cards = json.loads(en_path.read_text(encoding="utf-8"))
    cn_cards = json.loads(cn_path.read_text(encoding="utf-8"))
    cn_by_id = {c["card_id"]: c for c in cn_cards}

    out: dict[str, dict] = {}
    duplicates: list[tuple[str, object, object]] = []
    skipped = 0
    for card in en_cards:
        name = (card.get("name") or "").strip()
        if not name:
            skipped += 1
            continue
        key = name.lower()
        if key in out:
            duplicates.append((name, out[key]["card_id"], card["card_id"]))
            continue
        cn_card = cn_by_id.get(card["card_id"], {})
        out[key] = {
            "en": name,
            "cn_name": (cn_card.get("name") or "").strip(),
            "cn_ability": (cn_card.get("ability") or "").strip(),
            "card_id": card["card_id"],
        }
    _write_out(out)
    _report_counts(out, skipped, duplicates, f"offline {src_dir}")


def _fetch_lang(lang: str, version: str, timeout: int) -> list[dict]:
    """Fetch one language's full card payload from api.gwent.one.

    Single-language responses put localized fields at the CARD TOP LEVEL
    (card['name'], card['ability']) — unlike language=all which nests them
    under card[<lang>]. This is why online parsing reads the top level while
    the offline tables (already flattened by download.py) expose them directly.
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
    return cards


def build_fetch(version: str = API_VERSION) -> None:
    """Online build: pull EN + CN single-language payloads from api.gwent.one,
    join by card_id, emit effect_text.json with the same schema as the offline
    build."""
    print(f"从 api.gwent.one 在线拉取卡牌数据（version={version}，"
          f"socket 操作最长 {LANG_FETCH_TIMEOUT}s/语言，实测总拉取约 3 分钟）...")
    en_cards = _fetch_lang("en", version, LANG_FETCH_TIMEOUT)
    cn_cards = _fetch_lang("cn", version, LANG_FETCH_TIMEOUT)
    print(f"  EN {len(en_cards)} 条 / CN {len(cn_cards)} 条，按 card_id join...")

    cn_by_id = {c["id"]["card"]: c for c in cn_cards}
    out: dict[str, dict] = {}
    duplicates: list[tuple[str, object, object]] = []
    skipped = 0
    for card in en_cards:
        name = (card.get("name") or "").strip()  # single-lang: top-level field
        if not name:
            skipped += 1
            continue
        key = name.lower()
        if key in out:
            duplicates.append((name, out[key]["card_id"], card["id"]["card"]))
            continue
        cn_card = cn_by_id.get(card["id"]["card"], {})
        out[key] = {
            "en": name,
            "cn_name": (cn_card.get("name") or "").strip(),
            "cn_ability": (cn_card.get("ability") or "").strip(),
            "card_id": card["id"]["card"],
        }
    _write_out(out)
    _report_counts(out, skipped, duplicates, f"online api.gwent.one v{version}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build references/effect_text.json")
    ap.add_argument("--fetch", action="store_true",
                    help="在线从 api.gwent.one 拉取（无需本地 card-db，约 3 分钟）")
    ap.add_argument("--version", default=API_VERSION,
                    help=f"游戏版本（默认 {API_VERSION}，或 latest；latest 可能 schema 漂移）")
    ap.add_argument(
        "--src",
        default=os.environ.get("GWENT_CARD_DB", str(DEFAULT_SRC)),
        help="本地 card-db 根目录（离线模式，默认 $GWENT_CARD_DB 或 ~/gwent-card-db）",
    )
    args = ap.parse_args()

    if args.fetch:
        try:
            build_fetch(args.version)
        except (RuntimeError, KeyError, TypeError, AttributeError, ValueError) as exc:
            print(f"错误：effect_text.json 构建失败 ({type(exc).__name__}: {exc})",
                  file=sys.stderr)
            print("（effect_text.json 未生成；skill 会以降级模式运行——翻译正常，"
                  "官方卡牌效果逐字注入暂不可用）", file=sys.stderr)
            print("       可重试：python3 scripts/build_effect_reference.py --fetch",
                  file=sys.stderr)
            sys.exit(1)
    else:
        build(Path(args.src))


if __name__ == "__main__":
    main()
