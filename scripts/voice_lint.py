#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""voice_lint.py —— 口吻 + 事实双重机械体检

为什么要有这个脚本：同一个词（服气、不甘心）已经删了又写回来两次。
靠眼睛看不住，靠自觉也看不住，只能让机器每次拦一遍。

v2 新增两项（2026-11-02，用户第 N 次抓到编造之后）：
  ① 引语溯源 —— 正文引号里的内容必须在 00_sources.md 的 B 表里找得到。
     上一轮编造的正是一句「引号里的引语」（"我不甘心的就是这个"），
     禁词表永远扫不出来，只能靠"这句话到底存不存在"去扫。
  ② 技术黑话 —— 5 位错误码 / api unauthorized / cgi-bin 路径 / HTTP 状态码
     一律不许进正文。用户原话：「48001 是什么东西，阅读这能看懂吗？」
     要写就写现象：接口被拒、没权限、卡在账号类型上。

用法：
    python scripts/voice_lint.py <文章.md 或 02_drafts.json>
    python scripts/voice_lint.py --dir pipeline/2026-11-02/p1
    python scripts/voice_lint.py --dir <目录> --sources <台账.md>   # 手动指定台账

退出码：0 通过；1 有硬伤（禁词/编号/句长/感叹号/引语无源/技术黑话）；2 文件读不到
"""

import sys
import os
import re
import json
import argparse

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(SKILL_DIR, "config.json")

CN_NUM = "一二三四五六七八九十"
HEADING_RE = re.compile(r"^#{1,6}\s*(.+)$", re.M)

# 引号里的内容算引用（引别人的原话、引自己旧稿里的句子），不判口吻。
# 用等长占位符替换，保持字符位置不变，报行号时不跑偏。
QUOTE_RE = re.compile(r"「[^」\n]*」|『[^』\n]*』|\"[^\"\n]*\"|“[^”\n]*”")

# 硬核引语的最短长度（去标点后）。
# ⚠️ 阈值是拿真实案例标定的，别凭感觉调：
#   「我不甘心的就是这个」= 9 字 —— 当初编造的就是这句，**必须落在硬核区**（早期设 10 字，正好放它过去）
#   「这篇只有你能写」= 7 字、「帮我改改文字」= 6 字 —— 自撰强调/指令短语，只提醒
QUOTE_HARD_MIN = 8
QUOTE_SOFT_MIN = 6

# 技术黑话。命中即报错，不给"同段有翻译就放行"的口子——
# 因为规则本来就是"正文不写码，只写现象"。
TECH_PATTERNS = [
    (re.compile(r"(?<![\d.])\d{5}(?![\d.]|\s*(?:字|元|人|篇|个|次|年|月|日|天|小时|分钟|秒|%|万|条|份))"),
     "5 位错误码"),
    (re.compile(r"\berr(?:or)?[_\s-]?code\b", re.I), "错误码字段"),
    (re.compile(r"\bapi\s*[:_]?\s*unauthor\w*", re.I), "接口报错原文"),
    (re.compile(r"cgi-bin/[a-z0-9_/]+", re.I), "接口路径"),
    (re.compile(r"\b(?:datacube|freepublish|wxa|sns|user|material)/[a-z0-9_/]{3,}", re.I), "接口路径"),
    (re.compile(r"\b(?:HTTP|status)\s*[:=]?\s*[45]\d{2}\b", re.I), "HTTP 状态码"),
    (re.compile(r"\b(?:appid|app_?secret|access_?token)\b", re.I), "凭证字段名"),
]


def load_config():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def read_text(path):
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("content_markdown") or d.get("content") or ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def strip_noise(t):
    """去掉代码块、标题行、配图标记、引用行（免责声明）"""
    t = re.sub(r"```[\s\S]*?```", "", t)
    t = re.sub(r"^#{1,6}\s.*$", "", t, flags=re.M)
    t = re.sub(r"\[配图：[^\]]*\]", "", t)
    t = re.sub(r"^>\s.*$", "", t, flags=re.M)
    return t


def mask_quotes(t):
    if not QUOTE_RE.search(t):
        return t
    return QUOTE_RE.sub(lambda m: m.group(0)[0] + "口" * (len(m.group(0)) - 2) + m.group(0)[-1], t)


def norm_text(s):
    """去掉空白与中英标点，只留文字和字母数字，做宽容比对。

    台账里写「每个字都是想象出来的，没有一句是跟我有关系的。」
    正文里可能写成「每个字都是想象出来的 没有一句是跟我有关系的」，
    去掉标点后仍判为同一句。
    """
    return re.sub(r"""[\s\u3000·、，。；：！？「」『』“”"'（）()《》〈〉—\-…,.;:!?/\\|]""", "", s)


