#!/usr/bin/env python3
"""Build references/effect_text.json — official card effect text (EN + CN).

Source: the Gwent card-data SSOT mirror (`cards_en.json` + `cards_cn.json` under
a `tables/` subdir). Joins by card_id and emits one entry per card, keyed by the
lowercased English name so the translation pipeline can look up a card's OFFICIAL
Chinese ability by the English name found in the source:

    { "<en_name_lower>": {
        "en": "Ciri",
        "cn_name": "希里",
        "cn_ability": "部署：对 3 个敌军单位造成 1 点伤害。\\n...",
        "card_id": 112101
    } }

`references/effect_text.json` is COMMITTED, so normal translation work does not
need this script or the card-db checkout. Re-run it only when card data updates:

    python3 scripts/build_effect_reference.py
    python3 scripts/build_effect_reference.py --src /path/to/gwent-card-db
    GWENT_CARD_DB=/path/to/gwent-card-db python3 scripts/build_effect_reference.py
"""

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_SRC = Path(os.path.expanduser("~/gwent-card-db"))
OUT = Path(__file__).resolve().parent.parent / "references" / "effect_text.json"


def build(src_dir: Path) -> None:
    tables = src_dir / "tables"
    en_path = tables / "cards_en.json"
    cn_path = tables / "cards_cn.json"
    if not en_path.exists() or not cn_path.exists():
        print(f"错误：找不到 card-db 数据（{en_path} / {cn_path}）", file=sys.stderr)
        print("       用 --src 指向 card-db 根目录，或设 GWENT_CARD_DB 环境变量。",
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
            # Multiple versions share a name (e.g. Shupe: mage/hunter/knight).
            # Keep the first; record it so a maintainer notices if a future
            # duplicate carries DIFFERENT abilities (wrong-version risk).
            duplicates.append((name, out[key]["card_id"], card["card_id"]))
            continue
        cn_card = cn_by_id.get(card["card_id"], {})
        out[key] = {
            "en": name,
            "cn_name": (cn_card.get("name") or "").strip(),
            "cn_ability": (cn_card.get("ability") or "").strip(),
            "card_id": card["card_id"],
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    with_ability = sum(1 for v in out.values() if v["cn_ability"])
    print(f"写出 {len(out)} 张卡（{with_ability} 含官方效果，{skipped} 跳过）"
          f" -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    if duplicates:
        print(f"⚠ {len(duplicates)} 个重名（保留首个版本，注意核对）:")
        for name, kept_id, drop_id in duplicates[:10]:
            print(f"    {name}: 保留 card_id={kept_id}，跳过 card_id={drop_id}")
        if len(duplicates) > 10:
            print(f"    ... ({len(duplicates) - 10} more)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build references/effect_text.json from card-db")
    ap.add_argument(
        "--src",
        default=os.environ.get("GWENT_CARD_DB", str(DEFAULT_SRC)),
        help="card-db 根目录（默认 $GWENT_CARD_DB 或 ~/gwent-card-db）",
    )
    build(Path(ap.parse_args().src))


if __name__ == "__main__":
    main()
