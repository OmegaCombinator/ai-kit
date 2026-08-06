#!/usr/bin/env python3
"""影响面计算：给定一批改动的 .ac 模块，输出"必须重验的依赖闭包"。

原理
----
Acorn 证书按（模块限定）名字解析声明；模块 M 的证书是否失效，取决于 M 的
源文本是否变化，以及 M 引用的依赖模块是否发生了会影响 M 的声明变化。
保守但机械可算的近似：改动模块 = 源 hash 变化的模块；受影响闭包 = 所有
（直接或间接）import 了任一改动模块的模块。闭包内的模块需要重放
（check --strict）或重搜（verify，若重放失败）。

本工具不调用 acorn 二进制，只做两件事：
  1. 扫描 src/**/*.ac 的 `from <module> import ...` 行建模块依赖 DAG；
  2. 对改动集合做反向 BFS 求下游闭包，按依赖序输出。

用法
----
  # 显式指定改动模块（文件路径或模块名均可）
  impact_closure.py --root <lib> --changed src/list/list_sum.ac,src/add.ac [--json]

  # 比较两份 manifest，自动得出改动模块（内容寻址：hash 变 = 改动）
  impact_closure.py --root <lib> --manifest-a build/manifest.json \
                    --manifest-b other/manifest.json [--json]

  # 输出拓扑序（依赖在前）的下游闭包模块名
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict, deque
from typing import Dict, List, Set

IMPORT_RE = re.compile(r"^\s*from\s+([A-Za-z0-9_.]+)\s+import\b", re.M)


def module_of(ac_path: str, root: str) -> str:
    """src/list/list_base.ac -> list.list_base ; src/nat.ac -> nat"""
    rel = os.path.relpath(ac_path, root)
    assert rel.endswith(".ac"), rel
    rel = rel[:-3]
    return rel.replace(os.sep, ".")


def build_dag(root: str) -> Dict[str, Set[str]]:
    """返回 {module: set(dependency modules)}。模块名与文件路径一一对应。"""
    dag: Dict[str, Set[str]] = {}
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".ac"):
                continue
            path = os.path.join(dirpath, fn)
            mod = module_of(path, root)
            deps: Set[str] = set()
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            except OSError as e:
                print(f"impact_closure: cannot read {path}: {e}", file=sys.stderr)
                sys.exit(2)
            for m in IMPORT_RE.findall(text):
                deps.add(m)
            dag[mod] = deps
    return dag


def load_manifest(path: str) -> Dict[str, str]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    modules = data.get("modules", {})
    if not isinstance(modules, dict):
        print(f"impact_closure: unexpected manifest shape in {path}", file=sys.stderr)
        sys.exit(2)
    return {k: str(v) for k, v in modules.items()}


def changed_from_manifests(a: Dict[str, str], b: Dict[str, str]) -> List[str]:
    keys = set(a) | set(b)
    return sorted(k for k in keys if a.get(k) != b.get(k))


def downstream_closure(dag: Dict[str, Set[str]], changed: List[str]) -> List[str]:
    """反向 BFS：从改动模块出发，沿"谁 import 我"传播。返回拓扑序（依赖在前）。"""
    reverse: Dict[str, Set[str]] = defaultdict(set)
    for mod, deps in dag.items():
        for d in deps:
            reverse[d].add(mod)

    # 只保留 DAG 中存在的模块
    alive = set(dag)
    changed = [c for c in changed if c in alive]
    if not changed:
        return []

    # 反向闭包（含自身）
    affected: Set[str] = set()
    q = deque(changed)
    while q:
        m = q.popleft()
        if m in affected:
            continue
        affected.add(m)
        for nxt in reverse.get(m, ()):
            if nxt not in affected:
                q.append(nxt)

    # 拓扑排序（Kahn）：只考虑 affected 子图，依赖在前
    indeg: Dict[str, int] = {m: 0 for m in affected}
    for m in affected:
        for d in dag[m]:
            if d in affected:
                indeg[m] += 1
    q = deque(sorted(m for m in affected if indeg[m] == 0))
    order: List[str] = []
    while q:
        m = q.popleft()
        order.append(m)
        for nxt in sorted(reverse.get(m, ())):
            if nxt in affected:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    q.append(nxt)
    if len(order) != len(affected):
        print("impact_closure: cycle detected in affected subgraph; "
              "falling back to BFS order", file=sys.stderr)
        return sorted(affected)
    return order


def main() -> int:
    ap = argparse.ArgumentParser(description="Acorn affected-module closure calculator")
    ap.add_argument("--root", required=True, help="acornlib root (dir containing src/)")
    ap.add_argument("--changed", default="", help="comma-separated module names or .ac paths")
    ap.add_argument("--manifest-a", help="manifest from one side (module -> hash)")
    ap.add_argument("--manifest-b", help="manifest from the other side")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = args.root
    src_root = os.path.join(root, "src")
    if not os.path.isdir(src_root):
        print(f"impact_closure: no src/ under {root}", file=sys.stderr)
        return 2

    dag = build_dag(src_root)

    changed: List[str] = []
    if args.manifest_a and args.manifest_b:
        ma = load_manifest(args.manifest_a)
        mb = load_manifest(args.manifest_b)
        changed = changed_from_manifests(ma, mb)
    if args.changed:
        for item in args.changed.split(","):
            item = item.strip()
            if not item:
                continue
            if item.endswith(".ac"):
                # 归一化: 接受 src/ 前缀或相对 root 的路径, 都转成模块名
                norm = item
                if norm.startswith("src/"):
                    norm = norm[len("src/"):]
                mod = norm[:-3].replace(os.sep, ".")
            else:
                # 已是模块名; 容忍用户误带 src. 前缀
                mod = item[len("src."):] if item.startswith("src.") else item
            changed.append(mod)

    order = downstream_closure(dag, changed)

    if args.json:
        print(json.dumps({
            "modules": len(dag),
            "changed": changed,
            "affected_closure": order,
            "affected_count": len(order),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"modules in DAG: {len(dag)}")
        print(f"changed modules: {len(changed)}")
        print(f"affected closure (topological order): {len(order)}")
        for m in order:
            print(f"  {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
