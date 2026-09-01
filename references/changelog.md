# Changelog

## 2026-09-01 — 三档更名 pro/lite/flash + README 四语种同步

- **主 skill 更名**：`gwent-translation-style` → `gwent-translation-pro`。三档统一为
  前缀-pro/lite/flash 格式（lite/flash 目录名本已匹配，零改动）；skill 选择界面的
  名词与 slash 命令随之变为 `/gwent-translation-pro`。触发词不变
- **改动面**：SKILL.md name 字段、lite 两入口与 flash 入口对主档的全部引用、
  install.sh 默认目录、agent.json、_shared.py docstring；顺带清理已卸载的
  ~/.hanako 路径残留（lite/flash 共 3 处）
- **README 四语种内容同步**（上次内容同步停在 flash 档上线）：1366→1381 卡；
  health_check 63→78 PASS；文件树补 3 个新脚本（build_card_names_reference /
  build_card_meta / test_rebuild）+ card_meta.json + term_decisions.md + flash/
  目录；「一起安装主 skill 和 lite」→「一起安装三个层级」；分层节更名
  Three Tiers / 三个层级 / Trzy poziomy / Три уровня；Features 补
  macOS/Linux/Windows 跨平台；树形结构经栈式校验器四语种全过
- **迁移注意**：已装旧名目录的机器需重跑 install.sh（装到新目录）并删旧目录；
  pending_terms.md 等运行时数据先备份再恢复（install.sh 的 re-clone 分支自带
  备份/恢复，但跨目录改名需手动搬一次数据）；opencode 本地命令里的绝对路径
  需同步（仓库外配置）

## 2026-09-01 — Windows GBK 编码崩溃修复：run_utf8 统一子进程调用

- **背景**：用户在 Windows 实测报 `translate.py prepare --lite` / `finish --lite`
  崩 `UnicodeDecodeError: 'gbk' codec can't decode byte 0xa5/0x83`——
  `subprocess.run(capture_output=True, text=True)` 在中文 Windows 上用平台
  locale（GBK/cp936）解码子进程 stdout，而 auto_pipeline / completeness_guard
  输出含 UTF-8 中文（effect_text.json 等），流水线在 Windows 完全不可用
- **修复**：`_shared.py` 新增 `run_utf8()`（cmd/timeout/env/cwd 参数）——
  父进程 `encoding="utf-8", errors="replace"` 解码（脏字节降级为替换符不崩，
  诊断信息保活），子进程经 `PYTHONIOENCODING=utf-8` 强制输出 UTF-8。
  **两侧必须一起钉死**：只修父进程会把子进程 GBK 输出变成静默乱码。
  env 参数叠加在 os.environ 之上（测试隔离变量存活）
- **全仓 20 处 capture+text 调用统一换用**：_shared（context_lock build）/
  translate（run_script_json JSON runner、卡库 auto-build）/ completeness_guard
  （run_script_json）/ auto_pipeline（pre）/ check_translation（锁构建、
  term_enforcer）/ phase_c_check / diff_review / health_check ×4 / test_rebuild ×7。
  translate `run` 子命令的两处无捕获控制台透传不动（无解码路径）
- **回归**：+`_t_subprocess_utf8`（子进程直写 UTF-8 字节使父进程解码成为
  唯一变量，跨平台可复现；print 子进程验证 PYTHONIOENCODING 强制 + env
  叠加）；test_rebuild 26→27、health_check 77→78、samples 22 不变；
  prepare --lite 端到端实测 PASS
- **诚实边界**：`run` 子命令的控制台透传不经过 run_utf8 的捕获逻辑——交互式
  GBK 控制台上属显示层问题（现代 Python 控制台走 Unicode IO，退出码不受影响）；
  但外层工具若用**管道捕获** `run` 的输出，Windows 子进程仍按 GBK 字节写入管道
  （需要时外层自设 PYTHONIOENCODING=utf-8 或改走 prepare/finish 捕获路径）。
  本修复覆盖所有「捕获并解码」路径

## 2026-09-01 — 歧义名单全表重建：罗契双卡陷阱根治 + 21 组新登 + 机器不变量

- **背景**：用户报「罗契：冷酷之心和弗农·罗契还是搞混」（BC35/VK 案同型）。
  排查定位三层病根：①ambiguous_names.md 没登记 Roche——EN 裸 "Roche" 静默漏
  提取（无锁无消歧提示），模型凭名气先验默认弗农·罗契；②门禁只查一致性不查
  事实，源帖认错卡则一致地错（结构性，卡图核对防线在 bc_data 流程）；③全表
  核验发现手工维护的歧义名单烂了几个月没人发现：34 行幽灵卡名（33 个唯一
  名，卡库不存在的老名/错名）、多处官方改名漂移、1 个表头解析失败把行挂到
  上一组
- **references/ambiguous_names.md 全表重建（48→63 组）**（口径按审查复算：
  26 组核对未动；16 组同键修复；21 组新键；旧 48 - 6 组旧键退役 = 42 保留
  + 21 新 = 63）：
  - 16 组同键修复：EN 改名对齐（Regis: Rebirth→Reborn、Triss: Butterfly
    Spell→Butterflies、Yennefer: Enchantress→Conjurer、John Calveit→Jan
    Calveit、Hjalmar: Pirate→Seawolf、Vilgefortz: Renegade Mage→Renegade、
    Dagon/Tyr/Gregory/Torres 副标题对齐现名）+ 成员修到现役（Caranthir 幽灵
    基名卡→Caranthir Ar-Feiniel、Usurper 全组、Harald 补到 5 张、
    Dol Blathanna/Aen 组换现役成员）
  - 21 组新键：姓氏形态 Roche/Adda/Roderick + 冒号形态 Auberon/Eithné/
    Frightener/Gigascorpion Decoction/Jacques/Red Riders/Saber-Tooth Tiger/
    Saesenthessis/Saov Ainmhi'dh/Shaping Nature/Shupe/Treant Mantis/Vial of
    Forbidden Knowledge/Viraxas + 4 个官方改键继任组（Dana Meadbh→Dana
    Méadbh、Kitsune→Aguara、Lake Guard→Lake Guardian、Melitele's Temple→
    Temple of Melitele）
  - 6 组旧键退役 = 上述 4 个继任键 + 2 组全幽灵删除（Seer、Clan Dimun
    Pirate，卡库零命中）
  - 清除 34 行幽灵卡名（33 个唯一名）
  - 所有 CN 名逐字取自 card_names_4lang.json；线索列卡面数值与阵营词经
    gwent-card-db 核实，且阵营词校验已并入 health_check 机器守护（需
    gwent-card-db 在场）
- **scripts/_shared.py 提取器重音支持**：CARD_NAME_PATTERN /
  extract_card_names_no_colon / extract_capitalized_phrases 三个词模式补
  À-ÿ 区间（同 _VARIANT_TOKEN_RE 先例）；修复 "Dana Méadbh: Caretaker"
  全名隐形且子串 Caretaker 误锁看门人的存量缺口；歧义表头解析正则放开
  重音字母（Dana Méadbh / Eithné 组此前会解析失败挂到上一组）
- **health_check 新增 check_ambiguous_names**：歧义表与卡库逐字对照（幽灵/
  CN 漂移/表头计数）——这份文件此前无任何机器守护，漂移数月无人知；缺库时
  降级 INFO（同 effect_text 惯例）
- **端到端实测**：裸 "Roche" → 歧义提取 + pack 双卡线索（NR 2/9 不忠间谍 vs
  NR 4/12 直伤蓝衣铁卫）；译文写弗农·罗契 PASS；裸写「罗契」BLOCK 且违规信息
  内联两个候选全名
