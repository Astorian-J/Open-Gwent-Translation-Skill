---
name: gwent-translation-flash
description: |
  Gwent (昆特牌) FASTEST translation for live chat — single-pass reply with
  one in-turn draft self-check; NO machine gate on the result. Quick reference
  table first; enumerated hard triggers (off-table all-caps abbreviations,
  "The X" card names, fantasy-sounding names, faction-abbr + capitalized-word
  combos, and a catch-all for suspected card/character names) force one
  full-corpus lookup (1381 cards + term tables) before translating. For
  fast-paced chat where waiting a minute means missing the conversation.
  Triggered by: 昆特秒翻, 昆特极速翻译, 昆特快翻, gwent flash translate, translate fast.
  Trade-off: the self-check is model self-discipline, not a machine gate. When
  the content matters or has many unfamiliar names, use gwent-translation-lite
  (adds a machine term gate). For full articles, use gwent-translation-style.
agent_created: true
---

# Gwent Translation Flash (昆特极速翻译)

> 三层速查：完整文章用 `gwent-translation-style`（全量门禁）；
> 聊天要保底用 `gwent-translation-lite`（prepare + finish --lite 机器核对）；
> **本 skill = 聊天抢速度：一轮回复（含轮内草稿自查），不跑任何机器校验。**

## 你现在的任务

**本 skill 一被调用 = 你现在要做昆特牌翻译。** 不是聊天、不是分析。
拿到内容 → 判断方向（EN↔CN）→ 按下方流程翻译后立刻回复译文。
不存文件、不跑 prepare / finish / 任何脚本校验——查库是唯一例外（见下）。

## 主 skill 目录（仅 lookup 查库时需要）

本 skill 唯一可能用到的脚本是主 skill 的 `lookup.py`。主 skill 在**本文件
所在目录的兄弟目录** `gwent-translation-style`（标准 install 布局，适用于
`~/.claude`、`~/.kimi`、`~/.agents`、`~/.hanako` 等所有安装位置）；设过
`GWENT_SKILL_DIR` 环境变量时以环境变量为准。下文 `$SK` 替换为解析出的实际路径。

## 流程：表优先，命中硬触发必查库

1. **对照下方速查表**：源文里的专名/术语/黑话，表里有的照表翻。
2. **全部在表内 / 没有专名 → 直接翻**（1 轮，最快路径）。
3. **表外词命中以下任一硬触发 → 必须查库再翻，不问自信度**（每个词一轮）：
   - 表外的 2-4 字母全大写 token（形状如 GN / BC / OP / CA）——GN 是实测事故词：
     GN=黄金孽鬼像，不是尼弗迦德（NG 才是）
   - "The + 大写词"短语（The Great Oak、The Guardian…）——这是卡名高发形态，
     最容易被当成普通短语直接直译（The Great Oak 的官方译名是「巨橡」，不是「大橡树」）
   - 任何想按奇幻专名音译/直译的词（人名、怪物名、武器名）
   - 卡组名式组合：阵营缩写 + 空格 + 大写词（如 SK Movement GN）
   - 兜底：疑似卡名/人名但拿不准是否命中上面模式的，仍按专名处理先查库

   ```bash
   python3 "$SK/scripts/lookup.py" "<词>" --plain
   ```

   查的是完整库：1381 张卡牌全名 + 术语/黑话/关键词全部词表。拿不准拼写加 `--fuzzy`。
   模型恰恰在最有信心的地方翻车（「大橡树」就是凭记忆自信造出来的）——
   触发是模式匹配，命中即查，不靠「我觉得拿不准」。

## 翻译规则

- **EN → CN**：B 站玩家口语。短句、主动语态、阿拉伯数字（5点 / 12人口 / R3）、中文括号「（）」
- **CN → EN**：native player 口气。casual 不书面，英文括号 ( )
- **禁用破折号**：别用「——」引出或补充文字（AI 味重），改用逗号 / 句号 / 括号；英文方向同理不用 —
- **修辞 / 夸张 / 反讽**：译意图不译字面（`loud design` → 存在感太强，不是「太大声」）
- **黑话保留味道**：`bleed` → 逼牌，`brick` → 卡手，`tutor` → 检索

