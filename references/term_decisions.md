# Term Decisions (术语裁决记录)

每一条争议术语的定名裁决都记录在此：**改动任何术语表（competitive_terms /
slang_map / terminology_map / keywords_map）里与本记录相关的条目之前，必须先在
本文件追加裁决条目（日期 + 裁决 + 来源 + 理由），否则回退。** 这是防术语表被静默
污染的铁律（借鉴 RimWorld/Minecraft Wiki 译名治理实践）。

来源二分口径：

- **官方**：CDPR 官方简中译名（含官方自带的口语化译名，如 Shupe → 店店）
- **社区**：玩家社区约定俗成（卡组俗称、黑话、论坛用语）
- **官方+社区**：官方译名本身已被社区当黑话使用

---

| 日期 | 术语/问题 | 裁决 | 来源 | 理由/依据 |
|------|-----------|------|------|-----------|
| 2026-05-30 | provision | 人口（正式语境）；「X费」仅口语 | 官方 | 初始定名；费/费用在正式语境禁用 |
| 2026-06-18 | seize | 抓捕 | 官方 | Enslave 领袖牌官方中英文对照 |
| 2026-06-24 | blue coin / red coin | 蓝币=先手 / 红币=后手；不引入 BC/RC 简写 | 社区 | BC 已被 Balance Council 占用，简写会撞名 |
| 2026-07-18 | Common（稀有度） | 普通；不是「铜卡」 | 官方 | color Bronze→铜卡 保留；稀有度与边框色撞名会产出双铜卡标签 |
| 2026-07-25 | Wagon | 进 CARD_VARIANT_COMMON_WORDS 过滤 | - | fuzzy 把 Wagon 误锁成 Dagon；Wagon 非卡名 |
| 2026-07-25 | Axel / Dagon | 不得加入通用词过滤 | 官方 | 两者都是真卡（Axel Three-Eyes / Dagon），过滤会漏锁 |
| 2026-07-29 | GN | 黄金孽鬼像（Golden Nekker，中立特殊卡）；**GN ≠ NG** | 官方 | GN/NG 字形近 + Nilfgaard 知名度高，AI 易把 GN decks 误译成尼弗迦德卡组 |
| 2026-08-20 | 狄拉夫 version_map ID | 202291/202888；132104 是卡兰希尔（复制错） | 官方 | 202888 首发于 2021-03 的 8.3 版本，归 Post-2020 列 |
| 2026-08-22 | Eternal | 进 CARD_VARIANT_COMMON_WORDS 过滤 | - | 无卡叫 Eternal；防 fuzzy 误锁 Ethereal |
| 2026-08-26 | broken → 超模 | 从 slang_map 移除「超模」译法 | 社区 | slang 是软层提示不进强制锁；「超模」曾泄漏进锁表造成歧义误报 |
| （追溯）| Shupe | 店店 | 官方+社区 | 官方简中自己采用口语化译名，社区当黑话沿用——术语表中「官方译名即黑话」的典型案例，与社区自造黑话（蛆妈/破烂怪）区分 |
| （追溯）| Ragh Nar Roog | 终末之战 | 官方 | CN→EN 锁定实测锚点 |
