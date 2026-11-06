---
name: rsi-wechat-publisher
aliases:
  - 公众号流水线
  - 微信公众号内容管线
  - rsi内容管线
  - 公众号AI写作
description: RSI 自进化微信公众号内容流水线（KK 个人版 v3.0）。半自动：从得到大脑当天真实笔记筛选题（两层筛 → AI 推 3 个候选 → **人选定并给触动点**）→ writer 写作 → qa 质检 → format 排版配图 → 推草稿箱 → 归档 → 同步 IMA → 复盘。选题只从本人真实笔记来，不从网上文章来；默认每天 1 篇，全部进草稿箱由人工选择群发（绝不自动群发）。每轮回写 RSI 进化台账（笔记避重/风格偏好/金句库），越用越聪明。Use when user mentions "发公众号", "公众号文章", "内容流水线", "rsi-wechat", "跑流水线", "选题", "从笔记找选题", "文章归档", "整理知识库".
version: 3.0.0
platforms: [darwin, linux, win32]
prerequisites:
  commands: [git, python3]
  optional_connectors: [ima-mcp]
---

# RSI 公众号内容流水线（rsi-wechat-publisher）

> **一句话**：把你自己的真实笔记变成公众号文章——AI 从得到大脑当天的记录里筛出 3 个候选，你选一个、说出真正触动你的那个点，再往下写。
> 本技能由杨辉老师的 rsi-wechat（OpenClaw 版）移植为 WorkBuddy 通用版。**v3.0 起选题源改为得到大脑，选题处必须停下等人确认**——这一步是全流程唯一的人工闸门，跳过去就退回「AI 生成」。

## 语言

跟随用户语言（默认中文）。

## ⚡ 首次使用：5 分钟配置（必须完成，否则流水线降级）

**第一步：准备两个凭证**

| 凭证 | 哪里拿 | 放哪里 | 没配会怎样 |
|------|--------|--------|-----------|
| ① IMA 开放 API | ima.qq.com → 设置 → 开放 API（或 ima.qq.com/openapi 入口）创建，得 `Client ID` + `API Key` | `~/.config/ima/client_id` 和 `~/.config/ima/api_key`（每文件一行纯文本） | 素材采集/文章回存 IMA 跳过，只能靠热点写 |
| ② 微信公众号 API | mp.weixin.qq.com → 设置与开发 → 基本配置：拿 `AppID` + `AppSecret`；**并把本机出口 IP 加入「IP 白名单」**（跑 `python3 scripts/diagnose.py` 可查出本机 IP） | `~/.config/wechat/appid` 和 `~/.config/wechat/secret` | 文章打包成本地 HTML（手动粘贴发布） |

```bash
mkdir -p ~/.config/ima ~/.config/wechat
echo -n '你的IMA_ClientID' > ~/.config/ima/client_id
echo -n '你的IMA_APIKey'    > ~/.config/ima/api_key
echo -n '你的公众号AppID'   > ~/.config/wechat/appid
echo -n '你的公众号Secret'  > ~/.config/wechat/secret
chmod 600 ~/.config/ima/* ~/.config/wechat/*
```

**第二步：运行配置向导**

对 WorkBuddy 说「**配置公众号流水线**」，或手动跑：

```bash
python3 scripts/setup_wizard.py
```

向导会：探测两个凭证 → 用你的 IMA 凭证列出你的知识库让你选 → 把选择写进 `config.json` → 实测公众号 token（IP 白名单不通过会告诉你加哪个 IP）→ 生成专属 `_rsi_ledger.md` 台账。

**第三步（可选但推荐）**：
- 配 WorkBuddy 的 **ima-mcp 连接器**（设置→连接器里添加 ima）：topic 选题环节搜索素材更顺。
- 准备**企微获客二维码**放 `config/wecom-qr.png`（文末 CTA 用；没有就用文字兜底「微信搜索：你的号名」，同时改 `config.json` 的 `wechat_account_name`）。
- 建每日定时：对 WorkBuddy 说「**给公众号流水线建每天 07:20 的定时任务**」。

## 配置文件（config.json，向导生成，可手改）

```json
{
  "ima_kb_id": "",            // 你的 IMA 知识库 ID（向导填）
  "ima_kb_name": "",          // 知识库名（台账/简报显示用）
  "ima_folder_articles": "",  // 成稿回存的文件夹 ID（空=知识库根目录；可后续 create_folder 建了再填）
  "author_name": "杨教练",     // 改成你的笔名
  "wechat_account_name": "AI量化杨教练",  // 无二维码时的文字 CTA 兜底
  "articles_per_day": 3,      // 每天几篇（1-3）
  "theme": "default",         // default=深蓝 / blue=亮蓝
  "persona": {                // 你的内容定位——越具体选题越准
    "positioning": "AI量化投资教练，帮投资者用系统战胜情绪",
    "target_readers": "30-55岁投资者、高净值人群、二代传承场景",
    "tone": "专业但不说教，像资深教练做一对一复盘，第二人称"
  },
  "topic_domains": ["量化投资", "AI与投资", "财富认知", "投资者行为"],
  "hotspot_queries": ["今日AI人工智能财经热点", "36氪 AI 快讯"]
}
```

**换知识库/改人设/改定位：改 config.json 即可，不动技能其他文件。**

## Workflow Router（本文件是入口，只做路由）

