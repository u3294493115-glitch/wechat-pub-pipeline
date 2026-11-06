#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_check.py —— 排版成品体检（format 之后、推草稿之前）

为什么要有这个脚本：
    writer 后面有 voice_lint 拦，qa 后面有 85 分门槛拦，
    但 **format 之后到推草稿之间没有任何检查**——HTML 生成完就直接上传。
    2026-11-02 实测发现：`md_to_html.py` 把引用块里的 <br/> 转义成了
    字面 `&lt;br/&gt;`，微信里读者看到的是 "。<br/>上下文："。
    这个 bug 在 2026-11-01 那篇**已经发布**的文章里同样存在，三篇都没人发现——
    因为没有任何一步会去看生成的 HTML 长什么样。

检查项（全部机械可判）：
    1. 转义残留        &lt;br/&gt; 这类，微信里会显示成字面标签
    2. 正文图片        本地相对路径（imgs/x.jpg）微信不显示，必须是 http/https
    3. 未替换占位      [配图：…] 留在终稿里
    4. 封面            文件存在且不太大
    5. CTA             文末有没有承接（回复数字 / 微信搜索）
    6. 标题长度        微信标题上限 64 字
    7. 摘要长度        建议 ≤54 字（post_draft 默认按这个截）
    8. 空壳             正文纯文字 < 300 字

用法：
    python scripts/render_check.py --dir pipeline/2026-11-02/p1/format --title "标题" --cover imgs/cover.png
    python scripts/render_check.py article.html

退出码：0 通过（可有提醒）；1 有硬伤；2 文件读不到
"""

import os
import re
import sys
import argparse

MAX_TITLE = 64
MAX_DIGEST = 54
MAX_COVER_KB = 500
MIN_BODY_CHARS = 300

ESC_RESIDUE_RE = re.compile(r"&lt;/?[a-zA-Z][^&]{0,20}&gt;")
IMG_SRC_RE = re.compile(r'<img[^>]*src="([^"]+)"', re.I)
PLACEHOLDER_RE = re.compile(r"\[配图[：:]")
CTA_HINTS = ("私信", "加你", "加我", "微信搜索", "一起聊")


def check(html_path, title=None, digest=None, cover=None):
    problems, warns, notes = [], [], []

    if not os.path.isfile(html_path):
        return ["HTML 不存在"], [], []
    html = open(html_path, encoding="utf-8").read()

    # 1) 转义残留
    residues = ESC_RESIDUE_RE.findall(html)
    if residues:
        uniq = sorted(set(residues))[:5]
        problems.append(
            f"[转义残留] {len(residues)} 处 {' '.join(uniq)} → 微信里会显示成字面标签。"
            f"查 md_to_html.py 里是不是先拼标签再做 html.escape"
        )

    # 2) 正文图片必须是可访问地址
    srcs = IMG_SRC_RE.findall(html)
    local_imgs = [s for s in srcs if not s.startswith(("http://", "https://", "data:"))]
    if local_imgs:
        problems.append(
            f"[正文图片] {len(local_imgs)} 张是本地路径（{', '.join(local_imgs[:3])}）→ "
            f"微信不显示本地文件。要么先传素材库换成 mmbiz 地址，要么删掉这几张图。"
            f"post_draft.py 只上传封面，不上传正文图"
        )
    if not srcs:
        notes.append("正文无图片")

    # 3) 未替换占位
    if PLACEHOLDER_RE.search(html):
        problems.append("[配图占位] 终稿里还留着 [配图：…]，format 环节必须替换成真图或删掉")

    # 4) 封面
    if cover is not None:
        if not os.path.isfile(cover):
            problems.append(f"[封面] 不存在：{cover}")
        else:
            kb = os.path.getsize(cover) / 1024
            if kb > MAX_COVER_KB:
                warns.append(f"[封面] {kb:.0f}KB > {MAX_COVER_KB}KB，建议跑 compress_image.sh")
            else:
                notes.append(f"封面 {kb:.0f}KB")

    # 5) CTA
    tail = html[-2500:]
    if not any(h in tail for h in CTA_HINTS):
        warns.append("[CTA] 文末没找到承接话术（回复数字 / 微信搜索 / 长按识别）——按 cta.md 规则应注入")

    # 6) 标题
    if title:
        if len(title) > MAX_TITLE:
            problems.append(f"[标题] {len(title)} 字 > 微信上限 {MAX_TITLE}")
        else:
            notes.append(f"标题 {len(title)} 字")

    # 7) 摘要
    if digest:
        if len(digest) > MAX_DIGEST:
            warns.append(f"[摘要] {len(digest)} 字 > {MAX_DIGEST}，推送时会被截断")
        else:
            notes.append(f"摘要 {len(digest)} 字")

    # 8) 空壳
    text_only = re.sub(r"<[^>]+>", "", html)
    n = len(re.sub(r"\s", "", text_only))
    if n < MIN_BODY_CHARS:
        problems.append(f"[正文过短] 纯文字 {n} 字 < {MIN_BODY_CHARS}，可能转换失败")
    else:
        notes.append(f"正文纯文字 {n} 字")

    return problems, warns, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html", nargs="?", help="article.html")
    ap.add_argument("--dir", help="format 目录，自动找 article.html")
    ap.add_argument("--title", default=None)
    ap.add_argument("--digest", default=None)
    ap.add_argument("--cover", default=None)
    a = ap.parse_args()

    html = a.html
    if a.dir:
        html = os.path.join(a.dir, "article.html")
    if not html:
        print("用法: python scripts/render_check.py article.html | --dir <format目录>", file=sys.stderr)
        return 2

    problems, warns, notes = check(html, a.title, a.digest, a.cover)
    print(f"=== 排版成品体检 · {os.path.basename(html)} ===")
    for n in notes:
        print(f"   · {n}")
    for w in warns:
        print(f"  ? {w}")
    for p in problems:
        print(f"  ✗ {p}")
    print("=== " + ("FAIL" if problems else ("PASS(有提醒)" if warns else "PASS")) + " ===")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
