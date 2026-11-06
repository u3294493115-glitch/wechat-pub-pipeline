#!/usr/bin/env bash
# fetch_stats.sh — 发布数据回流 v2.0.0
#
# 为什么 v2 要大改（v1 的两个硬伤）：
#   1) 本号是未认证个人订阅号，微信 datacube/* 全部接口返回 48001（api unauthorized）。
#      阅读数、粉丝数、已发布列表一个都拉不到。v1 的「自动拉取」在这台号上是死路，
#      而且失败时静默退出，会让人误以为「没数据」，其实是「没权限」。
#   2) v1 把 ori_page_read_count（原文页阅读次数）当成点赞写进台账，列语义是错的。
#
# v2 的做法：手工表是主路径，API 是备用分支。
#   你把后台数字抄进 data/stats_input.md 六列，本脚本负责算派生指标（打开率/分享率/
#   收藏率）、写 meta.stats、更新台账。接口若能用了（--api）仍可一键切回自动。
#
# 用法：
#   bash scripts/fetch_stats.sh --init                      生成/补全 data/stats_input.md 待填表
#   bash scripts/fetch_stats.sh [--dry-run]                 读表 → 回写 meta.stats → 更新台账
#   bash scripts/fetch_stats.sh --api [--dry-run]           试微信接口（未认证号会明确报 48001）
#   bash scripts/fetch_stats.sh --mark-published 2026-11-01 标记某篇已群发（写 meta.published_at）
#
# 边界：
#   - 没群发（meta.json 无 published_at）的文章一律跳过，草稿箱没有阅读数据。
#   - 手工表里留 `-` 的字段脚本不猜，派生指标算不出来就留空。
#   - 本脚本从不群发、不碰内容，只读 meta 写 stats 与台账。
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ARTICLES="${SKILL_DIR}/articles"
LEDGER="${SKILL_DIR}/_rsi_ledger.md"
INPUT="${SKILL_DIR}/data/stats_input.md"

MODE="run"; DRY=0; MARK=""
while [ $# -gt 0 ]; do
  case "$1" in
    --init)           MODE="init" ;;
    --api)            MODE="api" ;;
    --dry-run|-n)     DRY=1 ;;
    --mark-published) shift; MARK="${1:-}" ;;
    *) : ;;   # v1 的日期参数已废弃，忽略以保持命令兼容
  esac
  shift
done

mkdir -p "$(dirname "${INPUT}")"

if [ ! -f "${LEDGER}" ]; then echo "❌ 未找到台账 ${LEDGER}"; exit 1; fi

python3 - "${ARTICLES}" "${LEDGER}" "${INPUT}" "${MODE}" "${DRY}" "${MARK}" <<'PY'
# -*- coding: utf-8 -*-
import json, os, re, sys, glob, datetime

ARTICLES, LEDGER, INPUT, MODE, DRY, MARK = sys.argv[1:7]
DRY   = (DRY == "1")
TODAY = datetime.date.today().isoformat()

NEW_HEADER = "## 7. 发布数据（回流 · v2.0）"
COLS = ["归档目录", "群发日", "标题", "送达", "阅读人数", "阅读次数",
        "分享", "收藏", "点赞", "阅读来源占比"]