- **回归**：samples 基线 22 不变（零新增误报）；test_rebuild 25→26
  （+_t_ambiguous_rebuild，含 Éibhear 重音首字母断言）；health_check 75→77
  （+1 歧义不变量 +1 行为测试计入；75→77 的构成经 HEAD 快照对账属实）
- **诚实边界**：源帖自己认错卡（写成另一张的真名）任何术语门都拦不住，只能靠
  bc_data 的卡图核对铁律。含裸基础变体的组（自然法则/萨琪亚/红骑士/鹿灵/
  狐妖/达娜梅碧/巨蝎煎药/刃齿虎/老矛头/卡兰希尔/禁识之瓶/萨琪亚萨司 12 组）
  的中文裸名门禁结构性不触发——基名出现即满足 has_full，这是「裸名=基础版」
  设计的既定行为，不是漏洞；真正的新误报面是 CJK 子串：译文含「商店店员」
  会命中「店店」组的裸名检查（同「约翰」组先例，昆特语料概率低，接受并记录）

## 2026-09-01 — flash 提示词层加固（自查回路 + 硬触发 + 扩表 + 降级写法）

- **背景**：flash 纯提示词层分析定位
  四个根因——无校验回路、查库触发靠元认知、速查表覆盖率 25/1738≈1.4%、
  未知名静默造词；两起实测事故（The Great Oak→大橡树、GN/NR→尼弗迦德）均有
  仓库内记录（changelog 2026-08-27 条目与 2026-07 补记 a80d56a）
- **flash/SKILL.md**：①流程第 3 步「拿不准才查库」改枚举式硬触发（表外全大写
  缩写 / "The X" / 奇幻音直译词 / 阵营缩写+大写词组合 + 疑似即查兜底，命中即查
  不问自信度）；②专有名词规则加单轮自查回路（起草→回扫草稿专名对表→确认/改写
  →终稿，轮内完成不加轮数）、未知名降级写法（保守直译+括号留英文原名）与纯闲聊
  豁免；③社区黑话表 +7 行 GN 系词条（逐字抄自 competitive_terms.md:44/234-265，
  全行标点转全角，含「别和 NG 搞混」警告）；新增歧义基础名（裸名未确认版本禁止直翻）与 "The X"
  示例两节；description 与两处「不跑任何校验」表述同步为「无机器校验/门禁」口径
- **代价诚实**：自查回路 = 草稿+终稿两遍生成，输出 token 接近翻倍——这是 flash
  为准确性新付的速度代价（轮数不变，生成变长）；纯闲聊豁免兜底最常见的抢速度
  场景。flash 仍无机器门禁，自查是模型自律不是机器保证，要保底仍路由 lite
- **同步**：README 四语种 flash 行；lite 两入口指向 flash 的描述限定口径；
  install.sh 两处 flash 定位语；opencode /gwent-flash 命令（仓库外本地配置）
- 不动任何脚本与权威词表；lite/style 机制不变

## 2026-08-29 — 开源调研落地的七项增强（四批）

背景：三路开源调研（翻译 skill 生态/术语强制工作流/游戏社区翻译工具，全文见
auto-memory gwent-translation-open-source-survey）确认我们的核心机制无同类，
但散落着可借鉴设计；用户拍板七条全做。学习类写入全部走 gitignored 本地缓冲
（pending_terms.auto.md），更新永不覆盖学习记录（8-27 已建立的机制）。

**批A 门禁增强（translate.py + check_translation.py）**
- finish 修复回归追踪（strict-subset 借鉴）：BLOCKED 时把违规指纹基线落盘
  `<source>.gate.json`（源文件哈希绑定；挂在源文件而非译文文件——换文件名重存
  不断链），下一轮对比出 [REGRESS]（新引入的违规）与 [FIXED]（已解决数）；
  PASS 清基线；--fresh 逃生口（整篇重写后用）。violations JSON 加 repair_tracking。
  同源必同锁，无需锁指纹（实测推演后简化）
- 校验清单对表（Weblate/zotero 经验）：新四查——protected token（链接/行内代码
  原样保留）、粗体 ** 全丢、completeness（≥4 行非空且译文不足一半=疑似整段漏译）、
  empty（空译文）；ISSUE_CATEGORIES 加 format/protected_token/empty_translation/
  completeness，注释对齐 MQM 类目口径
**批B 学习整合（learn.py）**
- --from-lock：把锁表里 status=pending 的机器提取未知词（prepare 精挑的候选）
  并入同一 gitignored 自动缓冲，人审从「想词」变「勾词」；finish PASS 后带
  --from-lock 调 learn；JSON 加 from_lock_candidates
**批C 数据治理**
- 新建 references/term_decisions.md 术语裁决记录：改动术语表前必须先补裁决
  （日期+裁决+来源+理由），回填 12 条历史争议（GN≠NG、seize→抓捕、Common→普通、
  店店=官方简中自带口语译名等）；slang_map/competitive_terms 头部挂裁决记录指针
  与来源口径（官方/社区/官方+社区 二分）
**批D 卡库管道（build_card_names_reference.py）**
- --check 只对比不写库：构建新表 diff 现有库（新增/移除/改名，exit 1=有差异），
  游戏补丁以显式 diff 呈现而非静默覆盖（HearthstoneJSON 模式借鉴）
- 测试：test_rebuild 加 _t_repair_tracking + _t_new_format_checks（25 用例）

## 2026-08-28（三）— lookup 接上 1381 卡全库 + flash 条件查库 + 专名判断引导

- **存量缺口**：lookup.py 只搜 12 张术语/黑话 markdown 表，不含卡牌全名（全名在
  gitignored 的 card_names_4lang.json，仅 TermAuthority 加载）——lite 铁律
  「疑似卡名先 lookup 查证」实际查不到普通卡名
- **lookup.py**：新增 search_card_db（精确>子串>fuzzy，仅 en/cn 字段；子串 1.0 与
  md 表对齐），结果与 markdown 表命中合并按分数排序，format_result 加卡牌分支
  （en → cn [card_id]）；**slang_map.md 补进搜索范围**（此前宣传查黑话实际查不到，
  审查 I-2）；库缺失/损坏 stderr 分开 WARN + 构建指引含本地镜像；空查询拒绝
  （原会子串命中全表+1381 卡）
- **flash/SKILL.md**：「零脚本」改「表优先、查不到才查库」——表内有/无专名 1 轮
  直翻不变，表外疑似专名先 lookup（每词 1 轮）再翻；新增主 skill 目录定位节；
  description 同步；opencode /gwent-flash 同步
- **专名判断引导（用户提出）**：三处同步加两句话——「结合上下文判断哪些词算昆特
  专名（对局/卡组/机制/平衡讨论里的词都算，日常词在该语境也算）」+「不要盲信记忆，
  拿不准就按专名处理先查库」。落点：flash 专有名词规则、lite 铁律、lite/AGENTS.md
  term rule、translate.py pack 术语铁律（两种 pack 共用）
- **收益外溢**：lite 铁律的 lookup 查证与 flash 兜底从此都是真全库
- test_rebuild 加 _t_lookup_card_db（23 用例，含 md+卡库合并断言与缺库守卫）；
  pragmatic 审查 0C/2I/5M：I-1 部署未做（本轮部署解决）、I-2 slang_map 缺失（已修）、
  M-1/M-3/M-4/M-5 已修，M-2 fuzzy 微调接受不改（目标卡在 top-5 内）；deploy 4 副本

## 2026-08-28（二）— flash 极速版（三层体系补齐）

