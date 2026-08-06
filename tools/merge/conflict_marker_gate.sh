#!/usr/bin/env bash
# CI 冲突标记门：任何被 git 跟踪的 .jsonl / manifest.json 出现 git 冲突标记即失败。
#
# 背景：合并流水线用 merge driver / 机械预处理合并证书与 manifest；如果结果里残留
# "<<<<<<<" 等标记（例如 merge=union 拼接、driver 无法解析、手工解决遗漏），
# 证书/清单文件已经是损坏状态，任何进一步验证都没有意义。此门必须在 CI 与
# 合并后强制运行（参考 beads 项目的 conflict-marker detection 做法）。
#
# 用法: bash tools/merge/conflict_marker_gate.sh [--all]
#   --all: 扫描工作树全部文件（含未跟踪），否则只扫 git 跟踪的文件。

set -u

SCAN_ALL=0
if [ "${1:-}" = "--all" ]; then
  SCAN_ALL=1
fi

found=0

if [ "$SCAN_ALL" = "1" ]; then
  files=$(find . -type f \( -name '*.jsonl' -o -name 'manifest.json' \) \
    -not -path './.git/*' 2>/dev/null)
else
  files=$(git ls-files | grep -E '\.jsonl$|manifest\.json$' 2>/dev/null)
fi

for f in $files; do
  if [ -f "$f" ] && grep -qE '^(<<<<<<<|=======|>>>>>>>)' "$f"; then
    echo "CONFLICT MARKERS in $f" >&2
    found=1
  fi
done

if [ "$found" = "1" ]; then
  echo "conflict_marker_gate: FAIL — conflict markers present in certificate/manifest files" >&2
  exit 1
fi

echo "conflict_marker_gate: OK — no conflict markers in certificate/manifest files"
exit 0
