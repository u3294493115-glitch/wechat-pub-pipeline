#!/usr/bin/env bash
# archive_article.sh — rsi-wechat 文章归档（WorkBuddy/macOS 版）
# 把已进草稿箱（或本地降级包）的文章归档到 SKILL_DIR/articles/<日期>[-n]/，本地 git commit，有 remote 则 push。
#
# 用法:
#   bash archive_article.sh <YYYY-MM-DD> <产物目录> [--dry-run]
#   产物目录默认 <PROJECT_ROOT>/pipeline/<日期>
#
# 归档目录规则（同日多篇自动编号，绝不覆盖）:
#   articles/<日期>/   articles/<日期>-2/   articles/<日期>-3/ ...
#
# 多篇来源（优先级）:
#   1) <产物目录>/p*/format/manifest.json + 根 format/manifest.json
#   2) 扫描 <产物目录>/p*/format/article*.md
set -uo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="$(cd "${SKILL_DIR}/../../.." && pwd)"

DRY_RUN=0
ARGS=()
for a in "$@"; do
  case "$a" in
    --dry-run|-n) DRY_RUN=1 ;;
    *) ARGS+=("$a") ;;
  esac
done
DATE="${ARGS[0]:-$(date +%Y-%m-%d)}"
PIPELINE_DIR="${ARGS[1]:-${PROJECT_ROOT}/pipeline/${DATE}}"

REPO_REMOTE="${RSI_GIT_REMOTE:-origin}"
BRANCH="${RSI_REMOTE_BRANCH:-main}"
LOCAL_BRANCH="$(git -C "${SKILL_DIR}" symbolic-ref --short HEAD 2>/dev/null || echo main)"

echo "=== rsi-wechat 文章归档（WorkBuddy 版）==="
echo "日期: ${DATE}"
echo "产物目录: ${PIPELINE_DIR}"

[ -d "${PIPELINE_DIR}" ] || { echo "❌ 产物目录不存在: ${PIPELINE_DIR}" >&2; exit 1; }

json_escape() {
  printf '%s' "$1" | python3 -c 'import json,sys; sys.stdout.write(json.dumps(sys.stdin.read())[1:-1])' 2>/dev/null \
    || printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

next_dest() {
  local d="${SKILL_DIR}/articles/${DATE}"
  if [ ! -e "${d}" ]; then printf '%s' "${d}"; return; fi
  local n=2
  while [ -e "${SKILL_DIR}/articles/${DATE}-${n}" ]; do n=$((n+1)); done
  printf '%s' "${SKILL_DIR}/articles/${DATE}-${n}"
}

# 收集清单：JSONL 格式（每行一个 JSON 对象，避免 tab 分列脆弱性）
LIST_FILE="$(mktemp)"
trap 'rm -f "${LIST_FILE}"' EXIT

collect_from_manifest() {
  local mf="$1"
  python3 - "$mf" "$(dirname "$mf")" >> "${LIST_FILE}" <<'PY'
import json, sys, os
mf, fmt_dir = sys.argv[1], sys.argv[2]
try:
    data = json.load(open(mf, encoding="utf-8"))
except Exception:
    data = []
if isinstance(data, dict):
    data = data.get("articles", [])
for it in data:
    def resolve(p, default):
        if not p: p = default
        if not p: return ""
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(fmt_dir, p))
    print(json.dumps({
        "article": resolve(it.get("article"), "article.md"),
        "html": resolve(it.get("html"), ""),
        "cover": resolve(it.get("cover"), "imgs/cover.png"),
        "title": (it.get("title") or "").strip(),
        "media_id": (it.get("media_id") or "").strip(),
        "qa_score": str(it.get("qa_score") or ""),
    }, ensure_ascii=False))
PY
}

# 1) 各篇 manifest
for mf in "${PIPELINE_DIR}"/p*/format/manifest.json "${PIPELINE_DIR}"/format/manifest.json; do
  [ -f "$mf" ] && collect_from_manifest "$mf"