- **背景**（用户实测反馈）：用千问 app 翻译几秒出结果，走 skill 要 1 分钟到几分钟
  （agent 每轮模型思考 5-20s 乘以轮数），直播聊天场景跟不上对话节奏。脚本本身仅
  0.34s，瓶颈在 agent 轮次；用户拍板新增完全不跑脚本的第三档
- **flash/SKILL.md**：新 skill `gwent-translation-flash`——单轮直翻（读消息→翻→回，
  不存文件不跑脚本不核对），凭记忆+速查表翻；规则含方向风格/禁破折号/修辞译意图/
  黑话保留 + 软版专名铁律（凭最通行官方译名、NG≠NR 别搞反）；三张速查表与 lite 一致
- **定位**：style（文章全量门禁）→ lite（聊天+机器核对，2-3 轮）→ flash（直播聊天
  抢速度，1 轮无核对）；flash description 明确"不确定卡名/要保底用 lite"防误路由；
  lite 两入口反向指向 flash
- **部署**：install.sh 加 flash 目录部署（镜像 lite 模式）；README 四语种加 flash 档
- **诚实标注**：flash 无任何校验，卡名靠模型记忆——这正是它换速度的代价，用户知情选择

## 2026-08-28 — lite 提速：聊天级 pack + 3 轮往返流程 + 无专名快车道

- **背景**（用户反馈 lite 不够轻、流程慢）：实测脚本本身仅 0.34s（prepare 0.17s +
  finish --lite 0.17s），瓶颈在 agent 工具调用往返（每轮 5-20s，标准流程约 7 轮）
  与 pack 内容——聊天一句也生成 5.5KB pack，其中平衡方向/Markdown 格式/Phase C
  清单全是文章级 padding（且 finish --lite 不跑 Phase C，清单纯误导）
- **prepare --lite（translate.py）**：新增 lite pack 模式——砍掉 PACK_BALANCE_GUIDE /
  PACK_FORMAT_GUIDE / 官方效果注入 / Phase C 验收清单（finish --lite 不 gate 的
  全部裁掉），风格表按行标签过滤（LITE_STYLE_ENC/CN），头部与 NEXT STEP 精简
  （finish 命令带 --lite）；实测 pack 5476→2671 字节（-51%），完整版 pack 不变；
  `run --lite` 同时透传 prepare 与 finish
- **lite 入口流程重写（lite/SKILL.md + lite/AGENTS.md）**：标准流程 7 轮往返 → 3 轮
  （①存源+prepare --lite+cat pack 一条命令 ②翻译不跑工具 ③存译文+finish 一条
  命令）；新增快车道——源文明显无专有名词（"gg wp" 类）跳过 prepare，存两文件 +
  finish --lite 一条命令（finish 从源文现算锁兜底），固定 `-fast-` 文件名避免撞
  标准路径残留 sidecar；目录定位改兄弟目录单一规则（删 hermes 死默认路径）
- **文档同步**：README 四语种 Lite 段重写（原描述还停留在更早的"脑内自检"版）；
  agent.json prepare/run 补 --lite 参数 + json_output 对齐实际字段
  （修 skeleton_extracted 等陈年幽灵字段）
- 安全门不变：术语 / 残留 / 译名权威三道门在 lite 下全保留，精度不降

## 2026-08-27 — pending_terms 模板/数据分离（学习记录更新不重置）

- **背景**（用户实测 NR/GN→尼弗迦德误译排查后提出）：pending_terms.md（learn.py
  人审收件箱）原被 git 跟踪，与 skill 其他文件同命运——远端更新该文件时 pull 会被
  本地学习记录挡住，部署排障时的 `git checkout -- .` 会把学到的词全部洗掉
- **改动**：仓库只跟踪模板 `pending_terms.template.md`（原文件 git mv 改名）；
  `pending_terms.md` 加入 .gitignore 成为纯本地运行时数据，pull/重装/checkout
  物理上碰不到它；install.sh 新装时从模板初始化（有备份恢复优先）；
  health_check 加模板存在性检查；learn.py / translation_workflow.md 的
  "tracked inbox" 措辞同步；README 四语种目录树 + 缓冲区"更新不重置"说明
- **迁移注意**：tracked→untracked 切换的这一次更新，副本需走 install.sh
  （备份→拉取→恢复），本地文件有学习记录时裸 pull 会被 git 直接拒绝
  （local changes would be overwritten）；hanako 非 git archive 部署
  天然不受影响（archive 里不再含 pending_terms.md）
- 回归：test_rebuild 21 / health_check 71→72（+模板检查）/ samples 22 不变

## 2026-08-26（三）— 禁用破折号规则进全部提示词入口

- 用户要求：翻译不用破折号表达文字（「——」引出/补充是典型 AI 味）
- 五处同步：translate.py STYLE_ENC/STYLE_CN（pack 风格表，双向各加 Dash 行）、
  SKILL.md 两张方向表、lite/SKILL.md 与 lite/AGENTS.md 第 2 步、
  style_reference.md 新增 Punctuation: No Dashes 节（含改写示例）
- 规则口径：EN→CN 全文无「——」，原文 em-dash 也改写成逗号/句号/括号；
  CN→EN 英文输出不用 —
- 回归：test_rebuild 21 / health_check 71 / samples 22 不变

## 2026-08-26（二）— 小写 competitive 短语锁定 + 弯撇号卡名提取（blue coin 类聊天术语漏锁根治）

- **根因**（部署实测发现）：散文/聊天里小写 "blue coin" 完全不进锁——锁表只认大写
  提取器抓到的词，大写"Blue Coin"被强制、小写漏网纯属运气差异；"蓝色的硬币"这类
  字面乱翻（用户 lite 问题的典型形态）门禁抓不到
- **修复 1**：`competitive` 多词短语（blue coin / dry pass / tall punish…）进
  `_game_terms` 小写扫描（词边界精确短语匹配）；**单词暂不进**——warrior/dragon/
  move 这类极易撞卡组缩写（PF Warriors）和卡名子串，实测全为假阳性，等撇号提取
  与卡组缩写数据补齐再开；deck_name 维持排除（宽松卡组词汇，防过度锁定意译）
- **修复 2**：弯撇号卡名提取根治——`get_all_for_text` 入口 `_QUOTE_NORM` 归一化
  （位置保持 1:1）+ 三个卡名提取器词模式允许撇号组（`Dragon's`）+ `resolve()`
  所有格回退（`Schirru's`→`Schirru`）。此前 "Dragon’s Dream/Necromancer’s
  Tome/Cleaver’s Muscle" 这类真卡名整体漏提取，只有子串被锁
- **验证**：blue coin 小写锁定✓、Dragon’s Dream→龙之梦✓、Schirru's→希鲁✓、
  warrior/dragon/move 假阳性清零✓
- **samples 基线 18→22**：+4 全部逐条核实为真违规（tall punish 缺大怪惩罚；
  Necromancer’s Tome 译文写自创名「死灵术之书」实为邪灵法典；Cleaver’s Muscle
  译文插引号改写官方名；Nature’s Gift Midrange 缺破烂小叶子卡组）——老样本的
  陈年错误因提取覆盖扩大而现形，非误报
- test_rebuild 21 / health_check 71 不变

## 2026-08-26 — dsh 3 条可用性反馈 + 用户实测两问题：歧义消歧链修复 + lite 强制门禁

