#!/usr/bin/env python3
"""fix_certs.py — 合并树证书修复：按"源码来源"取对应侧完整证书。

原则（2026-08-07 实证）：
- fork 证书（HEAD，旧/新格式均可）在 0.2.6 下 0 searches 重放（2071/2071 实测）
- union/重生成的证书会丢失证明局部目标 → 不完整 → 搜索超时
- 所以：模块源码 == fork 版 → 取 fork 证书；== 上游版 → 取上游证书；
  混合版 → 尝试 fork 证书（源码近似），再不行则 keep 重生成 + 记录

对仍失败的模块：把其"被合并改动的传递依赖"也回退到 fork（如 functions 破坏 list_sum）。

用法:
    fix_certs.py --root <repo> --acorn <bin> --failing <module-files...>
"""

import argparse
import os
import subprocess
import sys


def git(root, *args, check=True):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr[:300]}")
    return r


def verify(root, acorn, path, timeout=300):
    r = subprocess.run([acorn, "verify", path], cwd=root, capture_output=True,
                       text=True, timeout=timeout)
    return r.returncode == 0


def restore(root, path, ref):
    try:
        if ref == ":0":
            # 索引 stage-0（合并版）：git checkout :0 在本环境不可用，改用 checkout-index
            git(root, "checkout-index", "-f", "--", path)
        else:
            git(root, "checkout", ref, "--", path)
    except RuntimeError:
        # 文件不在索引/ref 中（如证书是合并新增的）——保留现状即可
        pass


def cert_of(f):
    d, n = os.path.dirname(f), os.path.basename(f)[:-3]
    return (os.path.join("src", "certs", n + ".jsonl") if d == "src"
            else os.path.join(d, "certs", n + ".jsonl"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--acorn", default=os.environ.get("ACORN_BIN", "acorn"))
    ap.add_argument("--failing", nargs="+", required=True)
    ap.add_argument("--revert-deps", action="store_true",
                    help="仍失败时回退其改动的传递依赖到 fork")
    args = ap.parse_args()
    root = os.path.abspath(args.root)

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    from impact_closure import build_dag  # noqa

    # 改动模块集合（源码与 fork 是否一致）
    r = git(root, "diff", "--cached", "--name-only")
    changed = [f for f in r.stdout.splitlines() if f.endswith(".ac")]
    same_as_fork = {}
    for f in changed:
        a = git(root, "show", f"HEAD:{f}", check=False)
        b = git(root, "show", f":0:{f}", check=False)
        same_as_fork[f] = (a.returncode == 0 and b.returncode == 0 and a.stdout == b.stdout)

    dag = build_dag(os.path.join(root, "src"))

    for f in args.failing:
        if not os.path.isfile(os.path.join(root, f)):
            continue
        cf = cert_of(f)
        # 源码 == fork -> fork 证书；否则试上游证书
        if same_as_fork.get(f, False):
            if os.path.exists(os.path.join(root, cf)):
                restore(root, cf, "HEAD")
        else:
            if os.path.exists(os.path.join(root, cf)):
                restore(root, cf, "MERGE_HEAD")
        if verify(root, args.acorn, f):
            print(f"FIXED (certs): {f}")
            continue

        # 尝试 fork 源码（若合并版是上游的，回退源码到 fork 可能更稳）
        orig_src = None
        if not same_as_fork.get(f, False):
            restore(root, f, "HEAD")
            if os.path.exists(os.path.join(root, cf)):
                restore(root, cf, "HEAD")
            if verify(root, args.acorn, f):
                print(f"FIXED (reverted source to fork): {f}")
                continue
            restore(root, f, ":0")
            restore(root, cf, ":0")

        if not args.revert_deps:
            print(f"STILL FAILING: {f}")
            continue

        # 回退改动的传递依赖到 fork（如 functions -> list_sum）
        mod = f[4:-3].replace(os.sep, ".")
        deps, stack = set(), list(dag.get(mod, ()))
        while stack:
            d = stack.pop()
            if d in deps:
                continue
            deps.add(d)
            stack.extend(dag.get(d, ()))
        dep_files = ["src/" + d.replace(".", "/") + ".ac" for d in deps]
        dep_changed = [df for df in dep_files if df in same_as_fork]
        reverted = 0
        for df in dep_changed:
            restore(root, df, "HEAD")
            dcf = cert_of(df)
            if os.path.exists(os.path.join(root, dcf)):
                restore(root, dcf, "HEAD")
            reverted += 1
            if verify(root, args.acorn, f):
                print(f"FIXED (reverted {reverted} deps, last {df}): {f}")
                break
        else:
            print(f"STILL FAILING after dep reverts: {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
