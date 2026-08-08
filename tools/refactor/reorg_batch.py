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

    # 已有包（有 interface.ac）：移入会变私有模块，跳过（保留在根）
    packages = set()
    for dp, _d, _f in os.walk(os.path.join(root, "src")):
        if "interface.ac" in _f:
            packages.add(os.path.relpath(dp, os.path.join(root, "src")))
    print(f"reorg_batch: existing packages: {len(packages)}")

    # 选定要移动的模块（org_map 值以某领域开头，且当前在根级，且目标首段不是已有包）
    moves = {}
    skipped = []
    for mod, target in org_map.items():
        if any(target.startswith(d + "/") for d in domains):
            src = os.path.join(root, "src", mod + ".ac")
            if not os.path.isfile(src):
                continue
            first = target.split("/", 1)[0]
            if first in packages:
                skipped.append(mod)
                continue
            moves[mod] = target.replace("/", ".")
    if skipped:
        print(f"reorg_batch: skipped {len(skipped)} (target is existing package): "
              f"{skipped[:8]}...")
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

    # 4. 验证（replay 稳定性检查器）：
    #    全库 verify 一次（刷新 manifest）→ 全库 check --strict 一次。
    #    任何 replay 失败（如 ∈ 糖的 elaborate 变化）→ 自动回退整个批次。
    if args.verify:
        r = subprocess.run([args.acorn, "verify"], cwd=root, capture_output=True,
                           text=True, timeout=3600)
        vout = r.stdout + r.stderr
        if r.returncode != 0:
            print(f"  VERIFY FAILED:\n{vout[-600:]}", file=sys.stderr)
            failed = True
        else:
            r2 = subprocess.run([args.acorn, "check", "--strict", "-j", "8"], cwd=root,
                                capture_output=True, text=True, timeout=3600)
            sout = r2.stdout + r2.stderr
            failed = r2.returncode != 0
            print(f"  check --strict: rc={r2.returncode}\n{sout[-400:]}")
        if failed:
            print("  replay instability detected — reverting this batch", file=sys.stderr)
            subprocess.run(["git", "checkout", "HEAD", "--", "."], cwd=root)
            for m, new in moves.items():
                subprocess.run(["rm", "-rf",
                                os.path.join(root, "src", new.replace(".", os.sep))],
                               capture_output=True)
            print("  reverted")
            return 1
        print("  replay-stable: full check --strict OK")

    if args.commit:
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", args.commit], cwd=root, check=True)
    print("reorg_batch: done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