- **歧义卡名消歧链修复**（用户实测问题①，核心修复）：`resolve()` 里精确匹配
  排在歧义检查前，同名基础卡（Regis/Dandelion/Ciri/Avallac'h 这类"基础版本身
  是张卡"的）永远锁死基础版译文，按语境线索选副标题版本反被 finish 拦——
  歧义检查提到精确匹配之前（全名匹配不受影响）；配套 `_drop_subsumed` 补堵
  歧义条目（无 cn）不走覆盖弃锁的洞（源文只出现全名时译文写基础版仍被拦）
- **歧义名线索 + 违规带候选**：`ambiguous_names.md` 第 3 列语境线索（如
  "Shield/protection context"）现在注入 pack 歧义名节（`_load_ambiguous_names`
  带 clue 字段流到 variants）；check_translation 歧义违规消息内联全部候选中文
  全名，修错不用翻参考文件
- **lite 强制名词核对**（用户实测问题②）：finish 新增 `--lite`（guard `--lite`
  跳过 Phase C 风格检查；finish 侧再跳过 learn + effect 审计；术语/残留/译名
  权威三道门保留）；lite SKILL.md/AGENTS.md 流程重写为 prepare → 翻译 →
  finish --lite 修到 PASS，废除"脑内自检"；新增专有名词铁律（疑似昆特名词
  禁止凭记忆自创译名）——治 lite 随便给译名
- **pack 分节标记**（dsh#1）：所有节打 `[COPY 照抄]`/`[JUDGE 判断]` 标签 +
  顶部图例；pack 顶部加专有名词铁律（含 lookup 查证命令）
- **finish 违规全量透传**（dsh#2）：finish 调 guard 恒传 `--verbose-terms`
  （机器对机器不要 top-5 采样），JSON violations 恒全量；控制台展示上限 5→20；
  finish 自己的 `--verbose-terms` 参数删除（已无行为差异）
- **run 子命令**（dsh#3）：`translate.py run source [--translated out]`——
  无 --translated=prepare+打印路径预解析的确切 finish 命令；带 --translated=
  prepare+finish 一键；finish 在 `--source` 无对应 lock sidecar 且同目录存在
  其他 sidecar 时打 WARN 列出已 prepare 过的文件名（路径传错一眼可见）
- **residue 误报修复**：guard 里 `terminology_ok=False`（查出问题）被误当
  "crashed"，术语一有问题 residue 就跳过且误报"Residue not checked (crashed)"
  ——拆分 crashed 标志，residue 恒从 check2 结构化 issues 派生
- 回归：test_rebuild 20→21（+歧义基名优先级测试）、health_check 70→71、samples encn 基线 18 不变

## 2026-08-22（四）— 批3：守卫链去重 + prepare/finish 锁绑定 + effect 接入（交流式方案收官 3 项）

- **守卫链去重**（kimi#1）：guard 内 term_enforcer ×3→×1（check5 唯一实跑）；
  check_translation/phase_c 新增 --skip-ta（guard 传；phase_c encn-10 skip 时降
  manual note）；residue 检查改为从 check2 结构化 issues 按类别派生（物理删除
  auto_pipeline scan 子进程）；**parse_ta_envelope 单点解析**（判值不判键/降级计
  违规），三份解析拷贝（guard/phase_c/check_translation）全部收敛；顺删两处
  rc==0 早退（会吞 rc=0 时的降级警告）
- **prepare/finish 锁绑定**（dsh#4+kimi#5 撞车）：prepare 落 `<source>.lock.json`
  sidecar（带 source_sha256）；finish 优先复用（lock_reused），源变更→BLOCK，
  --allow-source-changed=按当前源重建（**审查抓出初版 Critical：逃生口误传过期锁**，
  已修+测试钉死）；guard --lock（缺失 fail-closed 不回落；不删调用者的锁）；
  NEXT STEP/提示改绝对路径
- **effect_verifier 接入 finish**（kimi#7）：effect_check 信息性输出（绝不影响
  退出码），无主脚本归位
- 新增 _t_parse_ta_envelope + _t_pipeline 绑定两段；test_rebuild 19→20、
  health_check 69→70
- pragmatic 审查批3 1C/4I/8M：Critical+4I+可修 Minor 全修，residue 双计数等
  3 条既有项带理由缓议；报告 .scratch/comm-dev-0822/review-report-batch3.md
- 至此 2026-08-22 交流式开发 12 项方案全部落地（3 批 3 提交，来源 dsh+kimi 双
  agent 评审，全部过 pragmatic 子 agent 审查）

## 2026-08-22（三）— 批2：skeleton 摘除 + learn 噪音根治与缓冲落盘 + 编排级测试（交流式方案第二批 3 项）

- **skeleton 摘除**（kimi/dsh/Claude 三方终裁）：auto_pipeline pre 物理删除 skeleton
  步骤（tempfile/Step/报告键/人类输出/陈旧清理 pattern，步骤 6→5 重编号）；translate
  ready 公式与输出同步；文档全面对齐（README 工作表/workflow Step3 改"照 pack 的
  格式保留节做"/lite 两文件标 standalone）
- **learn 噪音根治**（BC34 五条噪音 → 0）+ 根因修复：_QUOTE_NORM 提升到 _shared，
  _add_term 弯引号折叠（原 ASCII 守卫把 "Manor’s" 类卡名整张丢弃→已知词表缺口）；
  Pattern 3/4 常用词门（NOTE 类表格标记，SKIP_WORDS_FULL +Note/Rank/Name/Type/Date/Total/Top）；
  typo 门 _is_typo_of_known（整键+词级两档距离≤1，最短长度护栏 5 防 Kiri↔ciri 误杀）
- **learn 落盘改造**：--auto 写 gitignored 缓冲 pending_terms.auto.md（装机副本不再
  dirty，ff-only pull 不再挂）；新增 --commit 合并入 tracked 审核收件箱后删缓冲
  （missing_ok 防并发）；Discovered 日期在合并时保真；SKILL/AGENTS/workflow 文档同步
- **编排级测试 _t_pipeline**（dsh#5）：tmp 副本隔离跑 prepare→good/bad finish→
  4lang 缺失 fail-closed 四段断言（GWENT_CARD_DB 空目录保证离线）。**首跑即抓到真
  bug**：prepare 的 [AUTO]/[INFO] 诊断打 stdout 污染 --json 信封 → 已全部改 stderr
- test_rebuild 18→19、health_check 68→69；samples 基线 18 不变
- pragmatic 审查批2 0C/4I/5M 全修（typo 门短词误杀实证/skeleton 与 learn 两片文档
  失同步/commit 并发 unlink/pending 折叠不变量/日期保真/裸 clone 前置指引）；
  报告 .scratch/comm-dev-0822/review-report-batch2.md

## 2026-08-22（二）— 批1：BLOCKED 明细透传 + lite 修复 + 锁表过滤（交流式开发 12 项方案之首批 6 项）

- **finish/guard 违规明细透传**（dsh+kimi 双撞车项）：三个子检查 + term_authority
  全部改为内部 --json 解析（物理删除全部人类文本抠数字分支）；明细进
  checks[].issues（terms_summary 截断）；guard BLOCKED 与 finish BLOCKED 逐条打印
  （format_issue 共用渲染，含 rule_id）；finish 顶层 violations 聚合全部失败检查
  （带 check 标签）+ violations_total（真值=各检查 issue_count 之和）
- **lite 修复**：删两处 check_translation --plain 假命令（该 flag 史上不存在，
  lookup 的 flag 张冠李戴）；路径解析加"兄弟目录上溯"指引（自定义 INSTALL_DIR
  布局命中）
- **pack 锁表过滤**：_load_lock_terms 只收 confirmed/auto_locked（对齐
  context_lock:158 口径），MANDATORY 表不再出现空中文行；顺删恒不触发的
  setdefault 死代码