# ────────────────────────── 通用 ──────────────────────────
def read_json(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def published_dirs():
    """扫 articles/*/meta.json，只留已群发的。"""
    out = []
    for mp in sorted(glob.glob(os.path.join(ARTICLES, "*", "meta.json"))):
        d = read_json(mp)
        if not d or not d.get("published_at"):
            continue
        out.append((os.path.basename(os.path.dirname(mp)), d))
    return out


def num(v):
    """把我可能手滑写进去的 '1,234' '62%' '待填' 都吃下去；拿不准就返回 None。"""
    if v is None:
        return None
    s = str(v).strip().replace(",", "").replace("％", "%").replace("%", "")
    if s in ("", "-", "—", "待填", "?", "？", "无"):
        return None
    try:
        f = float(s)
        return int(f) if f == int(f) else round(f, 4)
    except Exception:
        return None


def pct(x):
    return "-" if x is None else f"{x * 100:.1f}%"


def derive(st):
    """派生指标。分母拿不到就留 None，绝不用假设值兜底。"""
    du, ru = st.get("delivered"), st.get("read_user")
    sh, fv, lk = st.get("share_count"), st.get("fav_count"), st.get("like_num")
    d = {}
    d["open_rate"] = round(ru / du, 4) if (du and ru is not None and du > 0) else None
    d["share_rate"] = round(sh / ru, 4) if (sh is not None and ru and ru > 0) else None
    d["fav_rate"] = round(fv / ru, 4) if (fv is not None and ru and ru > 0) else None
    d["like_rate"] = round(lk / ru, 4) if (lk is not None and ru and ru > 0) else None
    return d


def parse_sources(v):
    """'62/12/9/13/4' → {'session':62,...}；不成五段就返回 None，不硬凑。"""
    if not v or str(v).strip() in ("-", "—", "待填"):
        return None
    parts = [p for p in re.split(r"[/／,，]", str(v).strip()) if p.strip() != ""]
    if len(parts) != 5:
        return None
    keys = ["session", "moments", "chat", "look", "other"]
    vals = [num(p) for p in parts]
    if any(x is None for x in vals):
        return None
    return dict(zip(keys, vals))


# ────────────────────────── 模式：标记群发 ──────────────────────────
if MARK:
    mp = os.path.join(ARTICLES, MARK, "meta.json")
    if not os.path.isfile(mp):
        print(f"❌ 未找到 {mp}")
        sys.exit(1)
    d = read_json(mp) or {}
    d["published_at"] = TODAY
    if DRY:
        print(f"[dry-run] 将标记 {MARK} published_at={TODAY}")
    else:
        json.dump(d, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"✅ 已标记群发：{MARK}（published_at={TODAY}）")
    print("   下一步：bash scripts/fetch_stats.sh --init 生成待填表")
    sys.exit(0)


# ────────────────────────── 模式：--init ──────────────────────────
if MODE == "init":
    pubs = published_dirs()
    if not pubs:
        print("⚠️  articles/ 里没有已群发的文章（meta.json 缺 published_at）。")
        print("   刚发完先用：bash scripts/fetch_stats.sh --mark-published <归档目录名>")
        sys.exit(0)

    existing = set()
    if os.path.isfile(INPUT):
        for ln in open(INPUT, encoding="utf-8"):
            s = ln.strip()
            if not s.startswith("|"):
                continue
            c = [x.strip() for x in s.strip("|").split("|")]
            if c and c[0] and not re.fullmatch(r"[-:\s]+", c[0]) and c[0] != COLS[0]:
                existing.add(c[0])

    fresh = [(dn, d) for dn, d in pubs if dn not in existing]
    if not fresh and os.path.isfile(INPUT):
        print(f"✅ 待填表已是最新，无需补行：{INPUT}")
        sys.exit(0)

    if not os.path.isfile(INPUT):
        head = [
            "# 发布数据待填表（v2.0）",
            "",
            "> 什么时候填：群发后第 3 天抄一次（第 7 天想再看一次就覆盖同一行）。",
            "> 从哪抄：公众号后台 → 内容分析 → 单篇群发 → 点开对应标题。",
            "> 必填三列：**送达 / 阅读人数 / 分享**。其余留 `-`，脚本会跳过、不会瞎算。",
            "> 阅读来源占比：会话/朋友圈/聊天/看一看/其他，填百分比五段（如 `62/12/9/13/4`）。",
            ">   这一列不用每篇填，**一个月挑一篇**看看就行——数据量小时它大半是噪声。",
            "> 填完跑：`bash scripts/fetch_stats.sh`",
            "",
            "| " + " | ".join(COLS) + " |",
            "|" + "|".join(["------"] * len(COLS)) + "|",
        ]
        open(INPUT, "w", encoding="utf-8").write("\n".join(head) + "\n")
        print(f"✅ 已建待填表：{INPUT}")

    rows = [f"| {dn} | {d.get('published_at', '')} | {d.get('title', '')} | - | - | - | - | - | - | - |"
            for dn, d in fresh]
    if rows:
        txt = open(INPUT, encoding="utf-8").read().rstrip("\n")
        open(INPUT, "w", encoding="utf-8").write(txt + "\n" + "\n".join(rows) + "\n")
        print(f"✅ 补入 {len(rows)} 行待填：")
        for dn, d in fresh:
            print(f"   · {dn}  {d.get('title', '')}")
    print("\n填好后运行：bash scripts/fetch_stats.sh")
    sys.exit(0)


# ────────────────────────── 模式：--api（备用分支）──────────────────────────
if MODE == "api":
    import urllib.request

    def _read(p):
        try:
            return open(os.path.expanduser(p), encoding="utf-8").read().strip()
        except Exception:
            return ""

    appid = os.environ.get("WECHAT_APPID") or _read("~/.config/wechat/appid")
    secret = os.environ.get("WECHAT_SECRET") or _read("~/.config/wechat/secret")
    if not (appid and secret):
        print("⚠️  未找到 appid/secret（~/.config/wechat/ 或环境变量），无法走接口。")
        print("   这不影响主路径——用 data/stats_input.md 手工填即可。")
        sys.exit(0)

    def post(url, payload):
        req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())

    try:
        tok = json.loads(urllib.request.urlopen(
            "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential"
            f"&appid={appid}&secret={secret}", timeout=20).read().decode())
    except Exception as e:
        print(f"⚠️  取 access_token 异常：{e}")
        sys.exit(0)

    if "access_token" not in tok:
        print(f"⚠️  取 access_token 失败：{json.dumps(tok, ensure_ascii=False)}")
        print("   多半是 IP 白名单（家宽重播会变）或 secret 不对。跑 scripts/diagnose.py 看当前 IP。")
        sys.exit(0)

    AT = tok["access_token"]
    end = datetime.date.today()
    probes = {
        "getarticletotal": 6,
        "getusersummary": 6,
        "getarticlesummary": 6,
    }
    got = {}
    denied = []
    for ep, days in probes.items():
        try:
            r = post(f"https://api.weixin.qq.com/datacube/{ep}?access_token={AT}",
                     {"begin_date": (end - datetime.timedelta(days=days)).isoformat(),
                      "end_date": end.isoformat()})
        except Exception as e:
            print(f"   {ep}: 请求异常 {e}")
            continue
        code = r.get("errcode", 0)
        if code == 48001:
            denied.append(ep)
        elif code:
            print(f"   {ep}: errcode={code} {r.get('errmsg', '')}")
        else:
            got[ep] = r.get("list", [])

    if denied and not got:
        print("❌ 接口无权限（48001 api unauthorized）。")
        print("   本号是未认证个人订阅号，微信不开放 datacube/* 数据统计接口——")
        print("   阅读数、粉丝数、已发布列表都拉不到。这不是配置问题，是账号类型限制。")
        print("   → 请走主路径：bash scripts/fetch_stats.sh --init，手工填 data/stats_input.md")
        sys.exit(0)

    if not got:
        print("⚠️  接口通了但没有数据（近 6 天无群发，或数据有 1 天延迟）。")
        sys.exit(0)

    # 字段全量留着，不挑——以后有指标想回看，不用重拉。
    items = got.get("getarticletotal", [])
    merged = {}
    for it in items:
        t = (it.get("title") or "").strip()
        if t:
            merged.setdefault(re.sub(r"\s+", "", t), it)
    if not merged:
        print("⚠️  接口有权限但未返回图文数据。")
        sys.exit(0)

    pubs = published_dirs()
    hit = 0
    for dn, d in pubs:
        it = merged.get(re.sub(r"\s+", "", d.get("title", "")))
        if not it:
            continue
        st = {"source": "api", "fetched_at": TODAY, "raw": it}
        for k, v in (("read_user", it.get("int_page_read_user")),
                     ("read_count", it.get("int_page_read_count")),
                     ("share_count", it.get("share_count")),
                     ("fav_count", it.get("add_to_fav_count"))):
            st[k] = num(v)
        st["derived"] = derive(st)
        if DRY:
            print(f"[dry-run] {dn}: {st}")
        else:
            d["stats"] = st
            json.dump(d, open(os.path.join(ARTICLES, dn, "meta.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            print(f"✅ {dn}  {d.get('title', '')}  → meta.stats（api）")
        hit += 1
    print(f"\n接口模式回写 {hit} 篇。台账请跑一次普通模式汇总：bash scripts/fetch_stats.sh")
    sys.exit(0)


# ────────────────────────── 模式：run（主路径）──────────────────────────
if not os.path.isfile(INPUT):
    print(f"❌ 没有待填表 {INPUT}")
    print("   先跑：bash scripts/fetch_stats.sh --init")
    sys.exit(0)

# 解析手工表
records = []
for ln in open(INPUT, encoding="utf-8"):
    s = ln.strip()
    if not s.startswith("|"):
        continue
    c = [x.strip() for x in s.strip("|").split("|")]
    if not c or c[0] == COLS[0] or re.fullmatch(r"[-:\s]*", c[0]):
        continue
    c = (c + ["-"] * len(COLS))[:len(COLS)]
    records.append(dict(zip(COLS, c)))

if not records:
    print("⚠️  待填表里还没有数据行。")
    sys.exit(0)

filled = [r for r in records if any(num(r[k]) is not None for k in ("送达", "阅读人数", "分享", "收藏", "点赞"))]
if not filled:
    print("⚠️  待填表里所有行都还是 `-`，没有可回写的数字。")
    print("   去公众号后台抄满：送达 / 阅读人数 / 分享 三列就够。")
    sys.exit(0)

pubs = {dn: d for dn, d in published_dirs()}
ledger_rows = []
written = 0

for r in filled:
    dn = r["归档目录"]
    if dn not in pubs:
        print(f"⚠️  跳过 {dn}：articles/ 里没有这篇，或还没有 published_at")
        continue
    meta = pubs[dn]
    st = {
        "source": "manual",
        "fetched_at": TODAY,
        "delivered":   num(r["送达"]),
        "read_user":   num(r["阅读人数"]),
        "read_count":  num(r["阅读次数"]),
        "share_count": num(r["分享"]),
        "fav_count":   num(r["收藏"]),
        "like_num":    num(r["点赞"]),
    }
    st["derived"] = derive(st)
    src = parse_sources(r["阅读来源占比"])
    if src:
        st["sources"] = src

    hist = meta.get("stats_history") or []
    hist = [h for h in hist if h.get("fetched_at") != TODAY]
    hist.append(json.loads(json.dumps(st)))
    meta["stats"] = st
    meta["stats_history"] = hist[-8:]     # 只留最近 8 次采集，防文件膨胀

    if DRY:
        print(f"[dry-run] {dn} {r['标题']}: "
              f"打开率 {pct(st['derived']['open_rate'])}  分享率 {pct(st['derived']['share_rate'])}")
    else:
        json.dump(meta, open(os.path.join(ARTICLES, dn, "meta.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"✅ {dn}  {r['标题']}  → meta.stats"
              f"（打开率 {pct(st['derived']['open_rate'])}，分享率 {pct(st['derived']['share_rate'])}）")
    written += 1

    ledger_rows.append(
        f"| {r['群发日']} | {r['标题']} | "
        f"{'-' if st['delivered'] is None else int(st['delivered'])} | "
        f"{'-' if st['read_user'] is None else int(st['read_user'])} | "
        f"{pct(st['derived']['open_rate'])} | "
        f"{'-' if st['share_count'] is None else int(st['share_count'])} | "
        f"{pct(st['derived']['share_rate'])} | "
        f"{'-' if st['fav_count'] is None else int(st['fav_count'])} | "
        f"{'-' if st['like_num'] is None else int(st['like_num'])} | "
        f"{TODAY} | {dn} |"
    )

if DRY:
    print(f"\n[dry-run] 共 {written} 篇可回写，未落盘。")
    sys.exit(0)

if not ledger_rows:
    sys.exit(0)

# ── 重写台账第 7 节（v1 列语义有误，旧行仅在含真实数字时存档）──
txt = open(LEDGER, encoding="utf-8").read()
start = txt.find("## 7. 发布数据")
if start < 0:
    anchor = txt.find("## 8. 演进记录")
    start = anchor if anchor > 0 else len(txt)
    end = start
else:
    nxt = txt.find("\n## ", start + 5)
    end = nxt + 1 if nxt > 0 else len(txt)

old_block = txt[start:end] if start < len(txt) else ""

# 旧行抢救：v1 列是 日期|标题|阅读|点赞|采集日|归档，恰好 6 列；
# v2 新表是 11 列。按列数区分，否则新行会被自己当成旧行存档（回归 bug）。
salvaged = []
for ln in old_block.splitlines():
    s = ln.strip()
    if not s.startswith("|"):
        continue
    c = [x.strip() for x in s.strip("|").split("|")]
    if len(c) != 6:
        continue
    if c[0] in ("日期", "群发日") or re.fullmatch(r"[-:\s]*", c[0]):
        continue
    if c[2] in ("", "-", "待发"):
        continue
    salvaged.append(s)

note = [
    NEW_HEADER,
    "",
    "> 数据来源：`data/stats_input.md` 手工表（后台抄录）。本号是未认证个人订阅号，",
    "> 微信 `datacube/*` 接口返回 48001，**无法自动拉取**——不要指望这里出现自动同步的数字。",
    "> `打开率 = 阅读人数 ÷ 送达`；`分享率 = 分享次数 ÷ 阅读人数`。",
    "> 新号阶段（粉丝少）**只看分享率和收藏，别盯打开率**：分母太小，一个人就能让比例翻倍。",
    "",
    "| " + " | ".join(["群发日", "标题", "送达", "阅读人数", "打开率",
                        "分享", "分享率", "收藏", "点赞", "采集日", "归档目录"]) + " |",
    "|" + "|".join(["------"] * 11) + "|",
]

existing_body = []
for ln in old_block.splitlines():
    s = ln.strip()
    if not s.startswith("|"):
        continue
    c = [x.strip() for x in s.strip("|").split("|")]
    if len(c) < 11 or  c[0] in ("群发日", "日期") or re.fullmatch(r"[-:\s]*", c[0]):
        continue
    existing_body.append(s)

merged = {}
for ln in existing_body + ledger_rows:
    c = [x.strip() for x in ln.strip("|").split("|")]
    merged[c[-1] if len(c) >= 11 else c[0]] = ln     # 按归档目录去重，后写的覆盖

new_block = "\n".join(note + list(merged.values())) + "\n"

archive = ""
if salvaged:
    archive = ("\n## 7b. v1 旧表存档（列语义有误，勿引用）\n\n"
               "v1 把 `ori_page_read_count`（原文页阅读次数）当点赞写进了台账，"
               "下列原行仅作溯源，不要拿来算指标。\n\n"
               "```\n| 日期 | 标题 | 阅读 | 点赞(实为原文页阅读) | 采集日 | 归档目录 |\n"
               "|------|------|------|------|------|------|\n"
               + "\n".join(salvaged) + "\n```\n")

txt = txt[:start] + new_block + archive + ("\n" if end < len(txt) else "") + txt[end:]
open(LEDGER, "w", encoding="utf-8").write(txt)

print(f"\n✅ 台账已更新 {len(merged)} 行（{NEW_HEADER}）")
if salvaged:
    print(f"   旧表 {len(salvaged)} 行存档到 7b（原列语义有误，仅供参考）")
print("\n下一步（可选，一个月一次）：")
print("  打开后台单篇图文的「阅读来源」，判断是封面标题没吸引力，还是导语没让人想转发。")
print("  这一步没有接口，也不值得自动化——量小时看它只会把自己带偏。")
PY
