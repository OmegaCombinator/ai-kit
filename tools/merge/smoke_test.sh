#!/usr/bin/env bash
# 合并工具冒烟测试（不依赖 acorn 二进制）
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DRIVER="$ROOT/tools/merge/manifest_merge_driver.py"
GATE="$ROOT/tools/merge/conflict_marker_gate.sh"
IMPACT="$ROOT/tools/merge/impact_closure.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $1" >&2; exit 1; }

# --- driver: 干净合并（per-key） ---
cat > "$TMP/base.json" <<'EOF'
{"version": 23, "modules": {"add": "h1", "list": "h2", "real": "h3"}}
EOF
cat > "$TMP/ours.json" <<'EOF'
{"version": 23, "modules": {"add": "h1", "list": "h2x", "real": "h3", "new_mod": "h4"}}
EOF
cat > "$TMP/theirs.json" <<'EOF'
{"version": 23, "modules": {"add": "h1", "list": "h2", "real": "h3y", "other_mod": "h5"}}
EOF
cp "$TMP/ours.json" "$TMP/a.json"
python3 "$DRIVER" "$TMP/base.json" "$TMP/a.json" "$TMP/theirs.json" >/dev/null 2>&1 \
  || fail "clean merge should exit 0"
python3 - "$TMP/a.json" <<'PY' || fail "clean merge result wrong"
import json,sys
m = json.load(open(sys.argv[1]))["modules"]
assert m["list"] == "h2x" and m["real"] == "h3y", m
assert m["new_mod"] == "h4" and m["other_mod"] == "h5", m
PY

# --- driver: 冲突（同 key 两侧不同改） ---
cat > "$TMP/b.json" <<'EOF'
{"version": 23, "modules": {"shared": "oursH"}}
EOF
cat > "$TMP/t2.json" <<'EOF'
{"version": 23, "modules": {"shared": "theirsH"}}
EOF
cp "$TMP/b.json" "$TMP/a2.json"
if python3 "$DRIVER" "$TMP/base.json" "$TMP/a2.json" "$TMP/t2.json" >/dev/null 2>&1; then
  fail "conflict merge should exit 1"
fi
grep -q '<<<<<<<' "$TMP/a2.json" || fail "conflict markers should be present"

# --- gate: 有标记失败，无标记通过 ---
mkdir -p "$TMP/bad" "$TMP/good"
printf '<<<<<<< HEAD\n{"a":1}\n=======\n{"b":2}\n>>>>>>> branch\n' > "$TMP/bad/c.jsonl"
(cd "$TMP/bad" && bash "$GATE" --all >/dev/null 2>&1) && fail "gate should fail on markers"
echo '{"a": 1}' > "$TMP/good/ok.jsonl"
(cd "$TMP/good" && bash "$GATE" --all >/dev/null 2>&1) || fail "gate should pass clean"

# --- impact: 模块名与路径两种写法等价 ---
if [ -d "$ROOT/../../../workspace/suzumio-lark/acornlib-omega/src" ]; then
  OMEGA="$(cd "$ROOT/../../../workspace/suzumio-lark/acornlib-omega" && pwd)"
  A=$(python3 "$IMPACT" --root "$OMEGA" --changed list.list_sum --json | python3 -c "import json,sys; print(json.load(sys.stdin)['affected_count'])")
  B=$(python3 "$IMPACT" --root "$OMEGA" --changed src/list/list_sum.ac --json | python3 -c "import json,sys; print(json.load(sys.stdin)['affected_count'])")
  [ "$A" = "$B" ] || fail "module name and path forms disagree ($A vs $B)"
fi

echo "OK: all merge-tool smoke tests passed"
