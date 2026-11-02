#!/usr/bin/env python3
"""post_draft.py — 推送文章 HTML 到微信公众号草稿箱（WorkBuddy 版，替代 baoyu-post-to-wechat）。

用法:
    python3 post_draft.py <article.html> --cover <cover.png> --title <标题> --digest <摘要> [--author 杨教练]

凭证（自动探测，缺失时本地降级）:
    ~/.config/wechat/appid     公众号 appid
    ~/.config/wechat/secret    公众号 secret

行为:
    1. 凭证齐全:
       a. GET access_token（稳定版接口）
       b. POST /cgi-bin/material/add_material?type=image  上传封面 → thumb_media_id
       c. POST /cgi-bin/draft/add  新增草稿 → media_id
       d. 输出 JSON: {"ok": true, "media_id": ..., "mode": "api"}
    2. 凭证缺失或 API 报 40164（IP 不在白名单）（降级，不失败）:
       打包 article.html + cover + 相关图片到 <html所在目录>/local-package/
       输出 JSON: {"ok": true, "media_id": "local-only", "mode": "local", "package": <目录>}

红线: 本脚本物理上不具备群发能力（不调用 freepublish 接口），只进草稿箱。
"""
import argparse
import json
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request

CRED_DIR = os.path.expanduser("~/.config/wechat")
TOKEN_CACHE = os.path.join(CRED_DIR, ".token_cache")


def http_json(url, data=None, headers=None, timeout=30):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data is not None else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_access_token(appid: str, secret: str) -> str:
    # 带本地缓存（token 2 小时有效，避免反复触发 IP 白名单检查）
    import time
    if os.path.isfile(TOKEN_CACHE):
        try:
            ts, tok = open(TOKEN_CACHE).read().strip().split("\t", 1)
            if time.time() - float(ts) < 7000:
                return tok
        except Exception:
            pass
    # stable_token 要求 POST（GET 会报 43002）
    url = "https://api.weixin.qq.com/cgi-bin/stable_token"
    payload = json.dumps({"grant_type": "client_credential", "appid": appid, "secret": secret}).encode("utf-8")
    r = http_json(url, data=payload, headers={"Content-Type": "application/json"})
    if "access_token" not in r:
        err = RuntimeError(f"获取 access_token 失败: {r}")
        err.wx_errcode = r.get("errcode")
        err.wx_errmsg = r.get("errmsg", "")
        raise err
    try:
        with open(TOKEN_CACHE, "w") as f:
            f.write(f"{time.time()}\t{r['access_token']}")
        os.chmod(TOKEN_CACHE, 0o600)
    except Exception:
        pass
    return r["access_token"]


def upload_cover(token: str, cover_path: str) -> str:
    """上传永久素材封面图，返回 thumb_media_id。"""
    boundary = "----WbRsiBoundary7MA4YWxkTrZu0gW"
    with open(cover_path, "rb") as f:
        img = f.read()
    filename = os.path.basename(cover_path)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{filename}"; '
        f'Content-Type: image/{"jpeg" if filename.lower().endswith((".jpg", ".jpeg")) else "png"}\r\n\r\n'
    ).encode("utf-8") + img + f"\r\n--{boundary}--\r\n".encode("utf-8")
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?type=image&access_token={token}"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        r = json.loads(resp.read().decode("utf-8"))
    if "media_id" not in r:
        raise RuntimeError(f"封面上传失败: {r}")
    return r["media_id"]


def add_draft(token: str, title: str, author: str, digest: str, html_content: str, thumb_media_id: str) -> str:
    url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
    payload = {
        "articles": [
            {
                "title": title,
                "author": author,
                "digest": digest,
                "content": html_content,
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }
        ]
    }
    r = http_json(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                  headers={"Content-Type": "application/json"})
    if "media_id" not in r:
        raise RuntimeError(f"草稿新增失败: {r}")
    return r["media_id"]