def split_sentences(t):
    parts = re.split(r"[。！？；\n]+", t)
    return [p.strip() for p in parts if p.strip()]


def find_hits(masked, words, orig):
    """在脱敏文本上找禁词（引号内不算），但报原始行文，方便定位改。"""
    hits = []
    mlines = masked.split("\n")
    olines = orig.split("\n")
    for w in words:
        if not w:
            continue
        for i, ln in enumerate(mlines):
            if w in ln:
                show = olines[i].strip()[:80] if i < len(olines) else ln.strip()[:80]
                hits.append((w, i + 1, show))
                break
    return hits


def find_aux(dirpath, explicit=None):
    """找事实台账。台账是引语溯源的唯一依据，没有它这项检查降级为提醒。"""
    if explicit:
        return explicit if os.path.exists(explicit) else None
    if not dirpath:
        return None
    for name in ("00_sources.md", "01_sources.md"):
        p = os.path.join(dirpath, name)
        if os.path.exists(p):
            return p
    return None


def check_quotes(raw, aux_text, exempt, aux_label="00_sources.md"):
    """正文引号里的内容，必须在台账里找得到。

    返回 (problems, warns)。台账不存在时全部降级为提醒——
    不能因为没建台账就把所有稿子卡死，但要在输出里吼一声。
    """
    problems, warns = [], []
    body = strip_noise(raw)
    if not QUOTE_RE.search(body):
        return problems, warns

    aux_norm = norm_text(aux_text) if aux_text else ""
    exempt_norm = {norm_text(e) for e in (exempt or []) if e}
    strict = bool(aux_norm)

    seen = set()
    short_miss = []          # 短引语攒起来，最后合并成一行，别刷屏
    for m in QUOTE_RE.finditer(body):
        whole = m.group(0)
        inner = whole[1:-1].strip()
        nq = norm_text(inner)
        if not nq or nq in seen:
            continue
        seen.add(nq)
        # 作者自撰的短语，显式豁免
        if nq in exempt_norm:
            continue
        if len(nq) < QUOTE_SOFT_MIN:
            continue
        if nq in aux_norm:
            continue

        line_no = body[: m.start()].count("\n") + 1
        snippet = inner[:40]

        if len(nq) < QUOTE_HARD_MIN:
            short_miss.append(f"「{snippet}」")
        elif strict:
            problems.append(
                f"[引语无源] 第~{line_no}行「{snippet}」→ 台账 {aux_label} 里查不到这句。"
                f"三选一：① 把出处补进 B 表 ② 改成转述（有人说过…）③ 自己说的话就删掉引号"
            )
        else:
            problems.append(
                f"[引语无源] 第~{line_no}行「{snippet}」→ 没有台账，无法核验，按编造处理。"
                f"先建 00_sources.md 再写"
            )

    if short_miss:
        warns.append(
            f"[短引语] {len(short_miss)} 处 ≤{QUOTE_HARD_MIN - 1} 字未收台账（多为自撰强调，可不管）："
            + " / ".join(short_miss[:5])
        )
    return problems, warns


def check_tech(body, allow):
    """技术黑话不许进正文。要写就写现象，不写码。"""
    problems = []
    allow_norm = {a.strip() for a in (allow or []) if a}
    lines = body.split("\n")
    for i, ln in enumerate(lines):
        for pat, label in TECH_PATTERNS:
            for m in pat.finditer(ln):
                token = m.group(0)
                if token in allow_norm:
                    continue
                problems.append(
                    f"[技术黑话] 第{i+1}行「{token}」({label}) → 读者看不懂。"
                    f"改成现象：接口被拒 / 没权限 / 卡在账号类型上"
                )
    return problems


