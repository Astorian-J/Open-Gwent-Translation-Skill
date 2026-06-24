# Card Attributes Map (卡牌属性映射 — 稀有度 / 阵营)

卡牌的**属性类**信息强制映射。补两类原先散落或缺失的维度：
- **稀有度 rarity**：原先在整个 references 里零映射。
- **阵营 faction**：阵营名大多已在 terminology_map / reverse_terminology_map 强制，
  这里补齐 **Neutral/中立**（原先未注册）和**阵营缩写 NR/MO/SK/ST/SY/NE**（原先只有
  NG/SY 偶然漏入），让缩写也能被 extract_abbreviations 锁定并强制。

> **边框颜色 border color**（gold↔金卡、bronze↔铜卡）已在 `keywords_map.md` 的
> Card Types 表里强制，此处不重复；silver 已随版本移除，正确地不存在。

## Rarity (稀有度)

> 注意：rarity 词（common/rare/...）是通用英语词，**刻意不做小写扫描**（避免"common"/"rare"
> 在散文里误触发强制）。它们只在源文大写时被锁定。勿把 rarity 加进 `_factions` 那类小写扫描。

| English | Chinese | Notes |
|---------|---------|-------|
| common | 普通 | 铜卡档（beta 概念，现代昆特以颜色 gold/bronze 为准） |
| rare | 稀有 | beta 概念 |
| epic | 史诗 | beta 概念 |
| legendary | 传奇 | beta 概念；注意勿与卡名里的"传奇"混淆 |

## Faction (阵营 — 名 + 缩写)

| English | Chinese | Abbreviation |
|---------|---------|--------------|
| Northern Realms | 北方领域 | NR |
| Nilfgaard | 尼弗迦德 | NG |
| Monsters | 怪兽 | MO |
| Skellige | 史凯利格 | SK |
| Scoia'tael | 松鼠党 | ST |
| Syndicate | 辛迪加 | SY |
| Neutral | 中立 | NE |