- **注释/文档对齐 6 处**：translate.py cnen 旧注释/--direction help；guard
  not_applicable 死分支物理删除+docstring 收窄；check_translation TA 注释改真话；
  AGENTS.md 两处矛盾（:206 单双向、:291 保留值）
- **install.sh**：effect_text 本地镜像优先（对齐 card_names 两段式）；尾部加
  health_check 自检（信息性）
- **微优化**：_card_db_status 模块级缓存（构建成功显式失效）；_parse_json_envelope
  物理删除扫描兜底（污染源已迁 stderr，fail-closed 由调用方保证）
- **新增 4 项测试**（_t_format_issue_shapes/_t_lock_terms_filter/
  _t_violations_aggregation/_t_card_db_cache），test_rebuild 14→18、health_check
  64→68
- pragmatic 审查批1 0C/3I/5M 全修（NameError 兜底崩溃/guard 人类模式 TA 明细
  双缺口/新逻辑零覆盖 + 5 Minor）；报告 .scratch/comm-dev-0822/review-report-batch1.md

## 2026-08-22 — 子串卡名弃锁 _drop_subsumed + eternal 屏蔽（BC34 假违规修复）

- **来源**：dsh（DeepSeek Harness）翻译 BC34 排名表实测发现并提交补丁，
  Claude 独立复现+复核+审查后合入。
- **bug**：只出现在更长卡名里的子串卡名被单独加锁（如源文只有
  "Avallac'h: Sage" 却同时锁裸 "Avallac'h"），CJK 吸收规则使短名锁
  永远不可通过 → finish 对正确译文报假 term_missing。
- **修复**：`get_all_for_text` 末尾 `_drop_subsumed`——术语在源文的所有
  出现都被更长已锁卡名 span 包含时，丢弃该独立锁（长名锁已验证官方译名，
  零拦截损失）。独立出现不受影响（保留短锁）。
- **顺带**：samples 基线 25→18，消失 7 条（Brewess/Griffin/Guerilla/
  Imposter/Pockets/Schirru/Yago）逐一核实全为同类陈年假阳性。
- **CARD_VARIANT_COMMON_WORDS + eternal**：Eternal 模糊误配 Ethereal
  （编辑距离 2）的复发防线；无卡正好叫 Eternal，同 wagon→Dagon 先例。
- **test_rebuild 新增 `_t_subsume_guard`**（弃锁/独立出现保留/无 Ethereal
  误锁三断言），13→14；health_check 63→64 PASS。
- **回归基线变化**：encn samples `check_translation` 基线由 25 改为 18
  （假阳性修复所致，非漏检；bc34 案例锁表 41→38）。

## 2026-08-20 — 批B：文档对齐 + 数据维护 + 目录卫生（M2/M3/M13/M14/M16/M17/L2/L10）

- **M2** SKILL.md 关于 `finish` "edits no file" 的说法改为真话（不碰译文文件；
  PASS 后 learn.py --auto 追加 pending_terms.md）。
- **M3** AGENTS.md 三处过时：pre 的 JSON 示例 locked_terms 条目修为实际形状
  （仅 canonical_en/chinese）；文档化默认 top-5 截断与 `--verbose-terms`；
  term_authority status 文档改为 ran/skipped/error（not_applicable 已废弃，
  CN→EN 也强制执行）。
- **M16** translation_workflow.md：auto_pipeline pre/post 表述统一为
  translate.py prepare/finish 入口；步骤断号 0-3/5/6/8/9 重排为 0-7；
  Step 6 补"翻译工作文件放 skill 目录外"指引；pending_terms 格式指引改指文件头模板。
- **M17** lite/AGENTS.md 两处断链修复（`../AGENTS.md` 改运行时定位、删悬空
  `../SIMPLE-MCP-PLAN.md` 引用）；lite/SKILL.md 流程表述已在批A对齐。
- **M13** 补记 2026-07-24 ~ 07-30 共 20 个提交的 changelog（见下方补记节）。
- **M14** version_map.md 狄拉夫行 ID 修正：132104 是卡兰希尔的 ID（复制错），
  改为真实的 202291/202888；全文件 ID 已对照 card_names_4lang.json 审计，
  其余零错误。
- **L2** .gitignore 补 source.md / source.pack.md / translated.txt 防翻译残留
  再落仓库根；部署目录的三个残留文件已清理。
- **L10** 删除过时两个月的旧打包 ~/.claude/skills/gwent-translation-style.zip。

## 2026-08-20 — 批A：代码行为类修复（13 组，A1-A13）

第二轮审查（/tmp/gwent-review-round1.md）的代码行为类问题一次性修复，详见
`fix-report-batch-a.md`：

- **A1/M1 删 `auto_pipeline post` 僵尸路径**：post 子命令全代码库无调用方，物理删除
  （函数本体 + argparse 注册 + main 分支）；docstring 与 pre/scan/guard 的出口文案
  统一指向 `translate.py finish`；AGENTS.md / README 四语种 / agent.json /
  SIMPLE-MCP-PLAN.md / translation_workflow.md / lite 两文件同步清零 post 引用。
- **A2/L1 死代码物理删除**：`scripts/agent_utils.py` 整文件（纯 re-export 垫片）；
  `_shared.TermAuthority.get_canonical/get_cn`；`context_lock.extract_terms_from_source`；
  `diff_review` 未用的 SequenceMatcher import 与死计算；`lookup.py` 双分支相同去重；
  `learn.py` 未使用的 `translated` 参数。
- **A3/M7 解析器收敛（按 2026-07-01 先例逐个实证判断）**：`lookup.py` 的
  `parse_markdown_table` 收敛到 `_shared` 版（处理反引号内 `\|` 转义）；
  `check_translation.py` 4 个手写解析器经实证对比**全部保留**（key 形态/消费方/
  门禁语义均有真实差异，收敛会改校验语义，先例禁止）。
- **A4/M8 `context_lock check` 委托 `term_enforcer.enforce_terms`**：删裸子串匹配
  重复实现，继承 cjk_suppress/词边界/方向感知，"希里 inside 冒牌希里"假阳性在此
  路径修复；M5 降级 warnings 也计 violation。
- **A5/M10 `diff_review` full-checker 恒空修复**：改走 check_translation `--json`
  envelope 解析（不再按行首 `-` 解析人类输出），崩溃/脚本缺失 fail-closed。
- **A6/H4 `format_skeleton restore` 回退报警**：chunk 耗尽/表格列数不符时统计回退
  次数，>0 则 stderr 警告 + JSON `fallback_count` + 非零退出，不再静默填未翻译原文。
- **A7/M4 4lang 解析失败补 stderr WARN**：与 `_load_effect_text` 对齐，卡名锁定
  静默失效（hollow lock）不再无提示。
- **A8/M6 prepare 方向自动检测**：`translate.py prepare` 省略 `--direction` 时用
  `source_is_chinese` 从源文判断（旧硬默认 encn 会把中文源的 pack 做成 EN→CN）；
  JSON/人类输出标注 auto-detected。pre 方向无关（context_lock build 用同一启发式），
  无参数可传。
- **A9/M12 CN 提取去正则化**：`get_all_for_text_cn` 的 `re.finditer(re.escape(...))`
  改 `str.find` 循环（语义逐位等价）。基准（54,942 字符中文文本，median of 3）：
  修前 1.149s → 修后 1.146s——性能中性，前提"re 512 编译缓存颠簸"在 Python 3.14
  上不复现（重编译仅 ~30ms，耗时在 step3 编辑距离模糊匹配）；改动价值是去不必要正则。
