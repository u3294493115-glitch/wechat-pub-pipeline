# 公众号内容流水线（WorkBuddy Skill）

> 从自己的 IMA 知识库挖素材，自动产出公众号长文进草稿箱。人只管审和发。

## 这是什么

一个 WorkBuddy 技能：把写公众号这件事拆成几个角色流水作业——

**采热点 → 拆爆款骨架 → 选题 → 写作 → 质检 → 排版推送 → 归档 → 回存知识库**

每个角色只管自己那一段，干完把结果写成文件交给下一个。写出来的东西全部进公众号**草稿箱**，永远不会自动群发。

> 本项目基于 [kenyanghui/wechat-pub-workbuddy](https://github.com/kenyanghui/wechat-pub-workbuddy) 改造而来，原作者以 MIT 协议开源。原版方法论与质检规则引擎来自 [kenyanghui/rsi-wechat-pub](https://github.com/kenyanghui/rsi-wechat-pub)。

## 相对原版改了什么

| 改动 | 说明 |
|------|------|
| **新增 Step 0.6 对标拆解** | 原版只搜新闻、不看同行。现在先用搜索词找同赛道爆款，**只拆骨架**（钩子类型/段落结构/节奏/受众/爆点），注入选题作结构参考。硬红线：禁止摘录原句，骨架不许夹带对标观点。 |
| **素材范围锁定** | 限定只从指定文件夹取素材，不扩到整个知识库，防止跑题与幻觉。 |
| **配置与台账外置** | `config.json`、`_rsi_ledger.md` 不进版本库；提供 `config.example.json`、`_rsi_ledger.template.md` 供参考。 |
| **Windows 适配** | 修掉归档脚本的路径写法问题，可直接在 Windows 上跑。 |

## 十步流程

```
Step 0   预热：读配置 + 读台账（提炼上轮硬约束）+ 断点续跑
Step 0.5 热点采集：按配置的搜索词抓当天新闻，只当由头
Step 0.6 对标拆解：找同赛道爆款，只拆骨架 → _benchmark.md
Step 0.7 素材运营：摸清知识库结构，可选把热点好文入库
Step 1   选题：读素材 + 热点 + 骨架 → 写施工图（论点/结构/口气/出处）
Step 1.5 物料清单 + 事实台账：把「还要你补什么」跟选题一起问，回收后建 00_sources.md
Step 2   写作：照施工图写 2200-2600 字初稿（只许从台账取料）
Step 2.5 体检门禁：禁词 + 引语溯源 + 技术黑话，exit 1 不进质检
Step 3   质检：十维加权打分，85 分及格，六条红线一票否决，不过退回重写
Step 4   排版：配封面图、转公众号样式、注入文末引导、推草稿箱
Step 5   归档：本地 git 归档
Step 6   回存：成稿同步回 IMA 知识库
Step 7   复盘：回写台账 + 漂移自检 + 日报
```

## 安装

```bash
git clone <本仓库地址> ~/.workbuddy/skills/wechat-pub-workbuddy
```

装好后重启 WorkBuddy（或新开对话）即可。

## 配置

```bash
cp config.example.json config.json
```

填好这几项：

| 项 | 说明 |
|----|------|
| `ima_kb_id` | 你的 IMA 知识库 ID |
| `ima_source_folder` | 素材来源文件夹 ID（限定范围，强烈建议填） |
| `persona` | 定位、目标读者、语气——决定选题准不准 |
| `topic_domains` | 主题词，决定往哪个方向找素材 |
| `hotspot_queries` | 找当天新闻的搜索词 |
| `benchmark_queries` | 找同赛道爆款的搜索词 |
| `benchmark_accounts` | 你盯的公众号名（可留空，留空则纯靠搜索词） |

凭证不放这里，放本机：

```bash
mkdir -p ~/.config/ima ~/.config/wechat
echo -n '<ClientID>' > ~/.config/ima/client_id
echo -n '<APIKey>'   > ~/.config/ima/api_key
echo -n '<AppID>'    > ~/.config/wechat/appid
echo -n '<Secret>'   > ~/.config/wechat/secret
```

也可以直接对 WorkBuddy 说「**配置公众号流水线**」，跑 `scripts/setup_wizard.py` 向导生成。

## 用法

| 你说 | 它做 |
|------|------|
| 跑流水线 | 立即走完整十步，产出进草稿箱 |
| 只拆爆款 | 单独跑 Step 0.6，看同赛道最近什么结构在起作用 |
| 诊断公众号流水线 | 一键体检（凭证/IP/连通性） |
| 给公众号流水线建每天 07:20 的定时任务 | 建每日 automation |

## 红线（不可违反）

1. **只进草稿箱，绝不自动群发**——发文脚本物理上没有群发能力。
2. **对标文章只拆骨架，禁止摘录原句**——原句一个字都不许进产物文件。
3. 投资/财经内容必含风险提示；无收益承诺、无绝对化用语、无无源数据。
4. **Truth-first**：素材不足允许减产（3→2→1→0）并留痕，绝不凑数发空心文。
5. 凭证只放 `~/.config/`，不进提示词、不进台账、不进 git。

## 目录结构

```
wechat-pub-workbuddy/
├── SKILL.md                     # 技能入口
├── SETUP.md                     # 配置指南
├── config.example.json          # 配置模板（复制成 config.json 用）
├── _rsi_ledger.template.md      # 台账模板
├── README.md
├── LICENSE
├── references/
│   ├── pipeline.md              # 十步编排手册
│   ├── agent-prompts.md         # 五个角色的提示词模板
│   ├── ima-api-mechanics.md     # IMA API 实测速查
│   └── qa-rubric.json           # 质检规则引擎
├── templates/                   # 产物模板（含 00_benchmark）
├── config/                      # 企微二维码（可选，不进库）
└── scripts/                     # 向导/诊断/排版/发文/归档/回存
```

## 许可

MIT License，见 [LICENSE](LICENSE)。原版权归原作者所有，本仓库为改造版本。
