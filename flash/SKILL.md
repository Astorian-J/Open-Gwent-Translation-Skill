---
name: gwent-translation-flash
description: |
  Gwent (昆特牌) FASTEST translation for live chat — single pass by default,
  ZERO result verification. Quick reference table first; ONLY when a suspected
  proper noun is NOT in the table, run one full-corpus lookup (1381 cards +
  term tables) before translating. For fast-paced chat where waiting a minute
  means missing the conversation.
  Triggered by: 昆特秒翻, 昆特极速翻译, 昆特快翻, gwent flash translate, translate fast.
  Trade-off: no machine gate on the result. When the content matters or has
  many unfamiliar names, use gwent-translation-lite (adds a machine term gate).
  For full articles, use gwent-translation-style.
agent_created: true
---

# Gwent Translation Flash (昆特极速翻译)

> 三层速查：完整文章用 `gwent-translation-style`（全量门禁）；
> 聊天要保底用 `gwent-translation-lite`（prepare + finish --lite 机器核对）；
> **本 skill = 聊天抢速度：默认一轮直翻，不跑任何校验。**

## 你现在的任务

**本 skill 一被调用 = 你现在要做昆特牌翻译。** 不是聊天、不是分析。
拿到内容 → 判断方向（EN↔CN）→ 按下方流程翻译后立刻回复译文。
不存文件、不跑 prepare / finish / 任何校验——查库是唯一例外（见下）。

## 主 skill 目录（仅 lookup 查库时需要）

本 skill 唯一可能用到的脚本是主 skill 的 `lookup.py`。主 skill 在**本文件
所在目录的兄弟目录** `gwent-translation-style`（标准 install 布局，适用于
`~/.claude`、`~/.kimi`、`~/.agents`、`~/.hanako` 等所有安装位置）；设过
`GWENT_SKILL_DIR` 环境变量时以环境变量为准。下文 `$SK` 替换为解析出的实际路径。

## 流程：表优先，查不到才查库

1. **对照下方速查表**：源文里的专名/术语/黑话，表里有的照表翻。
2. **全部在表内 / 没有专名 → 直接翻**（1 轮，最快路径）。
3. **表里没有的疑似专有名词 → 先查全库再翻**（每个词一轮）：

   ```bash
   python3 "$SK/scripts/lookup.py" "<词>" --plain
   ```

   查的是完整库：1381 张卡牌全名 + 术语/黑话/关键词全部词表。拿不准拼写加 `--fuzzy`。

## 翻译规则

- **EN → CN**：B 站玩家口语。短句、主动语态、阿拉伯数字（5点 / 12人口 / R3）、中文括号「（）」
- **CN → EN**：native player 口气。casual 不书面，英文括号 ( )
- **禁用破折号**：别用「——」引出或补充文字（AI 味重），改用逗号 / 句号 / 括号；英文方向同理不用 —
- **修辞 / 夸张 / 反讽**：译意图不译字面（`loud design` → 存在感太强，不是「太大声」）
- **黑话保留味道**：`bleed` → 逼牌，`brick` → 卡手，`tutor` → 检索

## 专有名词规则（无核对版，凭查证要稳）

- **怎么判断哪些词算昆特专名**：结合上下文语境——出现在卡组、对局、机制、平衡讨论里的词都按昆特专名对待（哪怕是日常词，如 weather / shield / consume 出现在对局语境时）；明显日常语义的不查
- **不要盲信记忆**：拿不准是不是专名、记不准译名的，一律按专名处理先查库对照。多查一次只多一轮，翻错要返工还丢人
- 表里有的：照表翻，零创造空间
- 表里没有的：先 lookup 查全库，用查到的官方译名，禁止自创新译名
- **查不到的**（lookup 无结果）：照官方名最接近的写法翻，宁可保留原味也别造词
- 翻完直接发。**结果不核对**——发现翻错了，下一条消息更正即可

---

## 速查表

### 阵营

| 缩写 | 英文 | 中文 |
|------|------|------|
| MO | Monsters | 怪兽 |
| NR | Northern Realms | 北方领域 |
| NG | Nilfgaard | 尼弗迦德 |
| SK | Skellige | 史凯利格 |
| ST | Scoia'tael | 松鼠党 |
| SY | Syndicate | 辛迪加 |
| NE | Neutral | 中立 |

### 高频术语

| 英文 | 中文 | 备注 |
|------|------|------|
| provision | 人口 | 不是「费用」 |
| deploy | 部署 | 最常见关键词 |
| bleed | 逼牌 | R1 消耗对手资源 |
| brick | 卡手 | 抽到打不出的牌 |
| thin | 滤牌 / 压缩 | 减少牌组 |
| dry pass | 空过 | 直接过小局 |
| blue coin | 蓝币 | = 先手 |
| red coin | 红币 | = 后手 |
| coin flip | 先后手 / 硬币 | 开局先后手归属 |
| tutor | 检索 | 找特定牌 |
| highroll / lowroll | 上限发挥 / 下限发挥 | 最好 / 最坏情况 |
| tempo | 节奏 | 每回合点数 |

### 社区黑话（卡组 / 俗称）

| 英文 | 中文 |
|------|------|
| no unit archetype | 气宗 |
| Arachas Swarm | 蟹蜘蛛 |
| Fruits / Fruits midrange | 蛆妈 / 破烂怪 |
| Devotion Knights (NR) | 赤诚骑士北 |
| Armor abuse (SK) | 互口岛 |
| enemy boost (NG) | 毒奶 |

> 表里没有的疑似专名查库（lookup.py），查不到的按最接近官方写法翻。
> 速度优先：这条消息发出后对话还在继续，错了下一轮更正。
