# Card Name Overrides (人工维护)

Hand-maintained card-name overrides layered on top of the generated
`card_names_4lang.json` (built by `scripts/build_card_names_reference.py` from the
official gwent.one card data — 1381 cards × 4 languages). The big EN|CN|card_id
main table that used to live in `card_names.md` is **superseded** by that
generated table; this file holds only the parts a human must curate:

- community / outdated English **aliases** that point at a canonical card name
- community / outdated **Chinese** names that must be corrected to the official form

Load order (see `scripts/_shared.py`): the 4-language table is registered first,
then this file is applied on top. **On conflict, the override here wins.**

## Supported sections

- **`## Leader Aliases`** — columns `Alias | Maps To | Notes`. English alias →
  canonical English card (canonical already in the 4lang table). The alias locks
  to the canonical's official Chinese.
- **`## Renamed / Corrected`** — columns `Skill原版 | 修正后 | 说明`. Chinese
  wrong → correct (soft correction layer; resolves the wrong form to the correct one).
- **`## Overrides`** — columns `English | Chinese | Notes`. Direct English →
  Chinese that **forces** over the 4lang table's CN. Use sparingly — only when
  the generated CN is genuinely wrong. (Empty below: no current conflicts.)

## Leader Aliases (旧名/别名，指向正确领袖)

| Alias | Maps To | Notes |
|-------|---------|-------|
| Crown of the Seasons | Blaze of Glory | 旧条目错误映射，荣耀圣焰实为 Blaze of Glory |
| Lockdown | Imposter | 旧条目错误映射，偷梁换柱实为 Imposter |
| Dagon: The Promised One | Dagon: Promised | 旧名（带 The）→ db 新名 Dagon: Promised；两者均为「达冈：应许者」 |

> 注：旧的 `Unseen Elder → Overwhelming Hunger` 别名已删除——它把单位卡
> Unseen Elder（暗影长者，card_id 202889）误导向领袖 Overwhelming Hunger（无尽渴望）。
> Unseen Elder 的正确译名是「暗影长者」（已在 4lang 表中）。

## Renamed / Corrected (Skill原版的错误)

| Skill原版 | 修正后 | 说明 |
|-----------|--------|------|
| 沙暴 | 沙尘暴 | 服务器确认 |
| 伊魅柯 | 伊魅珂 | 服务器确认 |
| 埃斯特·图尔赛赫 | 埃斯特·图尔赛克 | 服务器确认 |
| 咯咯哒 艾伯伦特 | "咯咯哒"艾伯伦特 | 带引号 |
| 布洛妮 | 布蕾恩 | 服务器匹配（可能译名更新） |
| 雷吉斯的鸣镝动怒 | 雷吉斯：血欲化身 | 原映射错误；鸣镝动怒是领袖名 |
| 怀柔 | 战术决策 | 原映射错误；怀柔是怀柔兼济的简称 |
| 夜宴 | 女巫夜宴 | 服务器确认完整名称 |

## Overrides (English → Chinese，强制覆盖 4lang 表)

> 目前无直接冲突——4lang 表的 CN 即权威。若日后发现生成的 CN 有误，在此添加
> `| English | Chinese | 原因 |` 数据行即可强制覆盖（加载时优先于 4lang 表）。

| English | Chinese | Notes |
|---------|---------|-------|

## Notes

- 卡牌名称主数据来自 `card_names_4lang.json`（gwent.one 官方镜像，4 语种齐全，构建期生成、不入 git）。
- 'Fruits' 作为卡组 archtype 指向 沼泽果实 领袖；社区俗称用 蛆妈/破烂怪。
- '蟹蜘蛛' 是 Arachas Swarm 领袖/卡组的社区俗称，非单卡。