- **A10/M11 方向自动检测可见化**：check_translation / phase_c_check /
  completeness_guard / term_enforcer / auto_pipeline scan 的 JSON 输出统一加
  `direction_auto_detected` 布尔字段（term_enforcer 无 --direction 旗标，lock 缺
  direction 字段时为 true）；AGENTS.md/agent.json schema 文档同轮同步。
- **A11/M15 `card_meta.json` 构建脚本入库**：新增 `scripts/build_card_meta.py`
  （`--src` 本地 gwent-card-db 离线 + `--fetch` card-api 双模式、原子写、shape
  校验）；两模式产物均与已提交 card_meta.json 字节级一致。
- **A12 终审残留 3 项**：姊妹脚本缺失 fail-open → fail-closed（check_translation /
  phase_c_check 产 `[checker error]`，completeness_guard 产 status=error）；
  test_rebuild 补 phase_c H1 守卫用例与 M5 消费端传播用例（11→13）。
- **A13 杂项 L3-L8**：test_rebuild `tempfile.mktemp` 清零（TemporaryDirectory +
  try/finally）；health_check 死检查 "### Phase" 改为校验 SKILL.md 现存 Step 1/2/3
  标题、文案脆弱断言改 JSON envelope 断言；diff_review 退出码统一（有 issue 即非零）；
  `--output` 默认值锚定脚本目录（内部调用方经查证全部显式传参）；term_enforcer
  `--source` 临时锁文件 finally 清理、_shared/auto_pipeline NamedTemporaryFile 句柄
  关闭；learn.py 行内 `__import__('datetime')` 提顶部、check_translation 函数内重复
  import 提模块级、auto_pipeline "[1/3]…[3/3]" 改为 [1/6]…[6/6]。

验证：health_check 63 PASS / 0 FAIL；test_rebuild 13/13；上轮修复行为
（H1/H2/M5/M9）回归用例全过。

批A终审返工（2 Important + 4 Minor，kimi 完成 I-1/I-2/M-1 主体后撞 API
配额中断，剩余由 Claude 接手）：`completeness_guard` 非 JSON 模式补姊妹脚本
缺失守卫（residue scan 不再假 PASS）；agent.json 补 prepare 的
`direction_auto_detected` 与 restore 的 `fallback_count`；learn 的
`translated` 参数删到 CLI 层（translate.py 调用/agent.json/文档同步）；
`_t_m5_consumer_propagation` 改临时目录副本（不再瞬时污染 tracked 文件）；
build_card_meta 离线解析失败改友好错误；README 四语种 56→63 PASS。

## 2026-08-20 — 触发词收窄 + 检查器 fail-closed（H1/H2/M5/M9）

审查报告 6 项修复，核心是消除"假 PASS"与 skill 触发劫持：

- **H3 触发词收窄**：主版 `SKILL.md` frontmatter 的「英文翻译」改为「昆特牌英文翻译」；
  lite 版 7 个无限定触发词（聊天翻译 / 群消息翻译 / 短句翻译 / chat translation /
  quick translate / 翻一下这句 / 这段说什么）逐个加昆特限定或删除，普通翻译请求
  不再被劫持成昆特翻译。已安装副本（~/.claude/skills/gwent-translation-lite）同步。
- **H1 term_enforcer 崩溃 fail-closed**：`check_translation.py` 与 `phase_c_check.py`
  中 term_enforcer 非零退出且 stdout 无合法 JSON envelope（或缺 `data` 键）时，不再
  静默返回空违规列表，改为产出 `[checker error] term_enforcer crashed (exit N)` issue，
  进入报告并影响退出码。
- **H2 `--fix` 保留 TA 违规**：`check_translation.py --fix` 重跑后整体重赋值 issues 导致
  term authority 违规丢失；现 TA 违规单独收集、重跑后并回，修复后仍在输出与退出码中。
- **M5 CJK suppress 裸吞异常**：`term_enforcer.py` 的 `_build_cjk_suppress` 加载
  TermAuthority 失败时向 stderr 打 WARN（suppress 不完整、可能假阳性），不再静默 pass；
  `ta._cn_entries` 私有访问改为 `_shared.py` 新增的公开 `cn_entries` property。
- **M9 guard lock 构建失败 fail-closed**：`completeness_guard.py` 提供了 `--source` 但
  lock 构建失败时，term_authority 检查判不通过（status=error），整体 BLOCKED；未提供
  source 的 `skipped` 语义不变。lock 构建失败的 `[WARN]` 诊断改打 stderr，保持 stdout
  纯 JSON。

### 返工（终审 ⚠️ Needs fixes：2 条 Important + 回归测试）

- **R1 守卫判值不判键**：`json_output` 的错误 envelope 恒含 `"data": null`（键存在、值
  为 null），旧守卫 `"data" not in parsed` 放行后在 `None.get` 上 AttributeError。
  `check_translation.py` 与 `phase_c_check.py` 两处守卫改为
  `not isinstance(parsed, dict) or not isinstance(parsed.get("data"), dict)`，
  消息优先拼 envelope `errors` 字段（比 stderr 尾巴可读），否则取 stderr 末尾。
- **R2 M5 降级信号进数据面**：stderr WARN 在管线里被 `capture_output=True` 丢弃，损坏
  references 会把 BLOCKED 翻成假 PASS。现 `_build_cjk_suppress` 返回
  `(suppress, degraded)`，`enforce_terms` 结果带 `warnings` 进 JSON envelope；
  降级计入 term_enforcer 自身退出码与 plain 输出 `Issues:` 总数；三个调用方
  （check_translation / phase_c_check / completeness_guard）读到 `data.warnings`
  一律转成 `[checker warning] term_enforcer degraded: ...` 计issue、卡退出码。
  端到端语义：references 损坏时管线必 FAIL/带降级 issue，不得干净 PASS。
- **R3 回归用例**：`test_rebuild.py` 新增 4 条（H1 守卫含 null-envelope 分支 / H2
  `--fix` 保留 TA / M9 lock 构建失败 / M5 降级传播），总数 7→11，health_check 自动纳入。

## 2026-07-24 ~ 2026-07-30 — 补记（changelog 滞后追录）

> 7-23 之后有 20 个提交未记 changelog（审查 M13），按主题补记：

- **rebuild 系列共 8 个提交（07-24）**：19c72ae 四语种卡表 + 库拆分 + 激进英文
  提取；9b38479 中文源提取 + 方向感知 build_lock；4725c7f 双向 presence 校验 +
  CJK 假阳性修复；85a2cbb 精确违规报告 + agent 重译循环文档；7ffd995 游戏术语
  校验 + `--verbose-terms` 输出控制；4d9865f committed 合成行为测试接入
  health_check；395cfb4 收紧激进 matcher 消常见词误锁；9b9f5c6 card_names.md
  引用改指 card_overrides.md / card_names_4lang.json。
- **8db3faa** 入口任务声明：SKILL.md/AGENTS.md/lite 两文件顶部加「你现在的任务」
  块；AGENTS.md 流程从 auto_pipeline 五阶段同步到 translate.py 三步（另配 opencode
  本地斜杠命令 /gwent-translate，在 ~/.config/opencode/commands/，属仓库外配置）。
- **9a3ad9f** pack 展示完整锁表（build_pack 改读 lock 文件，卡名全量进 pack）；
  cnen 锁质量修复（口语词误锁/slang 泄漏进强制锁/中文提取改位置消费）。
- **009b319 / bf01948** README 四语种同步 translate.py 三步；clone 说明补
  install.sh 必跑（卡牌库不入库）。