done

# 2) 回退：扫描 article*.md
if [ ! -s "${LIST_FILE}" ]; then
  while IFS= read -r md; do
    dir="$(dirname "$md")"
    cov=""; [ -f "${dir}/imgs/cover.png" ] && cov="${dir}/imgs/cover.png"
    htm=""; [ -f "${dir}/article.html" ] && htm="${dir}/article.html"
    printf '{"article": "%s", "html": "%s", "cover": "%s", "title": "", "media_id": "", "qa_score": ""}\n' \
      "${md//\"/\\\"}" "${htm//\"/\\\"}" "${cov//\"/\\\"}" >> "${LIST_FILE}"
  done < <(find "${PIPELINE_DIR}"/p*/format "${PIPELINE_DIR}/format" -maxdepth 1 -type f -name 'article*.md' 2>/dev/null | sort)
fi

[ -s "${LIST_FILE}" ] || { echo "⚠️ 未找到终稿 markdown，跳过" >&2; exit 1; }

# 逐行读取 JSONL 的辅助函数：jsonl_get <行> <字段>
jsonl_get() { printf '%s' "$1" | python3 -c 'import json,sys;print(json.load(sys.stdin).get(sys.argv[1],""))' "$2" 2>/dev/null; }

TOTAL="$(grep -c '' "${LIST_FILE}")"
echo "发现 ${TOTAL} 篇待归档"

if [ "${DRY_RUN}" = "1" ]; then
  echo "--- [dry-run] 计划归档（不写入）---"
  n=1
  while IFS= read -r LINE; do
    [ -z "${LINE}" ] && continue
    MD="$(jsonl_get "${LINE}" article)"
    TITLE="$(jsonl_get "${LINE}" title)"
    MID="$(jsonl_get "${LINE}" media_id)"
    QA="$(jsonl_get "${LINE}" qa_score)"
    printf '  [%d] %s | 标题:%s | media_id:%s | qa:%s\n' "$n" "${MD}" "${TITLE:-<推断>}" "${MID:-<无>}" "${QA:-<无>}"
    n=$((n+1))
  done < "${LIST_FILE}"
  echo "=== [dry-run] 结束 ==="
  exit 0
fi

# SKILL_DIR 需是 git 仓库（首次自动 init）
if ! git -C "${SKILL_DIR}" rev-parse git-dir >/dev/null 2>&1; then
  git -C "${SKILL_DIR}" init -q
  echo "ℹ️ 已在 SKILL_DIR 初始化 git 仓库（本地归档）"
fi

