#!/usr/bin/env python3
"""reorg_batch.py — 按 org_map 批量移动模块（src/ 重组执行器）。

对一批模块执行移动：文件移动 + import 改写 + 证书 lib() 改写 + 证书文件迁移，
然后对受影响闭包 verify + check --strict。

用法:
    reorg_batch.py --root <acornlib> --domains graph,probability [--map org_map.json]
                   [--acorn <bin>] [--dry-run] [--verify] [--commit "msg"]
"""

import argparse
import json
import os
import re
import subprocess
import sys

IMPORT_RE = re.compile(r"^from\s+([A-Za-z0-9_.]+)\s+import\b", re.M)


def module_of(f: str) -> str:
    # src/x.ac -> x ; src/a/b.ac -> a.b
    rel = f[4:-3].replace(os.sep, ".")
    return rel


def cert_of(mod: str, root: str) -> str:
    p = os.path.join(root, "src", mod.replace(".", os.sep) + ".ac")
    d, n = os.path.dirname(p), os.path.basename(p)[:-3]
    if d.endswith("src"):
        return os.path.join(root, "src", "certs", n + ".jsonl")
    return os.path.join(d, "certs", n + ".jsonl")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--domains", required=True, help="逗号分隔的目标领域前缀（org_map 值前缀）")
    ap.add_argument("--map", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "org_map.json"))
    ap.add_argument("--acorn", default=os.environ.get("ACORN_BIN", "acorn"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--commit", default="")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    org_map = json.load(open(args.map, encoding="utf-8"))

    # 选定要移动的模块（org_map 值以某领域开头，且当前在根级）
    moves = {}
    for mod, target in org_map.items():
        if any(target.startswith(d + "/") for d in domains):
            src = os.path.join(root, "src", mod + ".ac")
            if os.path.isfile(src):
                moves[mod] = target.replace("/", ".")
    if not moves:
        print(f"reorg_batch: no modules for domains {domains}", file=sys.stderr)
        return 2
    print(f"reorg_batch: moving {len(moves)} modules for {domains}")

    if args.dry_run:
        for mod, target in sorted(moves.items()):
            print(f"  {mod}.ac -> {target}.ac")
        return 0

    # 1. 执行移动（先移文件，再在移动后的树上统一改写，覆盖模块间相互引用）
    for mod, target in moves.items():
        # target 是模块名（点）；文件路径用斜杠
        target_path = target.replace(".", os.sep)
        src = os.path.join(root, "src", mod + ".ac")
        dst = os.path.join(root, "src", target_path + ".ac")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(src, dst)
        sc = cert_of(mod, root)
        if os.path.isfile(sc):
            dc = os.path.join(os.path.dirname(dst), "certs",
                              os.path.basename(dst)[:-3] + ".jsonl")
            os.makedirs(os.path.dirname(dc), exist_ok=True)
            os.replace(sc, dc)

    # 2. 改写引用（全部 .ac/.jsonl，包括移动后的文件自身）
    import_rewrites = 0
    lib_rewrites = 0
    for dirpath, _dirs, files in os.walk(os.path.join(root, "src")):
        for fn in files:
            p = os.path.join(dirpath, fn)
            if not (fn.endswith(".ac") or fn.endswith(".jsonl")):
                continue
            try:
                text = open(p, encoding="utf-8").read()
            except OSError:
                continue
            text2 = text
            for old_mod, new_mod in moves.items():
                if fn.endswith(".ac"):
                    text2 = re.sub(rf"^from\s+{re.escape(old_mod)}\s+import",
                                   f"from {new_mod} import", text2, flags=re.M)
                text2 = text2.replace(f"lib({old_mod}).", f"lib({new_mod}).")
            if text2 != text:
                open(p, "w", encoding="utf-8").write(text2)
                import_rewrites += 1

    print(f"  moved {len(moves)} files; rewrote {import_rewrites} files")

    # 4. 验证受影响闭包
    if args.verify:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "merge"))
        from impact_closure import build_dag, downstream_closure
        dag = build_dag(os.path.join(root, "src"))
        new_mods = [moves[m] for m in moves]
        closure = downstream_closure(dag, new_mods)
        targets = list(dict.fromkeys(new_mods + closure))
        failed = 0
        for t in targets:
            tp = os.path.join(root, "src", t.replace(".", os.sep) + ".ac")
            if not os.path.isfile(tp):
                continue
            r = subprocess.run([args.acorn, "verify", tp], cwd=root, capture_output=True,
                               text=True, timeout=900)
            if r.returncode != 0:
                print(f"  VERIFY FAIL: {tp}\n{(r.stdout+r.stderr)[-400:]}", file=sys.stderr)
                failed += 1
                continue
            r2 = subprocess.run([args.acorn, "check", "--strict", tp], cwd=root,
                                capture_output=True, text=True, timeout=900)
            out = r2.stdout + r2.stderr
            if r2.returncode != 0 or "0 searches performed" not in out:
                print(f"  STRICT FAIL: {tp}\n{out[-400:]}", file=sys.stderr)
                failed += 1
        print(f"  closure: {len(targets)} modules, {failed} failures")
        if failed:
            return 1

    if args.commit:
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", args.commit], cwd=root, check=True)
    print("reorg_batch: done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
