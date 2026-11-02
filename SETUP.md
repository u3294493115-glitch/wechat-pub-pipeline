# SETUP.md — 图文配置指南（5 分钟跑起来）

> 本指南面向非技术用户。跟着做，你不需要懂代码。
> 前提：已安装 WorkBuddy，并拿到本技能文件夹（rsi-wechat-publisher）。

## 第 0 步：把技能装进 WorkBuddy

1. 把 `rsi-wechat-publisher` 整个文件夹复制到 `~/.workbuddy/skills/`（用户级，所有项目可用）。
   - Finder 里按 `Cmd+Shift+G`，输入 `~/.workbuddy/skills/` 回车，粘贴进去。
   - 或终端：`cp -R ~/Downloads/rsi-wechat-publisher ~/.workbuddy/skills/`
2. 重启 WorkBuddy（或新开一个对话）。

## 第 1 步：拿两个「钥匙」

### 钥匙 A：IMA 开放 API（你的素材库 + 文章回存）

1. 打开 ima.qq.com，登录你的 QQ/微信
2. 进「设置」→「开放 API」（入口也可能在个人中心/开发者入口）
3. 创建凭证，得到 **Client ID** 和 **API Key**（只显示一次，马上复制）

### 钥匙 B：微信公众号 API（自动进草稿箱）

1. 打开 mp.weixin.qq.com → 「设置与开发」→「基本配置」
2. 记下 **AppID**，点「重置」拿 **AppSecret**（只显示一次）
3. 同页面找到「IP 白名单」——先空着，下一步会告诉你加什么

## 第 2 步：把钥匙放进指定位置

打开「终端」（Terminal），逐行粘贴（把尖括号内容换成你自己的）：

```bash
mkdir -p ~/.config/ima ~/.config/wechat
echo -n '<你的IMA_ClientID>' > ~/.config/ima/client_id
echo -n '<你的IMA_APIKey>'    > ~/.config/ima/api_key
echo -n '<你的AppID>'         > ~/.config/wechat/appid
echo -n '<你的AppSecret>'     > ~/.config/wechat/secret
chmod 600 ~/.config/ima/* ~/.config/wechat/*
```

## 第 3 步：跑配置向导

对 WorkBuddy 说：

> **配置公众号流水线**

（或终端跑 `python3 ~/.workbuddy/skills/rsi-wechat-publisher/scripts/setup_wizard.py`）

向导会：
- 验证两把钥匙是否有效
- 列出你的 IMA 知识库让你选哪个当素材库
- 问你：笔名、公众号名、内容定位、每天几篇
- 实测公众号 token——**如果提示 IP 不在白名单，把它给的 IP 加到公众号后台的 IP 白名单里，再跑一遍向导**

## 第 4 步（可选）：企微二维码

如果想做获客：把你企微活码图存为 `~/.workbuddy/skills/rsi-wechat-publisher/config/wecom-qr.png`——每篇文章末尾会自动带上。没有就先用文字版 CTA。

## 第 5 步：跑第一轮！

对 WorkBuddy 说：

> **跑流水线**

约 10-20 分钟后你会收到日报：3 篇文章（含标题、质检分、media_id）已经进了你公众号的**草稿箱**。去 mp.weixin.qq.com 审核、编辑、手动群发。

## 第 6 步（可选）：每天自动跑

对 WorkBuddy 说：

> **给公众号流水线建每天 07:20 的定时任务**

## 常见问题

| 问题 | 答案 |
|------|------|
| 会自动群发吗？ | **永远不会**。只进草稿箱，群发永远是你手动点。 |
| 会把我的凭证泄露吗？ | 凭证只存在你电脑的 `~/.config/`，不进对话、不进 git。 |
| 文章质量谁把关？ | 每篇过七维质检（≥85 分）+ 四条一票否决（合规/空心化/重复素材/无源数据），不过就自动打回重写。 |
| 没配公众号 API 能用吗？ | 能。文章打包成 HTML 文件，你手动复制进公众号编辑器。 |
| 素材用完了怎么办？ | truth-first 原则：宁缺毋滥，会减产并说明原因；往 IMA 库里持续攒素材即可。 |
| 换个知识库/改笔名？ | 改 `~/.workbuddy/skills/rsi-wechat-publisher/config.json`，或重跑向导。 |
| 诊断问题？ | 说「诊断公众号流水线」，或跑 `python3 …/scripts/diagnose.py`。 |
