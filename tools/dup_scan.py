#!/usr/bin/env python3
"""dup_scan.py — 证书目标指纹索引与查重（goal registry 离线版）。

背景：并行战役中多个 agent 可能证明同一个引理（duplicate constant 事故发生过）。
证书 jsonl 每行 {goal, proof}，goal 是规范化后的定理陈述字符串——它就是目标的指纹。

用法:
    dup_scan.py --root <acornlib> [--normalize] [--json] [--limit 20]

输出:
    - 跨模块重复目标（不同模块声称同一 goal）
    - 模块内重复（同一模块内 goal 重复出现）
    - 目标总数 / 唯一目标数（可用于注册表规模估算）

归一化（--normalize）: 折叠空白 + 排序顶层类型实参顺序敏感的暂不处理——
默认只做空白折叠，保证指纹稳定。
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict


def iter_certs(root: str):
    """产出 (模块名, 证书文件路径)。"""
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".jsonl"):
                continue
            path = os.path.join(dirpath, fn)
            # src/<module>/certs/<file>.jsonl 或 src/certs/<file>.jsonl
            rel = os.path.relpath(path, root)
            parts = rel.split(os.sep)
            if len(parts) >= 3 and parts[-2] == "certs":
                mod = ".".join(parts[1:-2]) + (f".{fn[:-6]}" if len(parts) > 3 else "")
                if len(parts) == 3:
                    mod = fn[:-6]
                elif len(parts) > 3:
                    mod = ".".join(parts[1:-2]) + "." + fn[:-6]
            else:
                mod = fn[:-6]
            yield mod, path


def norm_goal(g: str) -> str:
    return re.sub(r"\s+", " ", g).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=20)
    args = ap.parse_args()

    index: dict = defaultdict(list)  # goal -> [(module, path, line)]
    total = 0
    files = 0
    for mod, path in iter_certs(args.root):
        try:
            with open(path, encoding="utf-8") as f:
                for ln, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    g = rec.get("goal")
                    if not g:
                        continue
                    total += 1
                    index[norm_goal(g)].append((mod, os.path.relpath(path, args.root), ln))
            files += 1
        except OSError:
            continue

    cross_module = []
    in_module = []
    for g, occ in index.items():
        mods = {o[0] for o in occ}
        if len(mods) > 1:
            cross_module.append((g, occ))
        elif len(occ) > 1:
            in_module.append((g, occ))

    cross_module.sort(key=lambda x: -len(x[1]))
    in_module.sort(key=lambda x: -len(x[1]))

    if args.json:
        print(json.dumps({
            "cert_files": files,
            "goals_total": total,
            "goals_unique": len(index),
            "cross_module_dups": len(cross_module),
            "in_module_dups": len(in_module),
            "cross_module_sample": [
                {"goal": g[:200], "occurrences": len(occ),
                 "modules": sorted({o[0] for o in occ})} for g, occ in cross_module[:args.limit]
            ],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"cert files: {files}")
        print(f"goals total: {total}, unique: {len(index)}")
        print(f"cross-module duplicate goals: {len(cross_module)}")
        print(f"in-module duplicate goals: {len(in_module)}")
        for g, occ in cross_module[:args.limit]:
            print(f"  [{len(occ)}x] {g[:120]}")
            for m, p, ln in occ[:4]:
                print(f"       {m} ({p}:{ln})")
        for g, occ in in_module[:args.limit]:
            print(f"  (in-module) [{len(occ)}x] {g[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
