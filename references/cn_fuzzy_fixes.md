# Chinese Fuzzy Fixes (中文模糊词纠正)

For correcting typos, homophones, and abbreviated deck names in Chinese Gwent text.

## 1. Typo Corrections (错别字)

| Wrong | Correct | Type | Notes |
|-------|---------|------|-------|
| 伊魅柯 | 伊魅珂 | 别字 | "柯"→"珂"，服务器确认 [202370] |
| 埃斯特·图尔赛赫 | 埃斯特·图尔赛克 | 别字 | "赛赫"→"赛克"，服务器确认 [202883] |
| 沙暴 | 沙尘暴 | 漏字 | 缺"尘"字，服务器确认 [202205] |
| 夜宴 | 女巫夜宴 | 漏字 | 缺"女巫"前缀，服务器确认 [203054] |
| 咯咯哒 艾伯伦特 | "咯咯哒"艾伯伦特 | 标点 | 缺少引号 |
| 布洛妮 | 布蕾恩 | 音近 | 可能译名更新，服务器匹配 [142209] |

## 2. Homophone / Homograph Corrections (同音字/谐音)

| Wrong | Correct | Type | Context |
|-------|---------|------|---------|
| 户口岛 | 互口岛 | 同音 | SK armor abuse deck slang |
| 迪迦 | 辛迪加 | 谐音 | 阵营外号，辛迪加 → 迪迦 |
| 弃牌岛 | 弃牌岛 | ✓ | Actually correct (discard SK) |
| 气宗 | 气宗 | ✓ | Actually correct (no unit) |
| 肾法 | 肾法 | ✓ | Actually correct (alchemy, 谐音梗) |
| 毒奶 | 毒奶 | ✓ | Actually correct (NG enemy boost / poison) |
| 塞屎 | 塞屎 | ✓ | Actually correct (clog deck) |
| 滤干 | 滤干 | ✓ | Actually correct (thin to zero) |

## 3. Deck Name Abbreviations (卡组简称 → 全称)

### Pattern: [关键词] + [阵营简称] = [阵营全称] + [关键词] + 卡组

| Abbreviation | Full Name | Faction | Archetype |
|-------------|-----------|---------|-----------|
| 骑士北 | 北方领域骑士卡组 | NR | Knights |
| 士兵北 | 北方领域士兵卡组 | NR | Soldiers |
| 法师北 | 北方领域法师卡组 | NR | Mages |
| 攻城北 | 北方领域攻城器械卡组 | NR | Siege |
| 猎魔人北 | 北方领域猎魔人卡组 | NR | Witchers |
| 战士岛 | 史凯利格战士卡组 | SK | Warriors |
| 弃牌岛 | 史凯利格弃牌卡组 | SK | Discard |
| 自残岛 | 史凯利格自残卡组 | SK | Self-wound |
| 互口岛 | 史凯利格护甲滥用卡组 | SK | Armor abuse |
| 下雨岛 | 史凯利格雨天卡组 | SK | Rain |
| 炼金岛 | 史凯利格炼金卡组 | SK | Alchemy (Mushy Truffle) |
| 鸟岛 | 史凯利格孽鬼店店卡组 | SK | GN Shupe |
| 铺场怪 | 怪兽铺场卡组 | MO | Swarm |
| 遗愿怪 | 怪兽遗愿卡组 | MO | Deathwish |
| 成长怪 | 怪兽成长卡组 | MO | Thrive |
| 吸血鬼 | 怪兽吸血鬼卡组 | MO | Vampires |
| 三寒鸦 | 怪兽凯尔图里斯卡组 | MO | Keltullis |
| 果实/蛆妈 | 怪兽沼泽果实卡组 | MO | Fruits |
| 破烂怪 | 怪兽破烂怪中速卡组 | MO | Fruits midrange |
| 呓语帝国 | 尼弗迦德邪教徒卡组 | NG | Cultists |
| 间谍帝 | 尼弗迦德间谍卡组 | NG | Spies |
| 同化帝 | 尼弗迦德同化卡组 | NG | Assimilate |
| 塞屎帝 | 尼弗迦德塞屎卡组 | NG | Clog |
| 爆牌帝 | 尼弗迦德爆牌卡组 | NG | Mill |
| 控制帝 | 尼弗迦德控制卡组 | NG | Control |
| 位移松 | 松鼠党位移卡组 | ST | Movement |
| 和谐松 | 松鼠党和谐卡组 | ST | Harmony |
| 共生松 | 松鼠党共生卡组 | ST | Symbiosis |
| 矮人松 | 松鼠党矮人卡组 | ST | Dwarves |
| 精灵松 | 松鼠党精灵卡组 | ST | Elves |
| 手牌增益松 | 松鼠党手牌增益卡组 | ST | Handbuff |
| 炼金迪迦 | 辛迪加炼金卡组 | SY | Alchemy |
| 火誓者迪迦 | 辛迪加火誓者卡组 | SY | Firesworn |
| 赏金迪迦 | 辛迪加赏金卡组 | SY | Bounty |
| 黑市迪迦 | 辛迪加黑市买卖卡组 | SY | Off the Books |
| 大奖迪迦 | 辛迪加大奖卡组 | SY | Jackpot |
| 集会迪迦 | 辛迪加集会布道卡组 | SY | Congregate |
| 盆迪迦 | 辛迪加盆满钵满卡组 | SY | Lined Pockets |
| 海盗迪迦 | 辛迪加海盗卡组 | SY | Pirates Cove |

### Faction Abbreviation Rules

| Abbreviation | Full Name | In Deck Name Position |
|-------------|-----------|----------------------|
| 北 | 北方领域 | 后缀：骑士北、士兵北 |
| 岛 | 史凯利格 | 后缀：战士岛、弃牌岛 |
| 怪 | 怪兽 | 后缀：铺场怪、遗愿怪 |
| 帝 | 尼弗迦德 | 后缀：呓语帝、间谍帝 |
| 松 | 松鼠党 | 后缀：和谐松、矮人松 |
| 迪迦 | 辛迪加 | 后缀：炼金迪迦、赏金迪迦 |

## 4. Context-Dependent Disambiguation (语境消歧)

| Term | Meaning A | Meaning B | Disambiguation Rule |
|------|-----------|-----------|---------------------|
| 毒奶 | 尼弗迦德敌方增益 | 陶森特中毒 | 看阵营前缀/上下文 |
| 蟹蜘蛛 | 怪兽领袖/卡组 | 单卡（不存在） | 总是指领袖/卡组 |
| 黑市 | 黑市买卖（领袖） | 黑市炼金师（卡牌） | 领袖语境=OTB，卡牌语境=unit |

## 5. Auto-Detection Rules for Scripts

### Typo Detection
```
Pattern: 常用错别字表匹配
Action: 标记为 typo，建议正确写法
Severity: high (必须修正)
```

### Homophone Detection
```
Pattern: 同音字在特定语境中出现
Action: 检查是否为谐音梗/社区约定
Severity: medium (需确认)
Example: "户口岛" in SK context → suggest "互口岛"
```

### Deck Name Detection
```
Pattern: [关键词][阵营简称] or [阵营简称][关键词]
Action: 展开为完整卡组名称
Severity: info (建议展开)
Example: "骑士北" → "北方领域骑士卡组 (NR Knights)"
```
