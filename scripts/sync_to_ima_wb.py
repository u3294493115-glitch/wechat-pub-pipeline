#!/usr/bin/env python3
"""sync_to_ima_wb.py — 把归档文章以 Markdown 上传到 IMA 知识库（WorkBuddy 版）。
流程（ima-mcp 同协议直调 API，凭证 ~/.config/ima/）：
  check_repeated_names → create_media → COS 上传 → add_knowledge
用法: python3 sync_to_ima_wb.py <articles根目录> [日期]
"""
import json
import os
import sys
import tempfile
import time
import urllib.request

CRED = os.path.expanduser("~/.config/ima")
CLIENT_ID = open(os.path.join(CRED, "client_id")).read().strip()
API_KEY = open(os.path.join(CRED, "api_key")).read().strip()
# 从 config.json 读个人配置（向导生成）；环境变量可覆盖
_CFG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
try:
    _CFG = json.load(open(_CFG_PATH, encoding="utf-8"))
except Exception:
    _CFG = {}
KB_ID = os.environ.get("IMA_KB_ID") or _CFG.get("ima_kb_id") or ""
FOLDER_ID = os.environ.get("IMA_FOLDER_ID") or _CFG.get("ima_folder_articles") or KB_ID
if not KB_ID:
    print("❌ 未配置 ima_kb_id（跑 scripts/setup_wizard.py 或手改 config.json）")
    sys.exit(2)

BASE = "https://ima.qq.com/openapi/wiki/v1/"

# 本机代理对 ima API 可能 502——直连，绕过系统代理
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api(path, body):
    url = BASE + path
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Content-Type": "application/json",
        "ima-openapi-clientid": CLIENT_ID,
        "ima-openapi-apikey": API_KEY,
    })
    try:
        with _OPENER.open(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"code": e.code, "msg": str(e)}


def cos_put(cred, fpath, content_type):
    """COS XML API PUT 上传（标准 q-sign-algorithm=sha1 签名，FormatString 含 host）。"""
    import hashlib, hmac as _hmac
    import urllib.parse

    host = f"{cred['bucket_name']}.cos.{cred['region']}.myqcloud.com"
    path = "/" + cred["cos_key"]
    url = f"https://{host}{path}"
    data = open(fpath, "rb").read()

    def q(s):
        return urllib.parse.quote(s, safe="-_.~")

    headers_to_sign = {"host": host}
    hl = ";".join(sorted(q(k) for k in headers_to_sign))
    hs = "&".join(f"{q(k)}={q(v)}" for k, v in sorted(headers_to_sign.items()))

    st, et = str(cred["start_time"]), str(cred["expired_time"])
    key_time = f"{st};{et}"
    sign_key = _hmac.new(cred["secret_key"].encode(), key_time.encode(), hashlib.sha1).hexdigest()
    format_string = f"put\n{path}\n\n{hs}\n"
    string_to_sign = f"sha1\n{key_time}\n{hashlib.sha1(format_string.encode()).hexdigest()}\n"
    signature = _hmac.new(sign_key.encode(), string_to_sign.encode(), hashlib.sha1).hexdigest()
    authz = (f"q-sign-algorithm=sha1&q-ak={cred['secret_id']}&q-sign-time={key_time}&q-key-time={key_time}"
             f"&q-header-list={hl}&q-url-param-list=&q-signature={signature}")

    req = urllib.request.Request(url, data=data, method="PUT", headers={
        "Content-Type": content_type,
        "x-cos-security-token": cred.get("token", ""),
        "Authorization": authz})
    with _OPENER.open(req, timeout=120) as resp:
        return resp.status


def normalize_article(art_dir):
    """生成规范 Markdown 内容（标题+元信息+摘要+正文）。"""
    meta = json.load(open(os.path.join(art_dir, "meta.json"), encoding="utf-8"))
    md = open(os.path.join(art_dir, "article.md"), encoding="utf-8").read()
    # 去 frontmatter
    import re
    m = re.match(r"^---\n.*?\n---\n?", md, re.S)
    if m:
        md = md[m.end():]
    digest = meta.get("digest") or (json.load(open(os.path.join(art_dir, "..", ".."), encoding="utf-8")) if False else "")
    title = meta.get("title", "untitled")
    head = (f"# {title}\n\n"
            f"> **作者**：杨教练　|　**来源**：万丰金融·AI量化杨教练　|　**归档日期**：{meta.get('date','')}\n\n"
            f"> **质检分**：{meta.get('qa_score','—')}\n\n---\n\n")
    return title, head + md.strip() + "\n"


def upload_one(name, content, size):
    # 1) create_media
    cm = api("create_media", {
        "file_name": name, "file_size": size, "content_type": "text/markdown",
        "knowledge_base_id": KB_ID, "file_ext": "md", "folder_id": FOLDER_ID})
    if cm.get("code") != 0:
        return f"create_media 失败: {cm.get('msg', cm)}"
    d = cm["data"]
    mid, cred, cos_key = d.get("media_id", ""), d.get("cos_credential", {}), d.get("cos_credential", {}).get("cos_key", "")

    # 2) COS 上传
    tmp = os.path.join(tempfile.gettempdir(), f"ima_upload_{int(time.time()*1000)}.md")
    open(tmp, "w", encoding="utf-8").write(content)
    try:
        cos_put(cred, tmp, "text/markdown")
    except Exception as e:
        os.remove(tmp)
        return f"COS 上传失败: {e}"

    # 3) add_knowledge
    ak = api("add_knowledge", {
        "media_type": 7, "media_id": mid, "title": name,
        "knowledge_base_id": KB_ID, "folder_id": FOLDER_ID,
        "file_info": {"cos_key": cos_key, "file_size": size, "file_name": name}})
    if ak.get("code") != 0:
        return f"add_knowledge 失败: {ak.get('msg', ak)}"
    os.remove(tmp)
    return None


def main():
    articles_root = sys.argv[1]
    date_prefix = sys.argv[2] if len(sys.argv) > 2 else ""
    ok, fail = 0, 0
    for d in sorted(os.listdir(articles_root)):
        if date_prefix and not d.startswith(date_prefix):
            continue
        adir = os.path.join(articles_root, d)
        if not (os.path.isfile(os.path.join(adir, "article.md")) and os.path.isfile(os.path.join(adir, "meta.json"))):
            continue
        title, content = normalize_article(adir)
        name = f"{d}_{title}.md"[:80].replace("/", "_")
        size = len(content.encode("utf-8"))
        print(f"[{d}] {title} ({size}B) …", end=" ")
        err = upload_one(name, content, size)
        if err:
            print(f"❌ {err}"); fail += 1
        else:
            print("✅"); ok += 1
        time.sleep(0.5)
    print(f"=== IMA 同步完成: 成功 {ok} / 失败 {fail} ===")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
