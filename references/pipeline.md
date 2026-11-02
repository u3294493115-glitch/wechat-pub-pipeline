# 九步流水线详细编排（rsi-wechat-publisher v1.0.0，主控必读）

> 主控（WorkBuddy 会话）的动作手册。所有个人参数从 `config.json` 读取，禁止硬编码。

## 核心纪律（先读）

1. **执行前先读 config.json**：作者名/知识库 ID/每日篇数/persona 全部从配置取，拼进子代理提示词。
2. **产物目录**：`<项目根>/pipeline/<YYYY-MM-DD>/p1|p2|p3/`（项目根 = 当前工作区）。
3. **磁盘为准**：子代理返回后必须 Read 验证产物文件存在；缺 → 携失败原因补 spawn 一次。
4. **断点续跑**：启动先看近 2 天 `_status.json`，`finished!=true` 则缺哪步补哪步，禁止覆盖已验证产物。
5. **Truth-first**：素材不足允许减产（3→2→1→0），台账留痕，绝不凑数。
6. **绝不群发**：post_draft.py 只进草稿箱；本地降级包也只是让人工手动发。
7. 凭证只在 `~/.config/`，绝不写进提示词、台账或 git 提交内容。

## 编排总览

```
主控
 ├── Step 0  预热：date 实测 → 断点盘点 → 建目录 → 读 config.json + _rsi_ledger.md 提炼硬约束
 ├── Step 0.5 热点采集：WebSearch（config.hotspot_queries）→ 热点候选池
 ├── Step 0.6 对标拆解（config.benchmark_enabled）：搜同赛道爆款 → 只拆骨架 → _benchmark.md
 ├── Step 0.7 素材运营（可选，IMA 凭证在时）：搜库摸底 + 热点精品入库
 ├── Step 1  spawn topic ×N（并行）→ 各篇 01_topics.md
 ├── Step 2  spawn writer ×N（并行）→ 各篇 02_drafts.json
 ├── Step 3  spawn qa ×N → 03_qa_scores.md（<85 打回 writer，同篇 ≤2 次）
 ├── Step 4  spawn format ×N → 封面/插图 + article.html + CTA + post_draft.py 推草稿箱 → 04_publish_queue.md + format/manifest.json
 ├── Step 5  archive：bash scripts/archive_article.sh <日期> <产物目录>
 ├── Step 6  sync-ima：python3 scripts/sync_to_ima_wb.py <articles目录> <日期>
 └── Step 7  复盘：回写台账 + check_drift + _status.json finished:true + 日报简报
```

子代理提示词模板：`references/agent-prompts.md`（填充后 spawn，subagent_type=general-purpose）。

## Step 0 预热

1. `date '+%Y-%m-%d %H:%M %Z'` 实测日期。
2. 断点盘点近 2 天。
3. `mkdir -p pipeline/<日期>/p{1..N}`。
4. 读 config.json：拿到 kb_id、author、persona、articles_per_day。
5. 读 `_rsi_ledger.md` 提炼：素材避重（7 天内/累计≥2 次）、风格偏好结论、金句库、硬约束修正。
6. IMA/公众号凭证探测：`python3 scripts/diagnose.py --check` 可选；缺 IMA → Step 0.7/6 跳过；缺公众号 → format 降级本地包（简报标注）。

## Step 0.5 热点采集（WebSearch）

跑 config.hotspot_queries 的 2-3 条查询 → 挑 5-10 条形成候选池（标题+一句摘要）。热点仅作钩子，主体观点必须来自知识库。失败不阻断（纯库存选题）。

## Step 0.6 对标拆解（`benchmark_enabled=true` 时）

**目的**：给选题一个「结构参考」——看同赛道最近什么写法被市场验证过，别闭门造车。

1. **搜索**：跑 `config.benchmark_queries` 的搜索词；`config.benchmark_accounts` 非空时优先按号找。从中挑 `benchmark_top_n` 篇（默认 3）**同赛道、近期、明显爆过**的：阅读量/点赞/转发显著高于同类，或搜索排序靠前。
2. **拆解**：spawn benchmark 子代理（提示词见 `agent-prompts.md § benchmark`）→ 产出 `pipeline/<日期>/_benchmark.md`。
3. **传递**：Step 1 的 topic 提示词注入 `{{BENCHMARK_SKELETONS}}`（骨架结论），**只作结构参考**。

**三条红线**：

