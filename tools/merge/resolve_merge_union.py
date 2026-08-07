#!/usr/bin/env python3
"""resolve_merge_union.py — 合并后残余冲突的机械解析。

三类处理：
- .ac 源码:   --ac 参数指定取 ours/theirs（如 6 个语义冲突统一取 theirs）
- 证书 jsonl: 按 goal 并集（两侧行都保留、去重）——max 化证书复用，verify 再重生成
- manifest:   保留两侧 key 并集（冲突 key 取 theirs），verify 会更新 hash

用法:
    resolve_merge_union.py --repo <dir> [--ac ours|theirs] [--jsonl] [--manifest]
    # 默认: 对所有未合并(unmerged)文件按类型处理
"""

import argparse
import json
import os
import subprocess
import sys


def load_jsonl(path):
    recs, order = {}, []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            try:
                g = json.loads(line).get("goal")
            except json.JSONDecodeError:
                g = None
            key = g if g is not None else "__line:" + line[:60]
            if key not in recs:
                recs[key] = line
                order.append(key)
    return recs, order


def union_jsonl(path):
    """把冲突标记文件解析为两侧并集（按 goal 去重，保持顺序）。"""
    ours, theirs = [], []
    mode = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("<<<<<<<"):
                mode = "ours"
                continue
            if line.startswith("======="):
                mode = "theirs"
                continue
            if line.startswith(">>>>>>>"):
                mode = None
                continue
            if mode == "ours":
                ours.append(line)
            elif mode == "theirs":
                theirs.append(line)
            else:
                ours.append(line)
                theirs.append(line)
    merged = {}
    order = []
    for line in ours + theirs:
        try:
            g = json.loads(line).get("goal")
        except json.JSONDecodeError:
            g = None
        key = g if g is not None else "__line:" + line[:60]
        if key not in merged:
            merged[key] = line
            order.append(key)
    with open(path, "w", encoding="utf-8") as f:
        for k in order:
            f.write(merged[k] + "\n")


def union_json(path):
    """manifest: 两侧 key 并集；冲突 key 取 theirs。"""
    def load(p):
        return json.load(open(p, encoding="utf-8"))
    try:
        ours = load(path)
    except Exception:
        return
    # 找 base/ours 版本来自 git
    r = subprocess.run(["git", "show", f":2:{os.path.relpath(path, os.getcwd())}"],
                       capture_output=True, text=True)
    theirs = None
    r3 = subprocess.run(["git", "show", f":3:{os.path.relpath(path, os.getcwd())}"],
                        capture_output=True, text=True)
    if r3.returncode == 0:
        theirs = json.loads(r3.stdout)

    def merge_obj(o, t):
        if not isinstance(o, dict) or not isinstance(t, dict):
            return t if t is not None else o
        out = dict(o)
        for k, v in t.items():
            if k not in out:
                out[k] = v
            elif isinstance(v, dict) and isinstance(out[k], dict):
                out[k] = merge_obj(out[k], v)
            else:
                out[k] = v  # 冲突 key 取 theirs
        return out

    merged = merge_obj(ours, theirs) if theirs else ours
    with open(path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--ac", choices=["ours", "theirs"], default="theirs",
                    help=".ac 冲突的取法")
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)

    r = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"],
                       cwd=repo, capture_output=True, text=True)
    files = [f for f in r.stdout.splitlines() if f]
    ac, jsonl, manifest = [], [], []
    for f in files:
        if f.endswith(".ac"):
            ac.append(f)
        elif f.endswith(".jsonl"):
            jsonl.append(f)
        elif f.endswith(".json"):
            manifest.append(f)

    for f in ac:
        subprocess.run(["git", "checkout", "--" + args.ac, f], cwd=repo, check=True)
        print(f"ac: took {args.ac} for {f}")
    for f in jsonl:
        union_jsonl(os.path.join(repo, f))
        print(f"jsonl: union-resolved {f}")
    for f in manifest:
        union_json(os.path.join(repo, f))
        print(f"manifest: union-resolved {f}")
    print(f"done: {len(ac)} ac, {len(jsonl)} jsonl, {len(manifest)} manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
