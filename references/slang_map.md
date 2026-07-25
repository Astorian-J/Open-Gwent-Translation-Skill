# Slang & Jargon Map (黑话映射)

Community balance/podcast slang that reads as gibberish if translated literally.
Each row: English slang → intended CN register (slash-separated alternatives) | literal-forbidden (never translate this way) | note.

Used by `auto_pipeline.py pre` (`slang_hints` injection) and `check_translation.py`
(reverse-scan warn). **Not a term-lock** — slang is register guidance, not hard
enforcement. Loaded into `TermAuthority._slang` (kept out of the enforced lock on purpose).

## Evaluative Slang (评价俚语)

| english | intended_cn | literal_forbidden | note |
|---|---|---|---|
| broken | 强到离谱 | 破碎的 | strength imbalance, not damaged |
| tier 0 | T0/独一档 | 零级 | top meta tier |
| unplayable | 没法玩/废卡 | 不可游玩 | synonym: 废卡 (hard-locked) |
| auto-win | 躺赢/保赢 | 自动胜利 | guaranteed win |
| free win | 白送的局/白嫖一局 | 免费赢 | easy win |
| carry | 扛局面/带飞 | 携带 | one card carries the deck |
| cancer | 毒瘤 | 癌症 | oppressive, keep the bite |
| copium | 自我安慰/自欺欺人 | 止痛药 | unrealistic optimism meme |
| sweaty | 卷王/功利 | 出汗的 | tryhard |

## Idioms & Metaphors (习语/比喻)

| english | intended_cn | literal_forbidden | note |
|---|---|---|---|
| on steroids | 加强版/打了鸡血版 | 类固醇 | hyperbole; 后者用于幽默场合 |
| sweet spot | 甜点位/最佳点 | 甜的位置 | ideal balance point |
| loud | 存在感太强/喧宾夺主 | 大声的 | dominant design presence |
| braindead | 无脑 | 脑死亡 | mindless, keep derogatory |
| glass cannon | 玻璃大炮/高伤脆皮 | 玻璃加农炮 | high impact, low survivability |
| back on the menu | 又能上场了/重新上桌 | 回到菜单 | viable again |
| drawing dead | 抽了也是白抽/死抽 | 抽到死 | poker term, no outs left |
| the nuts | 天胡/顶级 | 坚果 | poker term, best possible |
| nerf sponge | 削弱沙包/被反复削 | 削弱海绵 | repeatedly nerfed |
| point stick | 纯堆分卡/数值挂件 | 点数棍 | raw stats, no function |
| goldfish | 自闭测试/空过测速 | 金鱼 | solo speed test ignoring opponent |

## Action / Mechanic Slang (动作/机制黑话)

Note: `brick` / `mulligan` / `bleed` / `tutor` etc. are already hard-locked in
competitive_terms.md / terminology_map.md and intentionally omitted here to keep
the hard-layer (enforced) / soft-layer (register hint) split clean.

| english | intended_cn | literal_forbidden | note |
|---|---|---|---|
| point slam | 砸分/裸堆战力 | 点数重击 | raw points play |
| win condition | 制胜条件/赢牌核心 | 胜利条件 | often abbreviated wincon |