- **只拆骨架**（钩子类型 / 段落结构 / 节奏 / 受众 / 爆点），**禁止摘录原句、禁止复制段落**——对标文章的原句一个字都不许进任何产物文件。
- 骨架只影响「怎么排列」，不影响「说什么」：正文观点与论据仍必须全部来自 IMA 素材库。
- 搜不到合适爆款不阻断，写「本轮无对标」留痕，按原流程走。

## Step 0.7 素材运营（IMA 凭证在时）

 ima-mcp 可用则用 MCP 工具（get_knowledge_list / import_urls）；否则跳过（不强求）。目的：摸清库内素材结构，供 topic 参考；可选把 1-3 条当日相关热点文章 import_urls 入库（folder_id 必填）。

 **素材范围**：以 `config.json` 的 `ima_source_folder`（`{{ima_source_folder_name}}`）及其子文件夹为准，不扩到库根目录其他文件夹。该范围素材不足则 truth-first 减产，不凑数。

## Step 1-3（子代理执行，提示词见 agent-prompts.md）

- qa 规则：`references/qa-rubric.json`（七维加权 + 四条一票否决：compliance / content_hollow / source_dup / unsourced_claim）。
- 打回流程：qa REVISE → 携修改建议补 spawn writer（改 02_drafts.json 原地覆盖）→ qa 复检（追加到 03_qa_scores.md）；同篇 ≤2 次，仍不过换选题（回到 topic，单篇处理）。

## Step 4 format（子代理执行）

动作序列（提示词已内置，主控验收以下产物）：
1. `format/article.md`（微调后正文，[配图：…] 占位**必须全部替换为真实图片**——ImageGen 生成或删除占位段，禁止把占位框留在终稿）
2. `format/imgs/cover.png`（ImageGen 2.35:1；不可用 PIL 兜底）→ `bash scripts/compress_image.sh <cover> --max-kb 500`
3. `format/article.html`：`python3 scripts/md_to_html.py article.md article.html --title <标题> --theme <config.theme>`
4. CTA 注入（`templates/format/cta.md`）：有 `config/wecom-qr.png` 用图；没有用文字「微信搜索：`config.wechat_account_name`」
5. 推草稿箱：`python3 scripts/post_draft.py article.html --cover <cover绝对路径> --title <标题> --digest <摘要> --author <config.author_name>`
6. `04_publish_queue.md` + **标准结构** `format/manifest.json`：

```json
{"date": "<日期>", "articles": [{"title": "...", "article": "article.md", "html": "article.html", "cover": "imgs/cover.png", "media_id": "...", "qa_score": 88}]}
```

⚠️ manifest 的 article/html/cover 字段**相对 manifest 所在目录**（不要再带 `format/` 前缀）。

## Step 5 归档

`bash scripts/archive_article.sh <日期> <pipeline/日期目录>`——读 manifest → 写 `articles/<日期>[-n]/`（article.md + article.html + cover + meta.json）→ git commit（SKILL 目录内自动 init；配了 remote 自动 push，3 次重试）。

## Step 6 同步回 IMA

`python3 scripts/sync_to_ima_wb.py <技能目录>/articles <日期>`——读 config.json 的 kb_id/folder，create_media → COS（sha1 签名含 host，绕过代理）→ add_knowledge。失败不阻断。

## Step 7 复盘（不可跳过）

1. 回写 `_rsi_ledger.md`：素材避重 +1 行/源；风格偏好（标题模式+质检分）；金句候选；RSI 回路快照（本轮强在哪/下轮重点）。
2. `bash scripts/check_drift.sh` FAIL 当场修。
3. 写 `_status.json`：`finished:true` + stages + media_id 列表。
4. 向用户发日报（固定字段）：

```
【RSI 流水线日报 <日期>】
1. 产出：计划 N / 实际 M（M<N 给减产原因）
2. 选题与质检：各篇标题、角度、QA 分、过审/打回
3. 待发布清单：media_id（或 local-only 包路径）
4. 归档状态：git commit；IMA 同步数
5. 素材动态：新增源 / 复用源 / 热点使用
6. 人工修正 diff：无（首轮）/ 摘要
7. 漂移自检：PASS/FAIL
8. 发布数据：暂无（群发后次日可跑 fetch_stats.sh）
```

## 定时任务

用户说「建定时」时用 automation_update：scheduleType=recurring，`FREQ=DAILY;BYHOUR=7;BYMINUTE=20`（用户可改点），prompt 复述：加载本技能 → 读 pipeline.md 执行当日九步 → 断点续跑 → 红线（绝不群发/truth-first/风险提示）→ 日报。prompt 必须自包含技能绝对路径。
