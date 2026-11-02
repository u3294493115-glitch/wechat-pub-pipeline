#!/usr/bin/env python3
"""diagnose.py — 一键诊断：凭证 / IP 白名单 / IMA 连通 / 公众号 API / 代理干扰。

用法：python3 scripts/diagnose.py
输出：逐项 ✅/❌ 与修复指引；结尾给「本机出口 IP」（加公众号白名单用）。
"""
import json
import os
import re
import urllib.request

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
IMA_BASE = "https://ima.qq.com/openapi/wiki/v1/"


def read_cred(path):
    p = os.path.expanduser(path)
    return open(p).read().strip() if os.path.isfile(p) else None


def main():
    print("=" * 50)
    print(" rsi-wechat-publisher 一键诊断")
    print("=" * 50)

    # 1. 命令依赖
    import shutil
    for cmd in ("git", "python3"):
        print(f"[依赖] {cmd}: {'✅ ' + shutil.which(cmd) if shutil.which(cmd) else '❌ 未安装'}")

    # 2. IMA 凭证
    cid, key = read_cred("~/.config/ima/client_id"), read_cred("~/.config/ima/api_key")
    if not (cid and key):
        print("[IMA] ❌ 凭证缺失 ~/.config/ima/{client_id,api_key}（素材采集将跳过）")
    else:
        try:
            req = urllib.request.Request(
                IMA_BASE + "search_knowledge_base",
                data=json.dumps({"query": "", "limit": 1}).encode(), method="POST",
                headers={"Content-Type": "application/json",
                         "ima-openapi-clientid": cid, "ima-openapi-apikey": key})
            with OPENER.open(req, timeout=15) as r:
                rep = json.loads(r.read())
            print(f"[IMA] ✅ API 连通（code={rep.get('code')}）")
        except Exception as e:
            print(f"[IMA] ❌ API 失败：{e}")

    # 3. 公众号凭证 + IP 白名单
    appid, secret = read_cred("~/.config/wechat/appid"), read_cred("~/.config/wechat/secret")
    exit_ip = None
    if not (appid and secret):
        print("[公众号] ⚠️ 凭证缺失 ~/.config/wechat/{appid,secret}（将使用本地打包降级）")
    else:
        try:
            payload = json.dumps({"grant_type": "client_credential", "appid": appid, "secret": secret}).encode()
            req = urllib.request.Request("https://api.weixin.qq.com/cgi-bin/stable_token",
                                         data=payload, headers={"Content-Type": "application/json"})
            with OPENER.open(req, timeout=15) as r:
                rep = json.loads(r.read())
            if "access_token" in rep:
                print("[公众号] ✅ token 成功（凭证+IP 白名单正常）")
            elif rep.get("errcode") == 40164:
                m = re.search(r"invalid ip (\d+\.\d+\.\d+\.\d+)", rep.get("errmsg", ""))
                exit_ip = m.group(1) if m else None
                print(f"[公众号] ❌ IP 不在白名单{('，本机出口=' + exit_ip) if exit_ip else ''}")
                print(f"        → 公众号后台「设置与开发→基本配置→IP白名单」添加该 IP")
            else:
                print(f"[公众号] ❌ errcode={rep.get('errcode')}: {rep.get('errmsg')}")
        except Exception as e:
            print(f"[公众号] ❌ 请求失败：{e}")

    # 4. 出口 IP（兜底显示）
    if not exit_ip:
        try:
            req = urllib.request.Request("https://api.weixin.qq.com/cgi-bin/stable_token",
                                         data=b'{"grant_type":"client_credential","appid":"probe","secret":"probe"}',
                                         headers={"Content-Type": "application/json"})
            with OPENER.open(req, timeout=10) as r:
                rep = json.loads(r.read())
            m = re.search(r"invalid ip (\d+\.\d+\.\d+\.\d+)", rep.get("errmsg", ""))
            if m:
                exit_ip = m.group(1)
        except Exception:
            pass
    print(f"\n本机对微信 API 的出口 IP：{exit_ip or '（探测失败，跑一次向导/流水线后从报错里看）'}")

    # 5. config.json
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    if os.path.isfile(cfg_path):
        cfg = json.load(open(cfg_path, encoding="utf-8"))
        print(f"[配置] ✅ config.json 存在（知识库: {cfg.get('ima_kb_name') or cfg.get('ima_kb_id') or '未填'}；作者: {cfg.get('author_name','?')}）")
    else:
        print("[配置] ❌ config.json 不存在 → 跑 python3 scripts/setup_wizard.py")

    print("=" * 50)


if __name__ == "__main__":
    main()
