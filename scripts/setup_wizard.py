#!/usr/bin/env python3
"""setup_wizard.py — rsi-wechat-publisher 配置向导（首次使用必跑）。

做什么：
  1. 探测 IMA 凭证（~/.config/ima/{client_id,api_key}）→ 列出你的知识库 → 记下选择
  2. 探测公众号凭证（~/.config/wechat/{appid,secret}）→ 实测 token → IP 白名单不通过给出指引
  3. 交互收集：作者笔名 / 公众号名 / 内容定位 / 每日篇数
  4. 生成 config.json + 空白 _rsi_ledger.md + pipeline 目录
  5. 输出「下一步」清单

用法：
  python3 scripts/setup_wizard.py            # 交互式
  python3 scripts/setup_wizard.py --check    # 只做体检不写配置
"""
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(SKILL_DIR, "config.json")

# ── 网络（绕过系统代理，直连腾讯域） ──
import urllib.request
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
IMA_BASE = "https://ima.qq.com/openapi/wiki/v1/"


def ima_api(path, body, cid, key):
    req = urllib.request.Request(IMA_BASE + path, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json",
        "ima-openapi-clientid": cid,
        "ima-openapi-apikey": key})
    with OPENER.open(req, timeout=20) as r:
        return json.loads(r.read())


def read_cred(path, name):
    p = os.path.expanduser(path)
    if os.path.isfile(p):
        v = open(p).read().strip()
        if v:
            return v
    return None


def check_ima():
    print("\n【1/3】IMA 知识库凭证")
    cid = read_cred("~/.config/ima/client_id", "client_id")
    key = read_cred("~/.config/ima/api_key", "api_key")
    if not (cid and key):
        print("  ⚠️ 未找到 ~/.config/ima/{client_id,api_key}")
        print("     获取：ima.qq.com → 设置 → 开放 API → 创建凭证")
        print("     落盘：echo -n '<ClientID>' > ~/.config/ima/client_id")
        print("           echo -n '<APIKey>'  > ~/.config/ima/api_key")
        return None, None
    try:
        rep = ima_api("search_knowledge_base", {"query": "", "knowledge_base_id": "", "limit": 20}, cid, key)
        kbs = (rep.get("data") or {}).get("searched_knowledge_base_list") or []
        if not kbs:
            rep2 = ima_api("get_knowledge_base_list", {"params": [{"limit": 20}]}, cid, key)
            kbs = (rep2.get("results") or [{}])[0].get("knowledge_base_list") or []
        print(f"  ✅ 凭证有效，发现 {len(kbs)} 个知识库")
        return cid, kbs
    except Exception as e:
        print(f"  ❌ IMA API 调用失败：{e}")
        return cid, None


