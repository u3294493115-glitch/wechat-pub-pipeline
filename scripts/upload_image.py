#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""upload_image.py —— 正文图片上传微信素材库并回写 HTML

为什么要有这个脚本：
    `post_draft.py` 只上传**封面**，正文里的 <img src="imgs/x.jpg"> 是本地路径，
    推到公众号后读者看到的是一张裂图。2026-11-02 实测确认：
    旧三篇之所以没暴露，是因为它们正文里 0 张图；这篇有 2 张，一推就露。

做什么：
    1. 扫 HTML 里所有本地图片（非 http/https/data）
    2. 逐个上传 `cgi-bin/material/add_material?type=image`，拿回 mmbiz 地址
    3. 把 HTML 里的本地路径替换成 mmbiz 地址，另存 `article.pub.html`
    4. 按文件 sha1 缓存，同一张图不重复上传（避免素材库堆垃圾）

注意：
    - 必须直连，不走系统代理（代理出站可能变 IPv6，微信白名单只认 IPv4）
    - 需公众号 IP 白名单已包含本机出口 IP，否则 40164
    - 微信图片素材限制：≤10MB，格式 bmp/png/jpeg/jpg/gif

用法：
    python scripts/upload_image.py --dir pipeline/2026-11-02/p1/format
    python scripts/upload_image.py article.html --out article.pub.html

退出码：0 全部替换成功（或本来就没有本地图）；1 有失败；2 文件读不到
"""

import os
import re
import sys
import json
import hashlib
import argparse
import mimetypes
import urllib.request

CRED_DIR = os.path.expanduser("~/.config/wechat")
CACHE_PATH = os.path.join(CRED_DIR, ".img_cache.json")
IMG_SRC_RE = re.compile(r'(<img[^>]*src=")([^"]+)(")', re.I)
MAX_MB = 10
ALLOWED = (".jpg", ".jpeg", ".png", ".gif", ".bmp")

# 微信 API 直连：代理会导致出站 IPv6，而白名单只认 IPv4
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# 绕开代理还不够：Windows 默认 IPv6 优先，Python 直连出去仍是 IPv6。
# 必须把 DNS 解析锁死 AF_INET，出口才会是白名单里那个 IPv4。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from egress import force_ipv4, whitelist_hint  # noqa: E402

force_ipv4()

HINT = ("微信 IP 白名单未包含本机出口 IP。到公众号后台「设置与开发 → 基本配置 → IP白名单」"
        "把报错里那个 IPv4 加进去，再重跑。换网或重启光猫后 IP 可能变，变了要重新加。")


def http_json(url, data=None, headers=None, timeout=60):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    with _OPENER.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_access_token():
    appid_p, secret_p = os.path.join(CRED_DIR, "appid"), os.path.join(CRED_DIR, "secret")
    if not (os.path.isfile(appid_p) and os.path.isfile(secret_p)):
        raise RuntimeError(f"凭证缺失：{CRED_DIR}/appid 或 secret")
    appid = open(appid_p).read().strip()
    secret = open(secret_p).read().strip()
    r = http_json(f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}")
    if "access_token" not in r:
        raise RuntimeError(f"取 token 失败：{r}")
    return r["access_token"]


def load_cache():
    if os.path.isfile(CACHE_PATH):
        try:
            return json.load(open(CACHE_PATH, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(c):
    os.makedirs(CRED_DIR, exist_ok=True)
    json.dump(c, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def upload(token, path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED:
        raise RuntimeError(f"格式不支持（{ext}），微信只收 {'/'.join(ALLOWED)}")
    size_mb = os.path.getsize(path) / 1024 / 1024
    if size_mb > MAX_MB:
        raise RuntimeError(f"{size_mb:.1f}MB > {MAX_MB}MB，先跑 compress_image.sh")

    boundary = "----WXBoundary" + hashlib.md5(path.encode()).hexdigest()[:16]
    ctype = mimetypes.guess_type(path)[0] or "image/jpeg"
    data = open(path, "rb").read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{os.path.basename(path)}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?type=image&access_token={token}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with _OPENER.open(req, timeout=120) as resp:
        r = json.loads(resp.read().decode("utf-8"))
    if "url" not in r:
        raise RuntimeError(f"上传失败：{r}")
    return r["url"], r.get("media_id")


def resolve(src, base_dir):
    """本地路径解析：先按 html 同级，再按上级 imgs/ 找。"""
    cand = [
        os.path.normpath(os.path.join(base_dir, src)),
        os.path.normpath(os.path.join(base_dir, "..", src)),
        os.path.normpath(os.path.join(base_dir, "..", "imgs", os.path.basename(src))),
    ]
    for c in cand:
        if os.path.isfile(c):
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html", nargs="?", help="article.html")
    ap.add_argument("--dir", help="format 目录，自动找 article.html")
    ap.add_argument("--out", help="输出文件（默认 article.pub.html）")
    a = ap.parse_args()

    html_path = a.html or (os.path.join(a.dir, "article.html") if a.dir else None)
    if not html_path or not os.path.isfile(html_path):
        print(json.dumps({"ok": False, "error": f"HTML 不存在: {html_path}"}, ensure_ascii=False))
        return 2

    base_dir = os.path.dirname(os.path.abspath(html_path))
    out_path = a.out or os.path.join(base_dir, "article.pub.html")
    html = open(html_path, encoding="utf-8").read()

    locals_ = [(m.group(2)) for m in IMG_SRC_RE.finditer(html)
               if not m.group(2).startswith(("http://", "https://", "data:"))]
    if not locals_:
        print(json.dumps({"ok": True, "changed": 0, "note": "没有本地图片，无需处理", "out": html_path},
                         ensure_ascii=False))
        return 0

    cache = load_cache()
    mapping, errors = {}, []

    # 先取一次 token，失败就直接退出——不要每张图各试一遍白名单
    try:
        token = get_access_token()
    except Exception as e:
        msg = str(e)
        hint = whitelist_hint() if "40164" in msg else HINT
        print(json.dumps({"ok": False, "error": msg, "hint": hint,
                          "pending": list(dict.fromkeys(locals_))}, ensure_ascii=False, indent=1))
        return 1

    for src in dict.fromkeys(locals_):
        abs_p = resolve(src, base_dir)
        if not abs_p:
            errors.append(f"{src}: 文件找不到")
            continue
        sha = hashlib.sha1(open(abs_p, "rb").read()).hexdigest()
        if sha in cache:
            mapping[src] = cache[sha]["url"]
            continue
        try:
            url, mid = upload(token, abs_p)
            cache[sha] = {"url": url, "media_id": mid, "file": os.path.basename(abs_p)}
            mapping[src] = url
        except Exception as e:
            errors.append(f"{src}: {e}")

    if mapping:
        save_cache(cache)

    for old, new in mapping.items():
        html = html.replace(f'src="{old}"', f'src="{new}"')

    if errors:
        # 有失败就不写输出，避免半成品被推上去
        joined = " ".join(errors)
        out = {"ok": False, "error": "部分图片上传失败，未生成输出文件",
               "failed": errors, "succeeded": len(mapping)}
        if "40164" in joined:
            out["hint"] = whitelist_hint()
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    open(out_path, "w", encoding="utf-8").write(html)
    print(json.dumps({"ok": True, "changed": len(mapping), "out": out_path,
                      "mapping": mapping}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
