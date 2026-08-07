#!/usr/bin/env python3
"""move_module.py — 移动/重命名 .ac 模块（重组工具，merge_modules 改写逻辑的单模块版）。

移动模块 M 到新模块名 NEW（如 add -> algebra.add，即 src/add.ac -> src/algebra/add.ac）：
- 重写全部 `from M import` -> `from NEW import`
- 重写全部证书 `lib(M).` -> `lib(NEW).`
- 移动证书文件 src/certs/M.jsonl -> <NEW 路径>/certs/<NEW>.jsonl
- 校验受影响闭包 check --strict（0 searches = 证书按名重放成功）

不创建 interface.ac（见 docs/library-organization.md：无 interface 的目录不构成包边界，
模块保持 Outside 角色可自由导入；改名仅是路径/名前缀变化）。

用法:
    move_module.py --root <acornlib> --module <M> --new <NEW> [--acorn <bin>]
                   [--dry-run] [--verify] [--commit "msg"]
"""

import argparse
import os
import re
import subprocess
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--module", required=True, help="旧模块名（如 add）")
    ap.add_argument("--new", required=True, help="新模块名（如 algebra.add）")
    ap.add_argument("--acorn", default=os.environ.get("ACORN_BIN", "acorn"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="移动后验证受影响闭包")
    ap.add_argument("--commit", default="")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    old, new = args.module, args.new
    if old == new:
        print("move_module: --module and --new are the same", file=sys.stderr)
        return 2

    old_path = os.path.join(root, "src", old.replace(".", os.sep) + ".ac")
    new_path = os.path.join(root, "src", new.replace(".", os.sep) + ".ac")
    if not os.path.isfile(old_path):
        print(f"move_module: source not found: {old_path}", file=sys.stderr)
        return 2
    if os.path.exists(new_path):
        print(f"move_module: target exists: {new_path}", file=sys.stderr)
        return 2

    old_cert = os.path.join(root, "src", "certs", old + ".jsonl")
    new_cert_dir = os.path.join(root, "src", new.replace(".", os.sep), "certs")
    new_cert = os.path.join(new_cert_dir, new.rsplit(".", 1)[-1] + ".jsonl")
    # 包内模块证书: src/<dir>/certs/<file>.jsonl
    if not os.path.isfile(old_cert):
        old_cert = os.path.join(root, "src", old.replace(".", os.sep), "certs",
                                old.rsplit(".", 1)[-1] + ".jsonl")
        if os.path.isfile(old_cert):
            new_cert_dir = os.path.join(os.path.dirname(new_path), "certs")
            new_cert = os.path.join(new_cert_dir, new.rsplit(".", 1)[-1] + ".jsonl")

    # 改写清单
    import_rewrites = []
    lib_rewrites = []
    for dirpath, _dirs, files in os.walk(os.path.join(root, "src")):
        for fn in files:
            p = os.path.join(dirpath, fn)
            if p == old_path:
                continue
            try:
                text = open(p, encoding="utf-8").read()
            except OSError:
                continue
            if fn.endswith(".ac") and re.search(rf"^from\s+{re.escape(old)}\s+import", text, re.M):
                import_rewrites.append(p)
            if f"lib({old})." in text:
                lib_rewrites.append(p)

    if args.dry_run:
        print(f"move_module: DRY RUN — {old} -> {new}")
        print(f"  {old_path} -> {new_path}")
        print(f"  cert: {os.path.basename(old_cert) if os.path.isfile(old_cert) else '(none)'} -> "
              f"{os.path.relpath(new_cert, root)}")
        print(f"  import rewrites: {len(import_rewrites)} files")
        print(f"  lib() rewrites: {len(lib_rewrites)} files")
        for p in import_rewrites[:8]:
            print(f"    import: {os.path.relpath(p, root)}")
        return 0

    # 执行
    os.makedirs(os.path.dirname(new_path), exist_ok=True)
    os.replace(old_path, new_path)
    if os.path.isfile(old_cert):
        os.makedirs(new_cert_dir, exist_ok=True)
        os.replace(old_cert, new_cert)
        cert_moved = True
    else:
        cert_moved = False

    for p in import_rewrites:
        text = open(p, encoding="utf-8").read()
        text2 = re.sub(rf"^from\s+{re.escape(old)}\s+import", f"from {new} import", text, flags=re.M)
        if text2 == text:
            print(f"move_module: import rewrite no-op: {p}", file=sys.stderr)
        open(p, "w", encoding="utf-8").write(text2)
    for p in lib_rewrites:
        text = open(p, encoding="utf-8").read()
        text2 = text.replace(f"lib({old}).", f"lib({new}).")
        if text2 == text:
            print(f"move_module: lib rewrite no-op: {p}", file=sys.stderr)
        open(p, "w", encoding="utf-8").write(text2)

    print(f"move_module: moved {old} -> {new}; imports {len(import_rewrites)}, "
          f"lib() {len(lib_rewrites)}, cert moved: {cert_moved}")

    if args.verify:
        import sys as _s
        _s.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "merge"))
        try:
            from impact_closure import build_dag, downstream_closure
        except ImportError:
            print("move_module: cannot import impact_closure", file=_s.stderr)
            return 2
        dag = build_dag(os.path.join(root, "src"))
        closure = downstream_closure(dag, [new])
        targets = [new] + [c for c in closure if c != new]
        for t in targets:
            tp = os.path.join(root, "src", t.replace(".", os.sep) + ".ac")
            if not os.path.isfile(tp):
                continue
            r = subprocess.run([args.acorn, "verify", tp], capture_output=True, text=True,
                               timeout=3600)
            out = r.stdout + r.stderr
            if r.returncode != 0:
                print(f"move_module: verify failed for {tp}\n{out[-800:]}", file=_s.stderr)
                return 1
        for t in targets:
            tp = os.path.join(root, "src", t.replace(".", os.sep) + ".ac")
            if not os.path.isfile(tp):
                continue
            r = subprocess.run([args.acorn, "check", "--strict", tp], capture_output=True,
                               text=True, timeout=3600)
            out = r.stdout + r.stderr
            if r.returncode != 0 or "0 searches performed" not in out:
                print(f"move_module: strict replay failed for {tp}\n{out[-800:]}", file=_s.stderr)
                return 1
        print(f"move_module: verified {len(targets)} modules (move + closure) with 0 searches")

    if args.commit:
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", args.commit], cwd=root, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