- **6079319 / 501f11b** prepare 检测 4lang 卡牌库就绪（缺失 STOP 警告）→ 缺失时
  自动构建（本地 card-db 秒级，否则联网），开箱即用。
- **0ca79ce** 采纳另一台电脑实测反馈修 3 处（提取假阳性过滤、官方中文名引号
  归一化匹配、费正则排除 浪/恩）。
- **2ebb1f6 + e1255ee** sync from app：平衡调整方向判断引导（增强/削弱规则）、
  Markdown 格式保留、卡牌类型标注注入、card_meta.json 入库、37 个新领袖术语、
  The 开头卡名首词 skip 漏锁修复。
- **a80d56a** GN=黄金孽鬼像（Golden Nekker）缩写登记，避免误判 GN=Nilfgaard。
- **649a759** --- 分割线数量门禁（双向，译文少于原文则 block）。
- **3480c90** 术语变体识别引导（标点/typo/重音/简称/别称按 Term Lock Table 规范译名）。

## 2026-07-23 — CDPR 版权文本清理（effect_text.json 改 fetch-at-build + NOTICE）

公开仓库原 git 跟踪 references/effect_text.json（1366 张卡的 CDPR 官方能力文本），
属第三方版权内容分发。本轮清理（经 4 路 workflow 对抗验证：版权严格派 vs 务实派 /
影响面 / 技术方案）：

- effect_text.json 移出 git 跟踪（.gitignore + git rm --cached），改为**构建期产物**。
- scripts/build_effect_reference.py 新增 `--fetch` 在线模式（urllib stdlib，零依赖）：
  从 api.gwent.one 拉 en+cn 单语言端点，按 card_id join；保留 `--src` 本地离线模式。
  原子写（tempfile + os.replace）防崩溃半写损坏。install.sh 安装时自动跑 `--fetch`
  （失败降级，翻译不受影响）。
- health_check：effect_text.json 缺失从 FAIL 改为 INFO（构建期产物缺失非仓库损坏，
  附 build 提示）；保留文件存在时的 parse/count 检查。
- 新增 NOTICE：CDPR 归属 + GPL 边界切分（只覆盖原创代码，不覆盖 CDPR 数据）+
  unofficial 标注 + 非商业 + 数据源溯源 + 撤回风险。
- card_names.md / keywords_map.md **保留**（事实信息 + 核心运行时依赖，缺失会让
  skill 停摆），NOTICE 已声明其 CDPR 衍生属性不在 GPL 内。
- 四语种 README 目录树 effect_text.json 注释改 build-time + 加 unofficial 标注。

## 2026-06-30 — Slang 预防 + 检测（黑话"看不懂"修复）

用户痛点：英文黑话（slang/jargon）翻出来"看不懂"。预防为主、检测兜底，两者都做。
黑话词典刻意不进术语强制锁（保留硬层卡牌信息 / 软层修辞分层）。

### 预防层（pre 注入，主力）
- 新增 `references/slang_map.md`（30 条：评价俚语 / 习语比喻 / 动作机制），3 列对齐 category_map。
- `_shared.py`：`_load_slang_map` + `get_slang_for_text`（小写扫描源文黑话，多词短语 re.escape），**不调 _register**（不进强制锁）。
- `auto_pipeline.py pre`：扫源文黑话，注入 `slang_hints`（封顶 `SLANG_HINTS_CAP=15`，复用 official_effects 模式）。
- `SKILL.md` Phase A：提示 `slang_hints` 为意向译参考（hint 非硬锁）。

### 检测层（check_translation warn，兜底）
- `check_translation` 加 `source_text` 参数，返回 `(issues, warnings)`。
- 反向扫描：源文黑话（gameplay 上下文）+ 译文缺意向译 → warn（不 block）。
- `_slang_in_context` 误报控制（±20 字符窗口需含 card/deck/meta 等语境词）。
- warnings 不进 exit code（exit 只看 issues）；JSON 加 `warnings`/`warning_count`。
- 调用方适配：`phase_c_check.py:110` 解包；subprocess 调用方零改。

## 2026-06-24 — Card-info Enforcement (categories / attributes / effects)

用户原则：**所有卡牌信息（名称/词条/效果/阵营/边框/稀有度/类别）必须强制用既定译法**；
修辞/语气走引导。审计发现硬层有漏，本轮补齐。

### Phase 1 — 类别（category_map 之前是孤儿，relict→遗物 的根因）
- `scripts/_shared.py`：新增 `_load_category_map()`，按现有 loader 约定解析三张表，
  `—`/空 CN 跳过、通用词黑名单 SKIP_CATEGORY 跳过，注册 Gwent 专属类别
  （relict/insectoid/construct/...）。
- 新增 **小写类别词扫描**（仿已有的歧义名扫描）：类别词在散文里通常小写
  （"GN relicts"），大写短语提取器抓不到；扫描后 relict 等才会被锁定+强制
  （译文写"遗物"触发 term_missing_or_literal → completeness_guard 拦截）。

### Phase 2 — 卡牌属性（稀有度 + 阵营缺口）
- 新增 `references/card_attributes_map.md`：稀有度（common/rare/epic/legendary↔普通/稀有/史诗/传奇）、
  阵营全名+缩写（补 Neutral/中立、缩写 NR/MO/SK/ST/NE，原先只有 NG/SY 偶然漏入）。
- `scripts/_shared.py`：新增 `_load_card_attributes_map()`；阵营缩写经 _add_abbrev 注册后
  被 extract_abbreviations 锁定强制；非通用阵营全名（Nilfgaard/Skellige/...）加小写扫描，
  通用 Monsters/Neutral 走缩写 MO/NE 避免误伤。
- 边框颜色 gold/bronze 已在 keywords_map 强制（文件里注明），silver 随版本移除。

### Phase 3 — 官方效果文本（注入 + 自检；term-lock 不适合长句）
- 新增 `scripts/build_effect_reference.py`：从 `~/gwent-card-db/tables/cards_{en,cn}.json`
  生成 `references/effect_text.json`（1366 卡，EN+CN 官方 ability，0 NULL）。
- `scripts/_shared.py`：新增 `_load_effect_text()` + `get_official_ability(en)`。
- `scripts/auto_pipeline.py` pre：新增 OFFICIAL EFFECT TEXT 表 + JSON 字段 official_effects，
  把源文出现的卡的官方 CN 效果注入给 agent 逐字照抄（长句强制的实际手段）。
- 新增 `scripts/effect_verifier.py`：**信息性**自检（官方效果是否在译文逐字出现），
  不进 block 门（效果缺席可能只是没引用）。
- `references/phase_c_checklist.md`：加 manual 自检 encn-12 / cnen-10（引用效果与官方一致）。

### 验证
health_check 通过；encn 回归 issue_count=7 不变；relict→遗物 端到端被拦、残物通过；
阵营缩写/全名强制生效；pre 注入官方效果；effect_verifier 信息性输出。

## 2026-06-24 — Figurative Language & Tone Judgment

### Added
- `references/style_reference.md`: new section 《修辞与语气判断》 — rules + a
  real-example table for metaphor / hyperbole / sarcasm / mockery
  (译意图不译字面，保留"咬人味"). Grounded in an actual BC33 Reddit translation
  (on steroids / loud design / sweet spot / guess what / sink / toxic /
  dismissive tone).
- `SKILL.md` Phase B: added a "Rhetoric" row to both the EN→CN and CN→EN tables.
- `references/phase_c_checklist.md`: added manual checks encn-11 / cnen-09
  (figurative intent preserved, irony not flattened).

