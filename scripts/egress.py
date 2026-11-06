#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""egress.py —— 查本机直连出口 IPv4，并说明微信 40164 该加哪个 IP

为什么单独一个文件：
    微信 IP 白名单只认 IPv4。2026-11-02 实测同一台机器：
        直连出口  120.235.80.72            （IPv4，佛山移动）
        走代理出口 2409:8a55:51cd:6320:...  （IPv6）
    所以上传图片 / 推草稿必须**绕过系统代理**；代理开着不影响，
    但白名单里必须躺着那个 IPv4。
    换网、重启光猫、运营商重新分配，IPv4 都会变 —— 变了要重加。

用法：
    python scripts/egress.py          # 人看的输出
    python scripts/egress.py --json   # 给 upload_image.py / post_draft.py 调
"""

import os
import re
import sys
import json
import socket
import urllib.request

# 直连：空 ProxyHandler 等同于 requests 的 trust_env=False
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# 国内可达、返回纯文本的 IP 查询服务，按顺序试
PROBES = [
    "https://myip.ipip.net",
    "https://www.taobao.com/help/getip.php",
]

IPV4_RE = re.compile(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b")

_ipv4_forced = False


def force_ipv4():
    """把 DNS 解析锁死在 AF_INET。

    为什么必须这么做（2026-11-02 实测，同一台机器同时刻）：
        curl --noproxy '*'  https://myip.ipip.net  -> 120.235.80.72   （IPv4）
        python urllib 直连   https://myip.ipip.net  -> 2409:8a55:...   （IPv6）
    Windows 默认 IPv6 优先，Python 走 getaddrinfo 先拿到 AAAA 记录。
    微信白名单只认 IPv4，所以「绕开代理」还不够，还得把协议族锁死，
    否则照样 40164——而且报错里的 IPv6 永远加不进白名单。
    """
    global _ipv4_forced
    if _ipv4_forced:
        return
    _orig = socket.getaddrinfo

    def gai(host, port, family=0, type=0, proto=0, flags=0):
        return _orig(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = gai
    _ipv4_forced = True


def _fetch_via(opener, url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def detect(use_proxy=False):
    """返回出口的 IPv4 字符串；查不到返回 None。
    use_proxy=True 时沿用环境里的系统代理（只为对比，不用它调微信）。"""
    opener = urllib.request.build_opener() if use_proxy else _OPENER
    for url in PROBES:
        try:
            txt = _fetch_via(opener, url)
        except Exception:
            continue
        for m in IPV4_RE.finditer(txt):
            ip = m.group(1)
            # 排除版本号之类的误命中，简单校验各段 <=255
            if all(0 <= int(x) <= 255 for x in ip.split(".")):
                return ip
    return None


def proxy_env():
    for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        if os.environ.get(k):
            return os.environ[k]
    return None


def report():
    direct = detect(use_proxy=False)
    proxied = detect(use_proxy=True) if proxy_env() else None
    return {"direct_ipv4": direct, "proxy_env": proxy_env(), "proxied_ipv4": proxied}


def whitelist_hint():
    """给 40164 用的完整提示：直接把该加的 IP 写出来。"""
    force_ipv4()
    r = report()
    ip = r["direct_ipv4"]
    lines = []
    if ip:
        lines.append(f"要把这个 IPv4 加进白名单：{ip}")
    else:
        lines.append("查不到本机出口 IPv4（可能断网），请手动访问 myip.ipip.net 查看。")
    lines.append("公众号后台 → 设置与开发 → 基本配置 → IP白名单 → 修改")
    if r["proxy_env"]:
        extra = f"，代理出口是 {r['proxied_ipv4']}" if r["proxied_ipv4"] else ""
        lines.append(f"注意：本机开着代理（{r['proxy_env']}）{extra}；"
                     "代理出口多为 IPv6，白名单不认，所以脚本强制直连——代理不必关。")
    lines.append("换网／重启光猫后 IPv4 可能变，变了要重加。")
    return " ".join(lines)


def main():
    force_ipv4()
    if "--json" in sys.argv:
        print(json.dumps(report(), ensure_ascii=False, indent=1))
        return 0
    r = report()
    print(f"直连出口 IPv4 : {r['direct_ipv4'] or '（查不到）'}")
    if r["proxy_env"]:
        print(f"系统代理      : {r['proxy_env']}")
        print(f"代理出口      : {r['proxied_ipv4'] or '（查不到）'}")
        print("")
        print("→ 上传图片/推草稿都强制直连，代理不用关；")
        print(f"→ 白名单要加的是直连那个：{r['direct_ipv4']}")
    else:
        print("系统代理      : 未开")
        print(f"→ 白名单要加的是：{r['direct_ipv4']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