def local_fallback(html_path: str, cover: str, title: str, reason: str = "") -> dict:
    """本地降级：打包 HTML + 封面 + 引用的本地图片。"""
    src_dir = os.path.dirname(os.path.abspath(html_path))
    pkg = os.path.join(src_dir, "local-package")
    os.makedirs(pkg, exist_ok=True)
    shutil.copy(html_path, os.path.join(pkg, "article.html"))
    imgs_dir = os.path.join(pkg, "imgs")
    os.makedirs(imgs_dir, exist_ok=True)
    html_txt = open(html_path, encoding="utf-8").read()
    for src in re.findall(r'src="([^"]+)"', html_txt):
        if src.startswith(("http://", "https://", "data:")):
            continue
        abs_p = os.path.normpath(os.path.join(src_dir, src))
        if os.path.isfile(abs_p):
            shutil.copy(abs_p, os.path.join(imgs_dir, os.path.basename(abs_p)))
    if cover and os.path.isfile(cover):
        shutil.copy(cover, os.path.join(imgs_dir, "cover" + os.path.splitext(cover)[1]))
    guide = os.path.join(pkg, "README.txt")
    with open(guide, "w", encoding="utf-8") as f:
        f.write(
            f"本地发布包（未走公众号 API）\n"
            f"标题: {title}\n生成时间: {__import__('datetime').datetime.now().isoformat()}\n"
            + (f"原因: {reason}\n" if reason else "原因: 公众号 API 凭证未配置\n")
            + f"\n手动发布步骤:\n"
            f"1. 打开 mp.weixin.qq.com → 新建图文\n"
            f"2. 标题/摘要从 meta 或本文件顶部复制\n"
            f"3. 正文: 用浏览器打开 article.html → 全选复制 → 粘贴进编辑器（内联样式会保留）\n"
            f"4. 封面: 上传 imgs/cover.*\n"
            f"5. 二维码图在 imgs/ 内，确认文末 CTA 图片正常显示\n"
            f"6. 保存为草稿，走人工闸门\n\n"
            f"API 全自动进草稿箱的前置条件:\n"
            f"  mkdir -p ~/.config/wechat && echo -n <appid> > ~/.config/wechat/appid && echo -n <secret> > ~/.config/wechat/secret\n"
            f"  且本机出口 IP 已加入公众号后台「IP 白名单」（设置与开发 → 基本配置）\n"
        )
    out = {"ok": True, "media_id": "local-only", "mode": "local", "package": pkg,
           "note": "已本地打包；修复 API 前置条件后重跑可自动进草稿箱"}
    if reason:
        out["fallback_reason"] = reason
    return out


def main():
    ap = argparse.ArgumentParser(description="推送到公众号草稿箱（无群发能力）")
    ap.add_argument("html")
    ap.add_argument("--cover", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--digest", default="")
    ap.add_argument("--author", default="杨教练")
    args = ap.parse_args()

    html_path = os.path.abspath(args.html)
    if not os.path.isfile(html_path):
        print(json.dumps({"ok": False, "error": f"HTML 不存在: {html_path}"}, ensure_ascii=False))
        sys.exit(1)
    if not os.path.isfile(args.cover):
        print(json.dumps({"ok": False, "error": f"封面不存在: {args.cover}"}, ensure_ascii=False))
        sys.exit(1)

    appid_p, secret_p = os.path.join(CRED_DIR, "appid"), os.path.join(CRED_DIR, "secret")
    if not (os.path.isfile(appid_p) and os.path.isfile(secret_p)):
        print(json.dumps(local_fallback(html_path, args.cover, args.title, "凭证缺失"), ensure_ascii=False))
        return

    try:
        appid = open(appid_p).read().strip()
        secret = open(secret_p).read().strip()
        token = get_access_token(appid, secret)
        thumb = upload_cover(token, args.cover)
        content = open(html_path, encoding="utf-8").read()
        media_id = add_draft(token, args.title, args.author, args.digest or args.title[:54], content, thumb)
        print(json.dumps({"ok": True, "media_id": media_id, "mode": "api"}, ensure_ascii=False))
    except Exception as e:
        errcode = getattr(e, "wx_errcode", None)
        errmsg = getattr(e, "wx_errmsg", "") or str(e)
        # 40164 = IP 不在白名单：给出明确指引
        if errcode == 40164:
            import re as _re
            ip_m = _re.search(r"invalid ip (\d+\.\d+\.\d+\.\d+)", errmsg)
            ip = ip_m.group(1) if ip_m else "<本机出口IP>"
            reason = (f"IP 白名单未包含本机出口 {ip}——请到公众号后台「设置与开发→基本配置→IP白名单」"
                      f"添加 {ip} 后重跑")
            print(json.dumps(local_fallback(html_path, args.cover, args.title, reason), ensure_ascii=False))
            return
        # 其余 API 失败也降级本地包，绝不丢稿
        result = local_fallback(html_path, args.cover, args.title, f"公众号 API 调用失败: {errmsg[:200]}")
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
