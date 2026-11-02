#!/usr/bin/env python3
"""md_to_html.py — Markdown 转微信公众号兼容 HTML（内联样式版）。

用法:
    python3 md_to_html.py <in.md> <out.html> [--title <标题>] [--theme default|blue]

说明:
    - 微信公众号编辑器不支持外部 CSS / <style> 标签，所有样式必须内联。
    - 支持: 标题/段落/加粗/斜体/行内代码/代码块/引用/有序无序列表/表格/图片/分隔线。
    - [配图：<描述>] 行会被转换为图片占位注释（供 format 环节替换为真实图片）。
    - 主题 default: 品牌深蓝 #1B3A5C；blue: 亮蓝 #2A6EC9。
    - 无第三方依赖，纯标准库。
"""
import argparse
import html
import json
import re
import sys

THEMES = {
    "default": {"primary": "#1B3A5C", "accent": "#2A6EC9", "bg": "#F5F7FA", "border": "#D8DEE6", "text": "#333333", "sub": "#666666"},
    "blue": {"primary": "#2A6EC9", "accent": "#2A6EC9", "bg": "#EDF3FB", "border": "#C5D8EE", "text": "#333333", "sub": "#666666"},
}

INLINE_RE = re.compile(
    r"(\*\*.+?\*\*|\*[^*]+?\*|`[^`]+?`|!\[[^\]]*\]\([^)]+\)|\[[^\]]+\]\([^)]+\))"
)