| 任务意图 | 路由到 |
|---------|--------|
| 首次配置 / 换配置 | `scripts/setup_wizard.py`（说「配置公众号流水线」） |
| 跑完整流水线 / 每天一篇 | `references/pipeline.md`（编排手册，**执行前必读**） |
| 出选题 / 从笔记里挑题 | `references/pipeline.md § Step 1` + `agent-prompts.md § topic` |
| 只做对标拆解（默认关闭，手动开） | `references/pipeline.md § Step 0.6` + `agent-prompts.md § benchmark` |
| writer/qa/format/benchmark 提示词模板 | `references/agent-prompts.md`（**所有 {{占位符}} 从 config.json 取**） |
| 只做素材查证 / 整理知识库 | pipeline.md § Step 0.7 |
| **查于困困某一讲的方法** | **`references/course-index.md`（36 讲路径 + 按用途反查）** |
| **审稿 / 挑毛病（七维度）** | **`references/yukunkun-7d-checklist.md`（第 26 讲提炼版，不用回原文）** |
| 诊断（IP/凭证/连通性） | `python3 scripts/diagnose.py` |
| 换企微二维码 | 直接覆盖 `config/wecom-qr.png`（文末 CTA 自动用新图） |
| 版本/口径漂移排查 | `bash scripts/check_drift.sh` |

**路由纪律**：改流程改 references/scripts，不动本文件；个人配置只放 config.json。

## 流水线概览（v3.0）

```
Step0 预热(读台账+断点续跑) → [0.5 热点 / 0.6 对标：默认关闭]
  → Step1 选题：拉得到大脑近2天笔记 → 两层筛 → 出3个候选 → ★停，等人选定并给触动点★
  → Step1.5 物料清单+事实台账(00_sources.md)：把「还要你补什么」跟选题一起问，回收后才许动笔
  → Step2 writer(围绕 user_trigger 写 2200-2600 字，先选骨架，场景≥3，只许从台账取料)
  → Step2.5 voice_lint 门禁(禁词+引语溯源+技术黑话)，exit 1 不进质检
  → Step3 qa(十维质检 ≥85 过，先查可替换性，再数场景，再对台账)
  → Step4 format(封面配图+排版+CTA)
  → Step4.5 render_check 门禁(转义/正文图/CTA/长度)，exit 1 不许推草稿箱
  → Step4.6 推草稿箱 → Step5 archive(本地git归档)
  → Step6 sync-ima(成稿回存) → Step7 复盘(回写台账+日报)
```

- topic/writer/qa/format/benchmark 由主控用 **Agent 工具** spawn 子代理执行（提示词模板已备好）；**Step 1 由主控自己做**，因为要跟人来回确认。
- **Step 1 和 Step 1.5 是两个人工闸门**：出完 3 个候选必须停，禁止自动 spawn writer。用户三种回法（选某个+触动点 / 3 个都不合适给自己的题 / 选某个改角度）都要把他原话写进 `01_topics.md` 的 `user_trigger`。
- **Step 0.5 热点 / 0.6 对标默认关闭**（`hotspot_enabled` / `benchmark_enabled` = false）。热点和对标爆款都属于「从爆款出发」，会把内容拉回同赛道均值。
- 产物：`<项目根>/pipeline/<日期>/p1|p2|p3/`；归档：`articles/<日期>[-n]/`。

## 安全红线（不可违反）

1. **只进草稿箱，绝不自动群发**——post_draft.py 物理上无群发能力。
2. 投资/财经内容必含风险提示；无收益承诺、无绝对化用语、无无源数据（qa 一票否决）。
3. IMA 写操作必带 folder_id（防落根目录）；凭证只放 `~/.config/`，绝不进提示词/不提交 git。
4. Truth-first：素材不足允许减产留痕，绝不凑数发空心文。
5. **选题必须停**（v3.0）：Step 1 出完 3 个候选必须等用户回「选哪个 + 触动点」，不许自动往下写。

## 故障速查

| 症状 | 原因 | 解法 |
|------|------|------|
| token 报 40164 | 本机 IP 不在公众号白名单 | 跑 `scripts/diagnose.py` 拿 IP → 公众号后台加白 |
| IMA API 403/无响应 | 代理干扰或域名变化 | 脚本已内置绕过代理；仍失败跑 diagnose.py |
| 文章进了 local-package | 公众号凭证缺失或 API 失败 | 按包内 README 手动发，或修好凭证重跑 |
| COS 上传 SignatureDoesNotMatch | 签名格式 | 已修复版本勿改 cos_put 函数 |

## 目录结构

```
rsi-wechat-publisher/
├── SKILL.md                 # 本文件
├── SETUP.md                 # 图文配置指南（给非技术用户）
├── config.json              # 你的个人配置（向导生成）
├── _rsi_ledger.md           # RSI 进化台账（向导生成空白版）
├── config/                  # wecom-qr.png（可选二维码）
├── references/
│   ├── pipeline.md          # 九步编排手册（主控必读）
│   ├── agent-prompts.md     # 四个子代理提示词模板
│   ├── ima-api-mechanics.md # IMA API 实测速查（踩坑记录）
│   └── qa-rubric.json       # 质检规则引擎（十维+六否决）
├── templates/               # 产物模板（00_sources 事实台账 / 00_benchmark 对标拆解 / 01-04 各步产物）+ CTA 组件
└── scripts/                 # 全部脚本（详见各文件头注释）
    ├── setup_wizard.py      # 配置向导（首次必跑）
    ├── diagnose.py          # 一键诊断
    ├── voice_lint.py        # 口吻+引语溯源+技术黑话 三重体检（门禁）
    ├── render_check.py      # 排版成品体检（format 后门禁）
    ├── md_to_html.py        # 微信内联样式转换
    ├── post_draft.py        # 草稿箱推送（无群发能力）
    ├── sync_to_ima_wb.py    # 成稿回存 IMA（含COS签名）
    ├── archive_article.sh   # git 归档
    ├── compress_image.sh    # sips/cwebp 图片压缩
    ├── fetch_stats.sh       # 发布数据回流（手工表为主，接口 48001 无权限）
    └── check_drift.sh       # 防漂移自检
```