def check_wechat():
    print("\n【2/3】微信公众号凭证")
    appid = read_cred("~/.config/wechat/appid", "appid")
    secret = read_cred("~/.config/wechat/secret", "secret")
    if not (appid and secret):
        print("  ⚠️ 未找到 ~/.config/wechat/{appid,secret}（可选：不配则文章打包本地 HTML 手动发）")
        return False
    import urllib.parse
    url = "https://api.weixin.qq.com/cgi-bin/stable_token"
    payload = json.dumps({"grant_type": "client_credential", "appid": appid, "secret": secret}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with OPENER.open(req, timeout=15) as r:
            rep = json.loads(r.read())
        if "access_token" in rep:
            print("  ✅ token 获取成功（凭证+IP白名单均正常）")
            return True
        errcode = rep.get("errcode")
        if errcode == 40164:
            import re
            ip = (re.search(r"invalid ip (\d+\.\d+\.\d+\.\d+)", rep.get("errmsg", "")) or [None, "<未知>"])[1]
            print(f"  ❌ IP 不在白名单：请到公众号后台「设置与开发→基本配置→IP白名单」添加 {ip}")
            print(f"     （跑 python3 scripts/diagnose.py 可复现此 IP）")
        else:
            print(f"  ❌ 失败 errcode={errcode}: {rep.get('errmsg')}")
    except Exception as e:
        print(f"  ❌ 请求失败：{e}")
    return False


def ask(prompt, default=""):
    try:
        v = input(f"{prompt}{'[' + default + ']' if default else ''}: ").strip()
        return v or default
    except EOFError:
        return default


def main():
    if "--check" in sys.argv:
        check_ima(); check_wechat()
        print("\n体检完成（--check 模式不写配置）")
        return

    print("=" * 52)
    print("  rsi-wechat-publisher 配置向导")
    print("=" * 52)

    cid, kbs = check_ima()
    wechat_ok = check_wechat()

    print("\n【3/3】个人配置")
    kb_id, kb_name = "", ""
    if kbs:
        print("  选择内容主素材知识库：")
        for i, kb in enumerate(kbs[:10], 1):
            print(f"   {i}. {kb.get('basic_info',{}).get('name','?')}  (id: {kb.get('id','')[:20]}…)")
        sel = ask("  输入序号（默认 1）", "1")
        try:
            kb = kbs[int(sel) - 1]
            kb_id = kb.get("id", "")
            kb_name = kb.get("basic_info", {}).get("name", "")
            print(f"  → 已选「{kb_name}」")
        except Exception:
            print("  → 序号无效，知识库 ID 留空（之后可手填 config.json）")
    else:
        kb_id = ask("  手填知识库 ID（可留空稍后补）", "")
        kb_name = ask("  知识库名称", "")

    author = ask("  作者笔名", "")
    account = ask("  公众号名称（无二维码时文末文字CTA用）", "")
    positioning = ask("  内容定位一句话", "")
    readers = ask("  目标读者", "")
    per_day = ask("  每天几篇（1-3）", "3")

    cfg = {
        "ima_kb_id": kb_id,
        "ima_kb_name": kb_name,
        "ima_folder_articles": "",
        "author_name": author,
        "wechat_account_name": account,
        "articles_per_day": int(per_day) if per_day.isdigit() else 3,
        "theme": "default",
        "persona": {"positioning": positioning, "target_readers": readers,
                     "tone": "专业但不说教，像资深教练做一对一复盘，第二人称"},
        "topic_domains": ["量化投资", "AI与投资", "财富认知", "投资者行为"],
        "hotspot_queries": ["今日AI人工智能财经热点", "36氪 AI 快讯"],
    }
    old = {}
    if os.path.isfile(CONFIG):
        try:
            old = json.load(open(CONFIG, encoding="utf-8"))
        except Exception:
            pass
    old.update(cfg)
    json.dump(old, open(CONFIG, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n✅ config.json 已写入：{CONFIG}")

    # 空白台账（不存在才建）
    ledger = os.path.join(SKILL_DIR, "_rsi_ledger.md")
    if not os.path.isfile(ledger):
        open(ledger, "w", encoding="utf-8").write(EMPTY_LEDGER.format(author=author))
        print(f"✅ 空白 RSI 台账已生成：{ledger}")

    pipe = os.path.join(os.path.dirname(SKILL_DIR), "pipeline")
    os.makedirs(pipe, exist_ok=True)
    print(f"✅ 产物目录已建：{pipe}")

    print("\n" + "=" * 52)
    print("下一步：")
    print("  1. 对 WorkBuddy 说「跑流水线」试第一轮")
    print("  2. （可选）把企微二维码放 config/wecom-qr.png")
    print("  3. （可选）说「给公众号流水线建每天 07:20 定时任务」")
    if not wechat_ok:
        print("  ⚠️ 公众号 API 未通：文章会打包到 local-package/ 手动发，修好凭证后自动进草稿箱")
    print("=" * 52)


EMPTY_LEDGER = """# RSI 进化台账（{author}）

> 本台账是 rsi-wechat-publisher 的自进化核心。每次流水线跑完一轮必须更新。越用越聪明。

## 1. 素材避重（换源）
| 日期 | 源名称 | 累计使用次数 | 最近使用日期 | 备注 |
|------|--------|-------------|-------------|------|

## 2. 风格偏好（哪些标题/调性效果最好）
| 日期 | 标题模式 | 质检分 | 人工反馈 | 结论 |
|------|---------|--------|---------|------|

## 3. 金句库（可复用、验证过传播力的表达）
| 金句 | 来源 | 首次使用日期 | 复用次数 |
|------|------|-------------|---------|

## 4. 人工修正记录（你的每次改动都是进化信号）
| 日期 | 文章 | 改了什么 | 为什么 | 频次 | 级别 |
|------|------|---------|--------|------|------|

> 硬/软分级：同款修改出现 ≥2 次或你明确说「以后都这样」→ 硬约束（必须遵守）；单次修改只是软参考。

## 5. RSI 回路快照（每轮一次的自我评估）
| 轮次 | 日期 | 质检分变化 | 比上轮强在哪 | 下轮重点 |
|------|------|-----------|-------------|---------|

## 6. 有效期提醒（Expiry Watch）
| 项目 | 文件/位置 | 生效日期 | 到期日期 | 处理动作 | 状态 |
|------|-----------|----------|----------|----------|------|

## 7. 发布数据（阅读/点赞回流）
| 日期 | 标题 | 阅读 | 点赞 | 采集日 | 归档目录 |
|------|------|------|------|--------|----------|

## 8. 演进记录（版本/流程变更）
| 日期 | 改进项 | 内容 | 触发原因 |
|------|--------|------|---------|
"""


if __name__ == "__main__":
    main()
