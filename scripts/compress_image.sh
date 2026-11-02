#!/usr/bin/env bash
# compress_image.sh — 图片压缩（macOS 版，替代 baoyu-compress-image 的 sharp 依赖）
# 自动探测 cwebp > sips；控制到目标体积以内。
#
# 用法: bash compress_image.sh <图片1> [图片2 ...] [--max-kb 300]
# 行为:
#   - 体积已达标 → 直接跳过（不动文件，HTML 引用不受影响）
#   - 超标 → 压缩后就地覆盖原路径（保持文件名不变，HTML 引用不变），原文件备份 *.orig
#   - cwebp 可用时输出 <名>.webp（HTML 引用需含 .webp 由 format 环节处理；默认优先保持原格式）
set -uo pipefail

MAX_KB=300
FILES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --max-kb) shift; MAX_KB="${1:-300}" ;;
    *) FILES+=("$1") ;;
  esac
  shift
done
[ "${#FILES[@]}" -eq 0 ] && { echo "用法: compress_image.sh <图片...> [--max-kb N]"; exit 2; }

MAX_BYTES=$((MAX_KB * 1024))
have_cwebp=0; command -v cwebp >/dev/null 2>&1 && have_cwebp=1

fsize() { stat -f%z "$1" 2>/dev/null || stat -c%s "$1" 2>/dev/null || echo 0; }

compress_one() {
  local f="$1" base size tmp
  [ -f "$f" ] || { echo "  ⚠️ 跳过（不存在）: $f"; return; }
  base="$(basename "$f")"
  size="$(fsize "$f")"

  # 已达标：跳过，不动文件
  if [ "$size" -le "$MAX_BYTES" ]; then
    echo "  ⏭ 已达标（$((size/1024))KB ≤ ${MAX_KB}KB）: $base"
    return
  fi

  cp "$f" "$f.orig"
  tmp="${f}.cmp"

  if [ "$have_cwebp" = "1" ] && [[ "$f" != *.png ]]; then
    # cwebp 只用于非 PNG（PNG 保留原格式以免微信编辑器兼容问题）
    local quality=82
    for _ in 1 2 3 4 5; do
      cwebp -quiet -q "$quality" "$f.orig" -o "$tmp" 2>/dev/null
      size="$(fsize "$tmp")"
      [ "$size" -le "$MAX_BYTES" ] && break
      quality=$((quality - 12)); [ "$quality" -lt 30 ] && quality=30
    done
    if [ "$size" -gt 0 ] && [ "$size" -lt "$(fsize "$f.orig")" ]; then
      mv "$tmp" "$f"
      echo "  ✅ WebP(q${quality}): $base → $((size/1024))KB（就地覆盖）"
    else
      rm -f "$tmp"; echo "  ⚠️ 压缩无收益，保留原图: $base"
    fi
  else
    # sips：PNG/JPG 均保持原格式，先缩尺寸再（JPEG 时）降质量
    local maxedge=1600
    sips --resampleHeightWidthMax "$maxedge" "$f.orig" --out "$tmp" >/dev/null 2>&1 || cp "$f.orig" "$tmp"
    if [[ "$f" != *.png ]]; then
      local q
      for q in 70 55 40; do
        size="$(fsize "$tmp")"
        [ "$size" -le "$MAX_BYTES" ] && break
        sips -s format jpeg -s formatOptions "$q" "$tmp" >/dev/null 2>&1
      done
    else
      # PNG 达不到目标再降一档分辨率
      size="$(fsize "$tmp")"
      if [ "$size" -gt "$MAX_BYTES" ]; then
        sips --resampleHeightWidthMax 1200 "$tmp" >/dev/null 2>&1
      fi
    fi
    size="$(fsize "$tmp")"
    if [ "$size" -gt 0 ] && [ "$size" -lt "$(fsize "$f.orig")" ]; then
      mv "$tmp" "$f"
      echo "  ✅ sips: $base → $((size/1024))KB（就地覆盖）"
    else
      rm -f "$tmp"; echo "  ⚠️ 压缩无收益，保留原图: $base"
    fi
  fi
}

echo "=== 图片压缩（目标 ≤${MAX_KB}KB）==="
for f in "${FILES[@]}"; do compress_one "$f"; done
echo "=== 完成（超限图原文件备份为 *.orig）==="