def lint(path, cfg, aux_path=None, verbose=True):
    raw = read_text(path)
    masked = mask_quotes(raw)
    body = strip_noise(masked)
    bl = cfg.get("voice_blacklist", {})
    met = cfg.get("voice_metrics", {})
    tol = met.get("tolerance", {})

    problems, warns, notes = [], [], []

    # 1) 禁词
    for cat, words in bl.items():
        if cat.startswith("_") or not isinstance(words, list):
            continue
        for w, ln, line in find_hits(masked, words, raw):
            problems.append(f"[禁词/{cat}] 第{ln}行「{w}」→ {line}")

    # 2) 编号小标题（教程感）
    for m in HEADING_RE.finditer(masked):
        h = m.group(1).strip()
        if re.match(rf"^[{CN_NUM}]+\s*[、.．]", h) or re.match(rf"^第[{CN_NUM}]+步", h) or re.match(r"^\d+\s*[、.．]", h):
            problems.append(f"[编号小标题] 「{h}」→ 不是教方法的内容不许用编号")

    # 3) 句长
    sents = split_sentences(body)
    if sents:
        lens = [len(s) for s in sents]
        avg = sum(lens) / len(lens)
        mx = max(lens)
        avg_max = tol.get("avg_max", 24)
        max_max = tol.get("max_len_max", 68)
        if avg > avg_max:
            problems.append(f"[句长] 平均 {avg:.1f} 字 > {avg_max}（基准 {met.get('avg_sentence_len')}）")
        else:
            notes.append(f"平均句长 {avg:.1f} 字（基准 {met.get('avg_sentence_len')}，上限 {avg_max}）")
        if mx > max_max:
            worst = max(sents, key=len)
            problems.append(f"[最长句] {mx} 字 > {max_max}：「{worst[:40]}…」")
        else:
            notes.append(f"最长句 {mx} 字（基准 {met.get('max_sentence_len')}，上限 {max_max}）")
    else:
        notes.append("没拆出句子")

    # 4) 感叹号
    bang = body.count("！")
    bang_max = tol.get("exclamation_max", 1)
    if bang > bang_max:
        problems.append(f"[感叹号] {bang} 个 > {bang_max}（九份讲稿合计只有 2 个）")
    else:
        notes.append(f"感叹号 {bang} 个")

    # 5) 我/你比
    ni, nu = body.count("我"), body.count("你")
    ratio = (ni / nu) if nu else 999
    rmin = tol.get("ratio_min", 2.0)
    if nu and ratio < rmin:
        warns.append(f"[人称] 我 {ni} : 你 {nu} = {ratio:.1f}:1 < {rmin}（基准 {met.get('i_to_you_ratio')}:1）——别对着读者喊，多说自己")
    else:
        notes.append(f"我 {ni} : 你 {nu} = {ratio:.1f}:1")

    # 6) 自曝其短（弱检查：有没有带数字的具体难堪）
    num_pat = re.compile(r"[\d一二三四五六七八九十百]+\s*(%|篇|个|小时|次|块|万|行|天|分钟|秒)")
    if num_pat.search(body):
        notes.append("有具体数字（自曝其短的原料）")
    else:
        warns.append("[自曝其短] 全文没找到具体数字，可信度会掉——他的可信度靠『一年亏了50%』这类难看的具体数")

    # 7) 引语溯源
    aux_text = None
    if aux_path and os.path.exists(aux_path):
        with open(aux_path, encoding="utf-8") as f:
            aux_text = f.read()
    qp, qw = check_quotes(
        raw, aux_text, cfg.get("quote_exempt", []),
        aux_label=os.path.basename(aux_path) if aux_path else "00_sources.md",
    )
    problems.extend(qp)
    warns.extend(qw)
    if not qp and not qw:
        if aux_text:
            notes.append(f"引语全部有源（台账：{os.path.basename(aux_path)}）")
        else:
            warns.append("[台账] 这个目录没有 00_sources.md，引语只能提醒不能拦——建了才拦得住")

    # 8) 技术黑话
    problems.extend(check_tech(body, cfg.get("tech_jargon_allow", [])))

    if verbose:
        print(f"=== 口吻+事实体检 · {os.path.basename(path)} ===")
        for n in notes:
            print(f"   · {n}")
        for w in warns:
            print(f"  ? {w}")
        for p in problems:
            print(f"  ✗ {p}")
        print("=== " + ("FAIL" if problems else ("PASS(有提醒)" if warns else "PASS")) + " ===")

    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="文章 md 或 02_drafts.json")
    ap.add_argument("--dir", help="稿件目录，自动找 article_draft.md / 02_drafts.json / 00_sources.md")
    ap.add_argument("--sources", help="手动指定事实台账")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    cfg = load_config()
    targets = []
    aux = None
    if a.dir:
        for name in ("article_draft.md", "02_drafts.json"):
            p = os.path.join(a.dir, name)
            if os.path.exists(p):
                targets.append(p)
        aux = find_aux(a.dir, a.sources)
    elif a.target:
        targets = [a.target]
        aux = find_aux(os.path.dirname(os.path.abspath(a.target)) or ".", a.sources)
    if not targets:
        print("用法: python scripts/voice_lint.py <文件> | --dir <稿件目录>", file=sys.stderr)
        return 2

    rc = 0
    for t in targets:
        if not os.path.exists(t):
            print(f"读不到 {t}", file=sys.stderr)
            rc = max(rc, 2)
            continue
        rc = max(rc, lint(t, cfg, aux_path=aux, verbose=not a.quiet))
    return rc


if __name__ == "__main__":
    sys.exit(main())
