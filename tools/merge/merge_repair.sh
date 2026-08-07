#!/usr/bin/env bash
# merge_repair.sh — 合并树逐模块修复收敛循环。
#
# 对合并后改动的每个模块（按依赖序，依赖在前）：verify（刷新 manifest + 重放）。
# 失败 -> 回退该模块源码+证书到 fork 版本(HEAD) 再 verify；
# 仍失败 -> 恢复合并版本(暂存 :0) 并记为 BLOCKED。
# 回退会级联：下游模块随后验证时如失败同样被回退。
#
# 用法: merge_repair.sh <acorn-bin> <changed-modules-file> <log-prefix>

set -u
ACORN="$1"
MODS_FILE="$2"
PREFIX="$3"
cd "$(git rev-parse --show-toplevel)"

OK_LOG="${PREFIX}-ok.log"
REVERT_LOG="${PREFIX}-reverted.log"
BLOCK_LOG="${PREFIX}-blocked.log"
: > "$OK_LOG"; : > "$REVERT_LOG"; : > "$BLOCK_LOG"

cert_of() { # module-file -> cert-file (root 与嵌套)
  local f="$1" dir name
  dir=$(dirname "$f")
  name=$(basename "$f" .ac)
  if [ "$dir" = "src" ]; then
    echo "src/certs/${name}.jsonl"
  else
    echo "${dir}/certs/${name}.jsonl"
  fi
}

n=0
total=$(wc -l < "$MODS_FILE")
while read -r f; do
  [ -f "$f" ] || continue
  n=$((n+1))
  cf=$(cert_of "$f")
  if timeout 240 "$ACORN" verify "$f" >/dev/null 2>&1; then
    echo "$f" >> "$OK_LOG"
  else
    git checkout HEAD -- "$f" 2>/dev/null
    [ -f "$cf" ] && git checkout HEAD -- "$cf" 2>/dev/null
    if timeout 240 "$ACORN" verify "$f" >/dev/null 2>&1; then
      echo "$f" >> "$REVERT_LOG"
      echo "REVERTED: $f"
    else
      git checkout :0 -- "$f" 2>/dev/null      # 恢复合并版本
      [ -f "$cf" ] && git checkout :0 -- "$cf" 2>/dev/null
      echo "$f" >> "$BLOCK_LOG"
      echo "BLOCKED: $f"
    fi
  fi
  if [ $((n % 25)) = 0 ]; then
    echo "progress $n/$total: ok=$(wc -l < "$OK_LOG") reverted=$(wc -l < "$REVERT_LOG") blocked=$(wc -l < "$BLOCK_LOG")"
  fi
done < "$MODS_FILE"

echo "DONE: ok=$(wc -l < "$OK_LOG") reverted=$(wc -l < "$REVERT_LOG") blocked=$(wc -l < "$BLOCK_LOG")"