## 专有名词规则（无机器核对，靠轮内自查 + 查证）

- **怎么判断哪些词算昆特专名**：结合上下文语境——出现在卡组、对局、机制、平衡讨论里的词都按昆特专名对待（哪怕是日常词，如 weather / shield / consume 出现在对局语境时）；明显日常语义的不查
- **不要盲信记忆**：拿不准是不是专名、记不准译名的，一律按专名处理先查库对照。多查一次只多一轮，翻错要返工还丢人
- 表里有的：照表翻，零创造空间
- 命中硬触发的：先 lookup 查全库（见上方流程第 3 步），用查到的官方译名，禁止自创新译名
- **查不到的**（lookup 无结果）：保守直译 + 括号保留英文原名，形如「直译名（English Original）」，不静默造词——括号让存疑处对用户可见
- **翻完先自查再发**（同一轮内完成；除命中硬触发时的补查 lookup 外，不新增任何工具调用）：
  1. 先起草完整译文
  2. 回扫草稿，逐个找出专名（卡名 / 人名 / 卡组名 / 全大写缩写），对照速查表和查库结果，确认每个用的都是表内/官方译名
  3. 发现凭记忆写、表里没有的：命中硬触发的补查，查不到的改成降级写法
  4. 确认完毕，输出终稿

  没有机器门禁，这道自查是本轮唯一的纠错机会——「错了下轮更正」是给用户的兜底承诺，不是跳过自查的理由
- **纯闲聊豁免**：明显无专名的消息（"gg wp" 类）可跳过自查，直接翻译回复

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
| Golden Nekker / GN | 黄金孽鬼像（中立特殊卡，GN=Golden Nekker，别和 NG=Nilfgaard 搞混！） |
| GN deck | 黄金孽鬼像卡组 |
| GN Movement / Golden Nekker Movement | 孽鬼跳松 |
| Selfwound Armor Nekker | 孽鬼自残 |
| GN Armor Selfwound | 孽鬼护甲自残 |
| SK Movement GN | 孽鬼位移岛 |
| Fruits Consume Nekker | 果实领袖的孽鬼吞 |

### 歧义基础名（未确认版本时禁止裸名直翻）

Geralt / Regis / Triss / Yennefer / Ciri 这类基础名一张卡有好几个版本。
裸基础名出现时：语境明确指基础版卡的（Regis、Ciri 这类基础版本身是张卡），
裸中文名即官方全名，直接用；语境指某个版本的，写版本全名；拿不准版本的
禁止裸名直翻，lookup 查证或按降级写法标存疑。高频版本示例（全名照抄）：

| 基础名 | 版本示例 |
|--------|----------|
| Geralt | 杰洛特：伊格尼法印 / 杰洛特：昆恩法印 / 杰洛特：猎魔专家 |
| Regis | 雷吉斯 / 雷吉斯：血欲化身 / 雷吉斯：高阶吸血鬼 |
| Triss | 特莉丝·梅莉葛德 / 特莉丝：流星雨 / 特莉丝：蝴蝶咒语 |
| Yennefer | 叶奈法：咒术师 / 叶奈法：幻术师 / 叶奈法：未卜先知 |
| Ciri | 希里 / 希里：冲刺 / 希里：新星 |

### "The X" 类卡名（历史上整批漏锁过）

"The + 大写词"一律先当候选卡名，不是普通短语。高频示例：

| 英文 | 中文 |
|------|------|
| The Great Oak | 巨橡 |
| The Guardian | 魔像守卫 |
| The Last Wish | 最后的愿望 |

> 表里没有的疑似专名查库（lookup.py），查不到的保守直译 + 括号留英文原名。
> 速度优先：自查在轮内完成、不加轮数；这条消息发出后对话还在继续，真错了下一轮更正。