def render_inline(text: str, t: dict) -> str:
    out, pos = [], 0
    for m in INLINE_RE.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        s = m.group(0)
        if s.startswith("**"):
            out.append(f'<strong style="color:{t["primary"]};">{html.escape(s[2:-2])}</strong>')
        elif s.startswith("`"):
            out.append(f'<code style="background:{t["bg"]};padding:2px 6px;border-radius:4px;font-size:15px;color:{t["primary"]};">{html.escape(s[1:-1])}</code>')
        elif s.startswith("!["):
            img_m = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", s)
            alt, src = img_m.group(1), img_m.group(2)
            out.append(f'<img src="{html.escape(src)}" alt="{html.escape(alt)}" style="max-width:100%;border-radius:8px;display:block;margin:16px auto;"/>')
        elif s.startswith("["):
            a_m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", s)
            label, href = a_m.group(1), a_m.group(2)
            out.append(f'<span style="color:{t["accent"]};text-decoration:underline;">{html.escape(label)}</span>')
        elif s.startswith("*"):
            out.append(f"<em>{html.escape(s[1:-1])}</em>")
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def md_to_html(md: str, title: str, theme: str) -> str:
    t = THEMES.get(theme, THEMES["default"])
    lines = md.split("\n")
    body, i, in_code = [], 0, False
    code_buf, list_stack = [], []

    def close_lists():
        while list_stack:
            body.append(f"</{list_stack.pop()}>")

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                code = "\n".join(code_buf)
                body.append(
                    f'<section style="background:{t["bg"]};border:1px solid {t["border"]};'
                    f'border-radius:8px;padding:14px 16px;margin:18px 0;overflow-x:auto;">'
                    f'<pre style="margin:0;font-size:14px;line-height:1.7;white-space:pre-wrap;color:{t["text"]};">{html.escape(code)}</pre></section>'
                )
                code_buf, in_code = [], False
            else:
                close_lists()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        if not stripped:
            close_lists()
            i += 1
            continue

        # [配图：…] 占位
        pm = re.match(r"^\[配图[：:] *(.+?)\]$", stripped)
        if pm:
            close_lists()
            body.append(
                f'<section style="text-align:center;margin:20px 0;padding:24px;background:{t["bg"]};'
                f'border:1px dashed {t["border"]};border-radius:8px;color:{t["sub"]};font-size:14px;">'
                f"📷 此处插入配图：{html.escape(pm.group(1))}</section>"
            )
            i += 1
            continue

        hm = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if hm:
            close_lists()
            level = len(hm.group(1))
            txt = render_inline(hm.group(2), t)
            if level == 1:
                body.append(f'<h1 style="font-size:22px;font-weight:700;color:{t["primary"]};text-align:center;margin:28px 0 20px;line-height:1.5;">{txt}</h1>')
            elif level == 2:
                body.append(f'<h2 style="font-size:19px;font-weight:700;color:{t["primary"]};border-left:5px solid {t["accent"]};padding-left:12px;margin:28px 0 14px;line-height:1.5;">{txt}</h2>')
            else:
                body.append(f'<h3 style="font-size:17px;font-weight:600;color:{t["primary"]};margin:22px 0 10px;line-height:1.5;">{txt}</h3>')
            i += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            close_lists()
            body.append(f'<hr style="border:none;border-top:1px solid {t["border"]};margin:24px 0;"/>')
            i += 1
            continue

        if stripped.startswith(">"):
            close_lists()
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            body.append(
                f'<blockquote style="border-left:4px solid {t["accent"]};background:{t["bg"]};'
                f'margin:18px 0;padding:12px 16px;color:{t["sub"]};font-size:15px;line-height:1.8;">'
                f"{render_inline('<br/>'.join(l for l in quote_lines if l), t)}</blockquote>"
            )
            continue

        # 表格
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
            close_lists()
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            thead = "".join(
                f'<th style="border:1px solid {t["border"]};padding:8px 10px;background:{t["bg"]};'
                f'color:{t["primary"]};font-size:14px;font-weight:600;">{render_inline(c, t)}</th>'
                for c in header
            )
            trs = "".join(
                "<tr>"
                + "".join(
                    f'<td style="border:1px solid {t["border"]};padding:8px 10px;font-size:14px;color:{t["text"]};">{render_inline(c, t)}</td>'
                    for c in row
                )
                + "</tr>"
                for row in rows
            )
            body.append(
                f'<section style="overflow-x:auto;margin:18px 0;"><table style="border-collapse:collapse;width:100%;">'
                f"<thead><tr>{thead}</tr></thead><tbody>{trs}</tbody></table></section>"
            )
            continue

        ol_m = re.match(r"^(\d+)[.、]\s+(.*)$", stripped)
        ul_m = re.match(r"^[-*•]\s+(.*)$", stripped)
        if ol_m or ul_m:
            want = "ol" if ol_m else "ul"
            if not list_stack or list_stack[-1] != want:
                close_lists()
                list_stack.append(want)
                body.append(
                    f'<{want} style="padding-left:22px;margin:12px 0;color:{t["text"]};font-size:16px;line-height:1.9;">'
                )
            item = ol_m.group(2) if ol_m else ul_m.group(1)
            body.append(f"<li style=\"margin:6px 0;\">{render_inline(item, t)}</li>")
            i += 1
            continue

        close_lists()
        body.append(f'<p style="font-size:16px;color:{t["text"]};line-height:1.9;margin:14px 0;letter-spacing:0.5px;">{render_inline(stripped, t)}</p>')
        i += 1

    close_lists()

    header = (
        f'<section style="text-align:center;margin:10px 0 6px;color:{t["sub"]};font-size:13px;">'
        f"{'· ' + html.escape(title) + ' ·' if title else ''}</section>"
    )
    return (
        f'{header}<section style="max-width:100%;word-wrap:break-word;">{"".join(body)}</section>'
    )


def main():
    ap = argparse.ArgumentParser(description="Markdown → 微信公众号内联样式 HTML")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--title", default="")
    ap.add_argument("--theme", default="default", choices=list(THEMES))
    args = ap.parse_args()

    md = open(args.input, encoding="utf-8").read()
    # 去 frontmatter
    fm = re.match(r"^---\n.*?\n---\n?", md, re.S)
    if fm:
        md = md[fm.end():]
    html_out = md_to_html(md, args.title, args.theme)
    open(args.output, "w", encoding="utf-8").write(html_out)
    print(json.dumps({"ok": True, "output": args.output, "bytes": len(html_out.encode('utf-8'))}, ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(main())
