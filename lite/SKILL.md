---
name: gwent-translation-lite
description: |
  Gwent (昆特牌) lightweight translation for short chat content — group messages,
  Discord/QQ comments, single sentences, brief remarks. Streamlined 3-step flow,
  no heavy validation pipeline.
  Triggered by: 聊天翻译, 群消息翻译, 短句翻译, chat translation, quick translate, 翻一下这句, 这段说什么.
  For full articles (meta reports, BC proposals, card analysis), use gwent-translation-style instead.
agent_created: true
---

# Gwent Translation Lite (昆特聊天短翻译)

> 短聊天内容用本 skill。完整文章（meta report / BC 提案 / 卡牌分析）用 `gwent-translation-style`
> （带 pre 注入 + 全套校验）。

## 何时用

- 群消息、Discord/QQ/Kook 评论、单句、短段落（< ~200 字）
- 非正式口语内容
- 用户说「翻一下这句」「这段聊天什么意思」「quick translate」

**不要用本 skill**：长文章翻译、需要术语锁表 / 格式骨架 / 完整校验的正式内容——
用 `gwent-translation-style`（跑 `auto_pipeline pre/post` + `completeness_guard`）。

---

## 流程（3 步，按需查询，不跑全套校验）

### 第 1 步：按需查询（仅当源文出现具体卡名 / 术语时）

**不要预加载术语表。** 只在源文里出现具体卡牌名、术语、黑话且你不确定官方译法时，查一下：

先定位主 skill 目录（首次使用时跑一次，后续命令复用 `$GWENT_SKILL_DIR`）：

```bash
# 三选一：环境变量 > Claude Code 默认 > hermes 默认
GWENT_SKILL_DIR="${GWENT_SKILL_DIR:-$HOME/.claude/skills/gwent-translation-style}"
[ -d "$GWENT_SKILL_DIR" ] || GWENT_SKILL_DIR="$HOME/.hermes/skills/gwent-translation-style"
```

查卡名 / 术语：

```bash
python3 "$GWENT_SKILL_DIR/scripts/lookup.py" "Geralt" --plain
python3 "$GWENT_SKILL_DIR/scripts/lookup.py" "blue coin" --plain
# 只记得大概拼写时，模糊匹配
python3 "$GWENT_SKILL_DIR/scripts/lookup.py" "siege" --fuzzy --plain
```

> **高频术语已在下方「快速参考」表里，不必查**——只查表里没有的具体卡名 / 冷门术语。
> **其他环境**（opencode 等）：`export GWENT_SKILL_DIR=/path/to/gwent-translation-style` 指向主 skill 安装路径即可。

### 第 2 步：翻译

按方向翻译（EN→CN 或 CN→EN）：

- **EN → CN**：B 站玩家口语。短句、主动语态、阿拉伯数字（5点 / 12人口 / R3）、中文括号「（）」
- **CN → EN**：native player 口气。casual 不书面，英文括号 ( )
- **术语 / 卡名**：用查到的官方译法（`blue coin` → 蓝币，不是「蓝色的硬币」；`provision` → 人口，不是「费用」）
- **修辞 / 夸张 / 反讽**：译意图不译字面（`loud design` → 存在感太强 / 喧宾夺主，不是「太大声」；
  `sweet spot` → 甜点位 / 刚刚好的最佳点，不是「该去的位置」）
- **黑话保留味道**：`bleed` → 逼牌，`brick` → 卡手，`tutor` → 检索——不要书面化

### 第 3 步：自检（轻量，脑内过一遍即可，不跑脚本）

输出前确认：

- 卡名 / 术语都已翻译（中文输出无英文卡名残留；英文输出无中文残留）
- 数字用阿拉伯数字（不是「五点」「十二人口」）
- 没有把术语字面直译（`blue coin` → 蓝币 ✓，不是「蓝硬币」✗）
- 黑话语气保住了（`bleed` → 逼牌 ✓，不是「消耗」✗）

**不要跑以下脚本**（这些是完整文章用的，聊天场景太重）：

- `auto_pipeline.py pre / post` — 全量术语注入 / 新词学习，短内容不需要
- `completeness_guard.py` — 5 项最终把关
- `phase_c_check.py` — Phase C 自检
- `term_enforcer.py` — 需要源文件 lock，聊天场景不适用
- `format_skeleton.py` / `learn.py` / `diff_review.py` / `backtranslate.py`

---

## 快速参考（高频，查表代替 lookup）

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

> 表里没有的具体卡名 / 冷门术语，调 `lookup.py` 查。

---

## 可选校验（通常不需要）

如果译文已存成文件、且想兜底检查术语残留（不强制）：

```bash
python3 "$GWENT_SKILL_DIR/scripts/check_translation.py" translated.txt --plain
```

不带 `--source`，只跑基础规则检查（禁用术语、英文残留、中文数字、括号等）。
聊天场景一般跳过这步，直接输出译文即可。