### Why
Translation notes from real BC content showed figurative / sarcastic lines were
handled inconsistently — some kept the bite (沉底 / 你猜怎么着), others got flattened
(sweet spot → 该去的位置) or translated too literally (loud design → 太大声). The
skill steered the overall tone but never told the agent to judge rhetoric on a
per-sentence basis.

## 2026-06-03 — Server Verification & Restructure

### Structural Changes
- Reorganized from flat files to `references/` subdirectory
- Eliminated redundancy between SKILL.md and reference files
- Added `keywords_map.md` (game keyword translations from server data)
- Added `card_names.md` with server-verified mappings
- Added `changelog.md` (this file)

### Corrections (from server card_data.json verification)
- `沙暴` → `沙尘暴` [202205]
- `伊魅柯` → `伊魅珂` [202370]
- `埃斯特·图尔赛赫` → `埃斯特·图尔赛克` [202883]
- `咯咯哒 艾伯伦特` → `"咯咯哒"艾伯伦特` (quote format)
- `布洛妮` → `布蕾恩` [142209]
- `雷吉斯的鸣镝动怒` → `雷吉斯：血欲化身` [202195] (原映射错误: 鸣镝动怒是领袖名)
- `怀柔` → `战术决策` [200164] (原映射错误: 怀柔是怀柔兼济的简称)
- `夜宴` → `女巫夜宴` [203054]

### Fixes to Incorrect Mappings
- `Tactical Decision` was incorrectly mapped to `怀柔`; corrected to `战术决策`
- `Regis: Bloodlust` was incorrectly mapped to `雷吉斯的鸣镝动怒`; corrected to `雷吉斯：血欲化身`
- Added note: "蟹蜘蛛" is community slang for deck/leader, not a single card

### Added
- 42 verified leader names
- 50+ game keywords with frequencies from server data
- Faction full names (English + Chinese)
- Self-check checklist in SKILL.md workflow

## 2026-06-03 — Supplemental References & Auto-Detection

### New Reference Files
- `ambiguous_names.md` — 40+ cards with multiple versions (e.g., 杰洛特 x6, 雷吉斯 x4, 特莉丝 x4)
- `competitive_terms.md` — 150+ competitive/community terms, including blog glossary data (16 terms from https://cngwentbd.top/glossary/)
- `common_pitfalls.md` — 7 categories of systematic errors with severity levels
- `category_map.md` — 60+ card category translations (人类, 猎魔人, 吸血鬼, 构造体, etc.)

### Script Enhancements (check_translation.py)
- Auto-detects ambiguous card names (flags "杰洛特" without subtitle)
- Auto-detects abbreviations (BC, OP, CA, etc.) and suggests expansion
- Auto-detects English parentheses and English colons
- Auto-detects Chinese numerals
- Rules loaded dynamically from references/ (no hardcoded duplication)
- Fixed word-boundary regex for CJK+Latin mixed text

## 2026-06-03 — Self-Evolution (Learn Mode)

### New: Learning System
- `scripts/learn.py` — Scans source+translated text to discover unknown terms
  - Detects card names with colons, capitalized phrases, all-caps abbreviations
  - Compares against all reference files to find gaps
  - Outputs preview or auto-writes to pending_terms.md
- `references/pending_terms.md` — Buffer for unverified terms
  - Human-reviewed before moving to confirmed references
  - Prevents pollution of verified data with uncertain translations
- SKILL.md Step 7: Learn — Post-translation self-evolution workflow
  - Scan → Compare → Record → Suggest
  - Never writes directly to confirmed files without human verification

### Self-Evolution Design
```
Translation ──► Detect Unknown Terms ──► pending_terms.md
                                            │
                         Human Review ◄─────┘
                                            │
                         Confirmed ──► terminology_map.md / card_names.md
```

## 2026-06-03 — Advanced Features (6 New Capabilities)

### 1. Version-Aware Translation (版本感知)
- `references/version_map.md` — Expansion timeline with card ID prefixes
- Date-based lookup rules for pre-2020 / 2020-2021 / post-2021 articles
- Resolves ambiguous card names by article date (e.g., Regis base vs. Regis: Rebirth)

### 2. Context Lock (上下文一致性锁)
- `scripts/context_lock.py` — Per-document terminology lock table
- Build lock from source → Lock translations → Enforce consistency across article
- Prevents "蟹蜘蛛" in paragraph 3 and "蛛群" in paragraph 15

### 3. Format Skeleton Preservation (格式骨架保留)
- `scripts/format_skeleton.py` — Extract/restore Markdown structure
- Preserves headings, lists, blockquotes, tables while translating content only
- Separates format from content for clean translation workflow

### 4. Diff Review Mode (审校差异模式)
- `scripts/diff_review.py` — Structured comparison of source vs. user translation
- Detects: terminology errors, numeric mismatches, omissions, additions
- Output grouped by severity (high/medium/low) with specific fix suggestions
- Does NOT retranslate—only analyzes and reports issues

### 5. Back-Translation Validation (回译验证)
- `scripts/backtranslate.py` — Framework for semantic drift detection
- Compares original English with back-translated English from Chinese output
- Flags: missing key information, wrong numbers, reversed causality
- Requires LLM for actual back-translation step

### 6. Style Fingerprint (个性化风格指纹)
- `references/style_fingerprint.md` — User's personal translation preferences
- Records term choice distribution (e.g., nerf → 削弱 80% / 来一刀 20%)
- Tracks preferred oral verbs, sentence split ratio, formatting choices
- Updated after each user correction session

### SKILL.md Workflow Restructure
- Added Step 0: Context Setup (date, type, style fingerprint)
- Added Step 2: Context Lock (for long articles)
- Added Step 3: Format Skeleton (for formatted articles)
- Renumbered subsequent steps
- Added "Special Modes" section for Diff Review and Back-Translation

## 2026-06-03 — Workflow Tools (3 New Scripts)

### 1. lookup.py — Terminology Quick Search
- One-command search across all 13 reference files
- Exact match + fuzzy matching support
- Groups results by source file with formatted output
- Usage: `python scripts/lookup.py "部署"`

### 2. translate.py — Workflow Orchestrator
- Chains all 6 workflow steps into a single command
- Auto-detects article context (date → version range)
- Outputs step-by-step translation guide with next actions
- Supports `--check-only` mode for post-translation verification
- Usage: `python scripts/translate.py article.md --date 2026-05`

### 3. health_check.py — Skill Health Check
- Verifies all 13 reference files and 7 scripts are present
- Checks SKILL.md structure and required sections
- Tests script syntax and basic functionality
- Data integrity checks (card count, pending terms, version history)
- Outputs color-coded PASS/FAIL/WARN/INFO summary
- Usage: `python scripts/health_check.py`

## 2026-06-03 — Bidirectional Translation Support

### CN → EN Translation
- `references/reverse_terminology_map.md` — Reverse term lookup (中文 → 英文)
- Covers: core terms, number formulas, slang reverse mappings, oral verbs
- Style notes for preserving Bilibili tone in natural English

### Updated Components
- SKILL.md: Split workflow into EN→CN and CN→EN variants
- Added direction-specific reference loading instructions
- Added CN→EN self-check checklist
- lookup.py: Searches both terminology_map.md and reverse_terminology_map.md
- health_check.py: Verifies reverse_terminology_map.md exists

## 2026-05-30 — Initial Release

### Based On
- 4 rounds of manual correction by 进
- Triangulation: program translation vs manual correction vs source
- Shinmiri-Lerio three-way comparison

### Key Rules Established
- provision → 人口 (formal), "5P"/"4费" (casual)
- "X for Y" → "Y人口X战力" format
- Active voice mandate
- Community slang standardization (气宗, 孽鬼店店, 互口岛, etc.)
