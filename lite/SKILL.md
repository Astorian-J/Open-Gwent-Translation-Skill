---
name: gwent-translation-lite
description: |
  Gwent (昆特牌) lightweight translation for short chat content — group messages,
  Discord/QQ comments, single sentences, brief remarks. 2-command flow with a
  lightweight machine term gate (prepare --lite -> translate -> finish --lite).
  Triggered by: 昆特聊天翻译, 昆特群消息翻译, 昆特短句翻译, Gwent chat translation, quick Gwent translate.
  For full articles (meta reports, BC proposals, card analysis), use gwent-translation-style instead.
agent_created: true
---

# Gwent Translation Lite (昆特聊天短翻译)

> 短聊天内容用本 skill。完整文章（meta report / BC 提案 / 卡牌分析）用 `gwent-translation-style`
> （同一条流水线跑全量门禁，不带 `--lite`）。

## 你现在的任务

**本 skill 一被调用 = 你现在要做昆特牌翻译。** 不是聊天、不是分析。
立刻：拿到要翻的内容 → 判断方向（EN↔CN）→ 按下方流程走。
用户贴了昆特牌中/英文没明说「翻译」，默认就是要翻译，直接翻。

## 何时用

- 群消息、Discord/QQ/Kook 评论、单句、短段落（< ~200 字）
- 非正式口语内容
- 用户说「翻一下这句」「这段聊天什么意思」「quick translate」

**不要用本 skill**：长文章翻译——用 `gwent-translation-style`（不带 `--lite` 的完整门禁）。
**比 lite 还要快、完全不要核对**（直播聊天连发场景）——用 `gwent-translation-flash`（一轮直翻，无机器校验）。

---

## 专有名词铁律（最重要的一条）

源文里的人名 / 卡牌名 / 关键词 / 机制词，凡疑似昆特牌专有名词：
**一律用官方译名（prepare 锁表 / lookup 查询结果），禁止凭记忆自创译名。**
你自己「记得」的译名可能是错的——这正是机器核对存在的原因。

**怎么判断「疑似」**：结合上下文语境——出现在卡组、对局、机制、平衡讨论里的词都算（哪怕日常词如 weather / shield / consume 出现在对局语境）；**拿不准就按专名处理先查，别赌记忆**。

---

## 主 skill 目录（先定位一次）

lite 没有自己的脚本，复用主 skill。主 skill 在**本文件所在目录的兄弟目录**
`gwent-translation-style`（标准 install 布局，适用于 `~/.claude`、`~/.kimi`、
`~/.agents`、`~/.hanako` 等所有安装位置）；设过 `GWENT_SKILL_DIR` 环境变量时以
环境变量为准。下文命令里的 `$SK` 一律替换为你解析出的主 skill 绝对路径。

## 流程（标准 3 步 = 2 条命令 + 1 次翻译）

### 第 1 步：存源文 + prepare --lite（一条命令，锁表直接看输出）

```bash
printf '%s\n' "要翻译的内容" > /tmp/gwent-lite-src.md && \
python3 "$SK/scripts/translate.py" prepare /tmp/gwent-lite-src.md --lite && \
cat /tmp/gwent-lite-src.pack.md
```

内容含引号或多行时用 heredoc 存文件，其余不变：

```bash
cat > /tmp/gwent-lite-src.md <<'EOF'
要翻译的内容（可多行）
EOF
python3 "$SK/scripts/translate.py" prepare /tmp/gwent-lite-src.md --lite && cat /tmp/gwent-lite-src.pack.md
```

命令输出里就有翻译要用的全部内容，不用再单独打开 pack 文件：

- **[COPY] MANDATORY Term Lock Table** — 锁定术语，必须照抄这些译名
- **[COPY] Ambiguous Names** — 歧义卡名：按语境线索选版本，用全名
- **专有名词铁律**（pack 顶部）— 锁表没锁但疑似卡名的词，先查再翻：
  `python3 "$SK/scripts/lookup.py" "<词>" --plain`

### 第 2 步：翻译（不跑任何工具）

按方向翻译（EN→CN 或 CN→EN），照锁表 [COPY] 节译名 + 下方快速参考表：

- **EN → CN**：B 站玩家口语。短句、主动语态、阿拉伯数字（5点 / 12人口 / R3）、中文括号「（）」
- **CN → EN**：native player 口气。casual 不书面，英文括号 ( )
- **禁用破折号**：别用「——」引出或补充文字（AI 味重），改用逗号 / 句号 / 括号，原文有 em-dash 也改写；英文方向同理不用 —
- **修辞 / 夸张 / 反讽**：译意图不译字面（`loud design` → 存在感太强，不是「太大声」）
- **黑话保留味道**：`bleed` → 逼牌，`brick` → 卡手，`tutor` → 检索——不要书面化

### 第 3 步：存译文 + finish --lite（一条命令，修到 PASS 才算完）

```bash
printf '%s\n' "你的译文" > /tmp/gwent-lite-out.md && \
python3 "$SK/scripts/translate.py" finish /tmp/gwent-lite-out.md \
  --source /tmp/gwent-lite-src.md --lite
```

- **PASS** → 把译文发给用户，完成。
- **BLOCKED** → 每条违规都带官方译法（`「term」 -> 官方译名`），照着改译文文件，重跑同一条命令。
  finish 会对比上一轮违规：修复不得引入新违规（出现 `[REGRESS]` 先修新引入的）。
  最多改 3 轮；仍 BLOCKED 就把违规清单和你的译文一起给用户看，说明哪些词查不到官方译名。

`--lite` 只跑术语 / 残留 / 译名权威核对（聊天内容够用），跳过文章级的风格检查和新词学习。

## 快车道（源文明显没有专有名词时，1 条命令搞定）

整句纯情绪 / 寒暄 / 闲聊，**没有任何疑似卡名 / 关键词 / 派系缩写 / 机制词**
（如 "gg wp"、"this patch is trash lol"、"稳了稳了"）→ 可跳过 prepare，直接翻译，
然后一条命令存两个文件并核对：

```bash
printf '%s\n' "原文" > /tmp/gwent-lite-fast-src.md && \
printf '%s\n' "你的译文" > /tmp/gwent-lite-fast-out.md && \
python3 "$SK/scripts/translate.py" finish /tmp/gwent-lite-fast-out.md \
  --source /tmp/gwent-lite-fast-src.md --lite
```

finish 会从源文现算术语锁兜底，翻错的名词照样被拦（违规带官方译法）。
**拿不准有没有专名就走标准 3 步，别赌。**
（快车道固定用 `-fast-` 文件名，避免撞上标准路径残留的旧锁文件。）

---

## 不要跑以下脚本（这些是完整文章用的）

- `auto_pipeline.py` / `phase_c_check.py` / `term_enforcer.py` / `completeness_guard.py` — 已在 prepare / finish 内部运行，别手动跑
- `learn.py` / `diff_review.py` / `backtranslate.py` / `format_skeleton.py` — 完整文章流程用
- finish **不带** `--lite` — 会跑文章级风格检查，对聊天短句误报

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

> 表里没有的具体卡名 / 冷门术语，调 `lookup.py` 查（第 1 步 prepare 的锁表通常已覆盖）。
