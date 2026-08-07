#!/usr/bin/env python3
"""unblock_merge.py — 合并树 BLOCKED 模块的第二层收敛。

merge_repair.sh 中"合并版与 fork 版都验证失败"的模块，失败根源通常是
其被合并改动的依赖（fork 版证明引用旧依赖语义）。本脚本对每个 blocked 模块：
按依赖序（近到远）逐个把"被合并改动的依赖"回退到 fork 版本，重试验证该模块，
直到它通过。回退级联由下游模块后续验证自然处理。

用法:
    unblock_merge.py --root <repo> --acorn <bin> --blocked a,b,c [--max-reverts N]
"""

import argparse
import os
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--acorn", default=os.environ.get("ACORN_BIN", "acorn"))
    ap.add_argument("--blocked", required=True, help="逗号分隔的 blocked 模块文件路径")
    ap.add_argument("--max-reverts", type=int, default=50)
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "merge"))
    from impact_closure import build_dag

    dag = build_dag(os.path.join(root, "src"))
    # 被合并改动的模块集合（暂存 vs HEAD）
    changed = set()
    r = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=root,
                       capture_output=True, text=True)
    for f in r.stdout.splitlines():
        if f.endswith(".ac") and f.startswith("src/"):
            changed.add(f[4:-3].replace(os.sep, "."))

    def verify(mod_file):
        return subprocess.run([args.acorn, "verify", mod_file], cwd=root,
                              capture_output=True, text=True, timeout=600).returncode == 0

    blocked_files = [b.strip() for b in args.blocked.split(",") if b.strip()]
    total_reverts = 0
    for bf in blocked_files:
        if not os.path.isfile(os.path.join(root, bf)):
            print(f"skip missing {bf}", file=sys.stderr)
            continue
        mod = bf[4:-3].replace(os.sep, ".")
        if verify(bf):
            print(f"OK already: {bf}")
            continue
        # 收集该模块的传递依赖（DAG 反向：先依赖后）
        deps = set()
        stack = list(dag.get(mod, ()))
        while stack:
            d = stack.pop()
            if d in deps or d == mod:
                continue
            deps.add(d)
            stack.extend(dag.get(d, ()))
        # 只考虑被合并改动的依赖，按依赖序（近到远 = 反拓扑？用 DAG 前向顺序）
        dep_order = []
        seen = set()
        for d in sorted(deps, key=lambda x: len(x)):
            if d in changed and d not in seen:
                seen.add(d)
                dep_order.append(d)
        reverted = 0
        for d in dep_order:
            if total_reverts >= args.max_reverts:
                print(f"STOP: max reverts reached at {bf}", file=sys.stderr)
                return 1
            df = os.path.join("src", d.replace(".", os.sep) + ".ac")
            r = subprocess.run(["git", "checkout", "HEAD", "--", df], cwd=root,
                               capture_output=True, text=True)
            cf = os.path.join("src", d.replace(".", os.sep), "certs",
                              d.rsplit(".", 1)[-1] + ".jsonl")
            if os.path.isfile(os.path.join(root, cf)):
                subprocess.run(["git", "checkout", "HEAD", "--", cf], cwd=root,
                               capture_output=True, text=True)
            elif os.path.isfile(os.path.join(root, "src", "certs", d.rsplit(".",1)[-1] + ".jsonl")):
                subprocess.run(["git", "checkout", "HEAD", "--",
                                os.path.join("src", "certs", d.rsplit(".",1)[-1] + ".jsonl")],
                               cwd=root, capture_output=True, text=True)
            total_reverts += 1
            reverted += 1
            if verify(bf):
                print(f"UNBLOCKED {bf} after reverting {reverted} dep(s) (last: {d})")
                break
        else:
            print(f"STILL BLOCKED: {bf} after reverting {len(dep_order)} deps", file=sys.stderr)
    print(f"done: {total_reverts} total dependency reverts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
