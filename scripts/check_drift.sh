#!/usr/bin/env bash
# check_drift.sh — 轻量自检（通用版）：配置完整性 / 台账章节 / 脚本健康
set -uo pipefail
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FAIL=0
say() { printf '%s\n' "$*"; }

say "=== rsi-wechat-publisher 自检 ==="

# 1. config.json
CFG="${SKILL_DIR}/config.json"
if [ -f "${CFG}" ]; then
  # Windows 适配：git bash 的 /c/... 路径原生 python 不认，转成 Windows 路径再传
  CFG_PY="$(cygpath -w "${CFG}" 2>/dev/null || printf '%s' "${CFG}")"
  python3 -c "
import json,sys
c=json.load(open(r'''${CFG_PY}''', encoding='utf-8'))
need=['ima_kb_id','author_name','wechat_account_name','articles_per_day','persona']
miss=[k for k in need if not c.get(k)]
if miss: print('❌ config.json 缺字段:', ', '.join(miss)); sys.exit(1)
print('✅ config.json 完整（库:', c.get('ima_kb_name') or c.get('ima_kb_id')[:16], '作者:', c.get('author_name'),'）')
" || FAIL=1
else
  say "❌ config.json 不存在 → 跑 scripts/setup_wizard.py"; FAIL=1
fi

# 2. 台账章节（8 节）
LEDGER="${SKILL_DIR}/_rsi_ledger.md"
if [ -f "${LEDGER}" ]; then
  miss=""
  for n in 1 2 3 4 5 6 7 8; do grep -q "^## ${n}\." "${LEDGER}" || miss="${miss} ${n}"; done
  [ -z "$miss" ] && say "✅ 台账 8 章节完整" || { say "❌ 台账缺章节:${miss}"; FAIL=1; }
else
  say "❌ _rsi_ledger.md 不存在（跑向导生成）"; FAIL=1
fi

# 3. 关键脚本在位
for s in setup_wizard.py diagnose.py md_to_html.py post_draft.py sync_to_ima_wb.py archive_article.sh compress_image.sh voice_lint.py render_check.py upload_image.py egress.py; do
  [ -f "${SKILL_DIR}/scripts/${s}" ] || { say "❌ 缺脚本 scripts/${s}"; FAIL=1; }
done
[ "${FAIL}" = 0 ] && say "✅ 12 个脚本在位（含 voice_lint / render_check / upload_image / egress）"

# 3.5 课程参考（v3.5）
for f in references/course-index.md references/yukunkun-7d-checklist.md; do
  [ -f "${SKILL_DIR}/${f}" ] || { say "❌ 缺 ${f}（查课程方法会退化成全盘搜索）"; FAIL=1; }
done
[ "${FAIL}" = 0 ] && say "✅ 课程索引与七维度清单在位"

# 4. 编码健康（BOM）
for f in "${SKILL_DIR}"/scripts/*; do
  head -c 3 "$f" | od -An -tx1 | grep -q 'ef bb bf' && { say "❌ ${f##*/} 含 BOM"; FAIL=1; }
done

[ "${FAIL}" = 0 ] && say "=== 全部 PASS ===" || say "=== 存在问题，按上面提示修复 ==="
exit "${FAIL}"