ARCHIVED=(); TITLES=()
while IFS= read -r LINE; do
  [ -z "${LINE}" ] && continue
  MD="$(jsonl_get "${LINE}" article)"
  HTM="$(jsonl_get "${LINE}" html)"
  COV="$(jsonl_get "${LINE}" cover)"
  TITLE="$(jsonl_get "${LINE}" title)"
  MID="$(jsonl_get "${LINE}" media_id)"
  QA="$(jsonl_get "${LINE}" qa_score)"
  [ -z "${MD}" ] && [ -z "${HTM}" ] && continue
  DEST="$(next_dest)"
  mkdir -p "${DEST}/images"
  REL_DEST="${DEST#${SKILL_DIR}/}"

  ok=0
  [ -n "${MD}" ] && [ -f "${MD}" ] && { cp "${MD}" "${DEST}/article.md"; ok=1; }
  [ -n "${HTM}" ] && [ -f "${HTM}" ] && cp "${HTM}" "${DEST}/article.html"
  [ -n "${COV}" ] && [ -f "${COV}" ] && cp "${COV}" "${DEST}/cover.png"
  # 配图目录
  IMG_SRC="$(dirname "${MD:-${HTM}}")/imgs"
  if [ -d "${IMG_SRC}" ]; then
    find "${IMG_SRC}" -maxdepth 1 -type f \
      \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' \) \
      ! -iname 'cover*' -exec cp {} "${DEST}/images/" \; 2>/dev/null || true
  fi
  # 本地降级包一并带走
  LP="$(dirname "${MD:-${HTM}}")/local-package"
  [ -d "${LP}" ] && cp -R "${LP}" "${DEST}/local-package"

  if [ "$ok" = "0" ] && [ ! -f "${DEST}/article.html" ]; then
    echo "   ⚠️ 正文缺失，跳过: ${MD}" >&2
    rm -rf "${DEST}" 2>/dev/null || true
    continue
  fi

  if [ -z "${TITLE}" ]; then
    TITLE="$(grep -m1 '^# \|^title:' "${DEST}/article.md" 2>/dev/null | sed -E 's/^# //; s/^title:[[:space:]]*//' || true)"
  fi
  [ -z "${TITLE}" ] && TITLE="${DATE}"

  cat > "${DEST}/meta.json" <<EOF
{
  "date": "${DATE}",
  "title": "$(json_escape "${TITLE}")",
  "source_pipeline": "${PIPELINE_DIR}",
  "media_id": "$(json_escape "${MID}")",
  "qa_score": "$(json_escape "${QA}")",
  "archived_at": "$(date -Iseconds)",
  "files": {
    "article": "article.md",
    "html": "article.html",
    "cover": "cover.png",
    "images_dir": "images/"
  }
}
EOF
  echo "   ✅ 已归档: ${REL_DEST} （${TITLE}）"
  ARCHIVED+=("${REL_DEST}"); TITLES+=("${TITLE}")
done < "${LIST_FILE}"

[ "${#ARCHIVED[@]}" -eq 0 ] && { echo "⚠️ 没有成功归档的文章" >&2; exit 1; }

# git commit
cd "${SKILL_DIR}"
for d in "${ARCHIVED[@]}"; do git add "${d}" >/dev/null 2>&1 || true; done
if git diff --cached --quiet 2>/dev/null; then
  echo "ℹ️ 无变更需提交（可能已归档过）"
else
  if [ "${#ARCHIVED[@]}" -eq 1 ]; then
    MSG="article: ${TITLES[0]} (${DATE})"
  else
    MSG="archive ${DATE}: ${#ARCHIVED[@]} 篇（${TITLES[0]} 等）"
  fi
  git commit -q -m "${MSG}" && echo "✅ 已提交: ${MSG}"
fi

# push（仅当配置了 remote）
if git remote get-url "${REPO_REMOTE}" >/dev/null 2>&1; then
  PUSH_OK=0
  # 远端有更新时先 rebase
  git fetch "${REPO_REMOTE}" "${BRANCH}" >/dev/null 2>&1 || true
  if git rev-parse "${REPO_REMOTE}/${BRANCH}" >/dev/null 2>&1; then
    git rebase "${REPO_REMOTE}/${BRANCH}" >/dev/null 2>&1 || echo "   ⚠️ rebase 失败，直接尝试 push"
  fi
  for attempt in 1 2 3; do
    if GIT_TERMINAL_PROMPT=0 git -c http.connectTimeout=30 push "${REPO_REMOTE}" "${LOCAL_BRANCH}:${BRANCH}" 2>/dev/null; then
      echo "✅ 已推送到 ${REPO_REMOTE}/${BRANCH}"; PUSH_OK=1; break
    fi
    echo "   ⚠️ 推送尝试 ${attempt} 失败" >&2
    [ "${attempt}" -lt 3 ] && sleep 5
  done
  [ "${PUSH_OK}" = "0" ] && { echo "⚠️ 推送失败（本地已归档，稍后可重试）" >&2; exit 2; }
else
  echo "ℹ️ 未配置 ${REPO_REMOTE} remote，仅本地归档（如需推 GitHub: cd ${SKILL_DIR} && git remote add origin <url>）"
fi

echo "=== 归档完成 ==="
