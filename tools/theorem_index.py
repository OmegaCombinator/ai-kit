#!/usr/bin/env python3
"""theorem_index.py — 基于 `acorn export` 的定理索引（acorn-tools §7 轻量实现）。

`acorn export --full` 已能导出全部定义/定理/类型 + 证明依赖（JSONL）。
本工具消费该导出，构建可查询的定理索引：
- 全部公共定理（名字、模块、参数、陈述摘要）
- 按名字/关键词搜索
- 证明依赖统计（哪个定理被引用最多 = 核心基础设施）
- 孤立定理（无人引用）

用法:
    theorem_index.py --export-dir <acorn export --full 输出目录> [--search <kw>]
                     [--top <N>] [--json]
"""

import argparse
import glob
import json
import os
import sys


def load_export(export_dir: str):
    """读取 export 目录里的所有 jsonl（defs/theorems/types）。"""
    records = []
    for path in sorted(glob.glob(os.path.join(export_dir, "**", "*.jsonl"), recursive=True)):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export-dir", required=True)
    ap.add_argument("--search", default="", help="按名字/陈述子串过滤")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    recs = load_export(args.export_dir)
    if not recs:
        print(f"theorem_index: no records under {args.export_dir}", file=sys.stderr)
        return 2

    # 结构探测
    sample = recs[0]
    keys = list(sample.keys())
    name_key = next((k for k in ("name", "id", "theorem", "decl") if k in sample), keys[0])

    if args.search:
        hits = [r for r in recs if args.search.lower() in
                json.dumps(r, ensure_ascii=False).lower()]
        print(f"search '{args.search}': {len(hits)} hits")
        for r in hits[:20]:
            print(f"  {r.get(name_key, '?')}  [{r.get('module', '?')}]")
        return 0

    # 依赖统计
    dep_key = next((k for k in ("proof_deps", "deps", "dependencies", "used") if k in sample), None)
    counts = {}
    for r in recs:
        deps = r.get(dep_key) or []
        if isinstance(deps, dict):
            deps = list(deps.keys())
        for d in deps:
            counts[d] = counts.get(d, 0) + 1

    top = sorted(counts.items(), key=lambda x: -x[1])[:args.top]
    if args.json:
        print(json.dumps({
            "records": len(recs), "name_key": name_key, "dep_key": dep_key,
            "most_used": [{"name": n, "times": c} for n, c in top],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"records: {len(recs)}")
        if dep_key:
            print(f"most-referenced theorems (core infrastructure):")
            for n, c in top:
                print(f"  {c:5d}x  {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
