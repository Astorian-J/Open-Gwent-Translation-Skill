# Version Map (版本映射)

Track Gwent expansion releases and their card ID prefixes.
Use this to infer which card versions are active for a given article date.

## Expansion Timeline

| Expansion | Release Date | Card ID Prefix | Chinese Name | Notes |
|-----------|-------------|----------------|--------------|-------|
| Base Game | 2018-10 | 11xxxx-16xxxx | 基础版 | Original release cards |
| Crimson Curse | 2019-03 | 200xxx | 猩红诅咒 | First expansion |
| Novigrad | 2019-06 | 200xxx | 诺维格瑞 | Syndicate introduced |
| Iron Judgment | 2019-10 | 201xxx | 钢铁审判 | Armor mechanics |
| Merchants of Ofir | 2020-01 | 201xxx | 欧菲尔商人 | New neutrals |
| Master Mirror | 2020-06 | 202xxx | 魔镜大师 | Evolving cards |
| Price of Power | 2021-07 | 202xxx | 权力的代价 | Scenario cards |
| Way of the Witcher | 2020-12 | 202xxx | 猎魔人之路 | Witcher schools |
| Black Sun | 2021-10 | 203xxx | 黑日诅咒 | Conjunction mechanics |
| Rogue Mage | 2022-07 | 203xxx | 流浪法师 | Alzur storyline |
| Tainted Wine | 2023-03 | 203xxx | 堕落的酒 | New leaders |
| Eternal Fire | 2023-09 | 203xxx | 永恒之火 | Firesworn expansion |
| Harvest of Sorrow | 2024-04 | 203xxx | 悲伤的收获 | New mechanics |

## Card ID Prefix Reference

| Prefix Range | Faction | Expansion |
|-------------|---------|-----------|
| 112xxx | Neutral | Base |
| 113xxx | Neutral (weather) | Base |
| 122xxx | Northern Realms | Base |
| 131xxx-133xxx | Monsters | Base |
| 142xxx-143xxx | Scoia'tael | Base |
| 152xxx-153xxx | Skellige | Base |
| 162xxx-163xxx | Nilfgaard | Base |
| 200xxx | Various | Crimson Curse / Novigrad |
| 201xxx | Various | Iron Judgment / Merchants |
| 202xxx | Various | Master Mirror / Witcher |
| 203xxx | Various | Black Sun onwards |

## Date-Based Lookup Rules

When translating an article, use the article's date to determine active cards:

1. **Article dated before 2019-03**: Only base game cards (11xxxx-16xxxx)
2. **Article dated 2019-03 to 2019-10**: Base + Crimson Curse (200xxx)
3. **Article dated 2019-10 to 2020-06**: Base + 200xxx + 201xxx
4. **Article dated 2020-06 to 2021-10**: Base + 200xxx + 201xxx + 202xxx
5. **Article dated 2021-10 onwards**: All cards including 203xxx

## Ambiguous Card Resolution by Date

When a base name appears without subtitle:

| Base Name | Pre-2020 | Post-2020 | Post-2022 |
|-----------|----------|-----------|-----------|
| Regis | 雷吉斯 (112104) | 雷吉斯 (112104) | + 雷吉斯：重生 (203099) |
| Dettlaff | 狄拉夫 (132104) | 狄拉夫 (132104) | + 狄拉夫：高阶吸血鬼 (202291) |
| Caranthir | 卡兰希尔 (132104) | 卡兰希尔 (132104) | + 卡兰希尔：金童 (203159) |
| Dagon | N/A | N/A | 达冈：应许者/崛起者 (203199/203208) |

## Usage in Translation

When source text includes a card name without subtitle:
1. Check the article date (from filename, URL, or user input)
2. Look up the date range in the timeline above
3. If ambiguous, use the version that was most recently released before the article date
4. For BC proposals (Balance Council), assume all current cards are active
