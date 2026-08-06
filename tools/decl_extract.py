#!/usr/bin/env python3
"""decl_extract.py — 从 .ac 源文件提取顶层声明（acorn-tools §2 Declaration Extractor 的轻量版）。

用途：
- 声明级目标注册表（并行去重：只索引顶层定理，滤掉证书里的证明局部断言）
- split-file / move-decl / rename-decl 重构的基础（声明边界 + 名字 + 区间）
- 库地图（acorn-tools §36）

输出（--json）：
  {module, declarations: [{kind, name, span:{startLine,endLine}, params}]}

说明：这是语法级近似（不做 elaboration）。足够做"顶层定理名单/边界"，
精确的类型/语义信息需要 acorn 自身（export-ast，见 roadmap P2）。

用法:
    decl_extract.py --root <acornlib> [--module a,b] [--json] [--out file]
"""

import argparse
import json
import os
import re
import sys


DECL_RE = re.compile(
    r"^(?P<kw>theorem|define|let|structure|inductive|typeclass|instance|attribute)"
    r"\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)


def extract(text: str):
    """返回声明列表 [{kind, name, start, end, params}]（end 为闭合括号行，1-based）。"""
    decls = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = DECL_RE.match(lines[i])
        if not m:
            i += 1
            continue
        kw, name = m.group("kw"), m.group("name")
        start = i + 1
        # 找到声明体闭合：统计大括号；无括号声明（如 let x = ... 或裸定理）到空行/下一个声明
        depth = 0
        j = i
        brace_started = False
        while j < len(lines):
            line = lines[j]
            depth += line.count("{") - line.count("}")
            if "{" in line:
                brace_started = True
            if brace_started and depth <= 0 and line.rstrip().endswith("}"):
                break
            if not brace_started and depth == 0 and j > i:
                # 无括号形式（let x = expr; theorem 无 by）——到空行或下一个声明
                if lines[j].strip() == "" or DECL_RE.match(lines[j]):
                    j -= 1
                    break
            j += 1
        end = j + 1
        # 参数（粗略）：抓第一个括号对
        params = ""
        pm = re.search(r"\((.*?)\)", lines[i])
        if pm:
            params = pm.group(1)[:80]
        decls.append({"kind": kw, "name": name, "start": start, "end": end, "params": params})
        i = j + 1
    return decls


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--module", default="", help="逗号分隔模块名；默认全部")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--count", action="store_true", help="只输出每种 kind 的计数")
    args = ap.parse_args()

    src_root = os.path.join(args.root, "src")
    if not os.path.isdir(src_root):
        print(f"decl_extract: no src/ under {args.root}", file=sys.stderr)
        return 2
    want = {m for m in args.module.split(",") if m} if args.module else None

    result = []
    kinds = {}
    for dirpath, _dirs, files in os.walk(src_root):
        for fn in sorted(files):
            if not fn.endswith(".ac"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, src_root)
            mod = rel[:-3].replace(os.sep, ".")
            if want and mod not in want:
                continue
            with open(p, encoding="utf-8") as f:
                text = f.read()
            decls = extract(text)
            for d in decls:
                kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
            result.append({"module": mod, "declarations": decls})

    if args.count:
        total = sum(kinds.values())
        print(json.dumps({"modules": len(result), "total_decls": total,
                          "by_kind": kinds}, ensure_ascii=False, indent=2))
        return 0

    out = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
