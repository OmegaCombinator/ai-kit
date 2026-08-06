#!/usr/bin/env python3
"""merge_modules.py — 把多个 .ac 模块整合成一个模块，证书随声明迁移、下游引用自动改写。

背景：acornlib 有大量扁平小模块（312+ 个根文件）。整合 = 把 a.ac + b.ac 的声明
合并进 out.ac。Acorn 证书按"名字"解析（对重构稳健，M1 实验已验证）：
- 被合并模块自身的证书行（goal+proof）按原顺序拼入新模块的证书文件；
- 其他模块证书里 `lib(<a>).` / `lib(<b>).` 限定名改写为 `lib(<out>).`；
- 其他 .ac 源文件里 `from <a> import` / `from <b> import` 改写为 `from <out> import`；
- 受影响闭包跑 check --strict 验证（0 searches = 证书原样重放）。

限制（v1）：
- 只支持根级模块（src/x.ac），不支持目录包模块；
- 被合并模块之间不得有同名声明（会中止）；
- 不自找属性/instance 顺序问题——交给 check --strict 兜底。

用法:
    merge_modules.py --root <acornlib> --out merged --modules a,b [--acorn <bin>]
                     [--dry-run] [--commit "msg"]

--dry-run: 只输出将发生的改写清单，不改文件。
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def mod_to_path(mod: str) -> str:
    return os.path.join("src", mod.replace(".", os.sep) + ".ac")


def cert_path_for(mod: str) -> str:
    # 根级模块: src/certs/<mod>.jsonl
    return os.path.join("src", "certs", mod + ".jsonl")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True, help="新模块名（根级）")
    ap.add_argument("--modules", required=True, help="逗号分隔的旧模块名")
    ap.add_argument("--acorn", default=os.environ.get("ACORN_BIN", "acorn"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--commit", default="")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    out = args.out
    mods = [m.strip() for m in args.modules.split(",") if m.strip()]
    if out in mods:
        print("merge_modules: --out must not be one of --modules", file=sys.stderr)
        return 2

    # 0. 前置：文件存在性
    for m in mods:
        p = os.path.join(root, mod_to_path(m))
        if not os.path.isfile(p):
            print(f"merge_modules: module file not found: {p}", file=sys.stderr)
            return 2
    out_path = os.path.join(root, mod_to_path(out))
    if os.path.exists(out_path):
        print(f"merge_modules: output already exists: {out_path}", file=sys.stderr)
        return 2

    # 1. 收集声明名（顶层 theorem/define/let/structure/inductive/typeclass 名），检查冲突
    decl_re = re.compile(r"^(?:theorem|define|let|structure|inductive|typeclass|instance|attribute)\s+([A-Za-z_][A-Za-z0-9_]*)")
    seen = {}
    sources = {}
    for m in mods:
        text = read(os.path.join(root, mod_to_path(m)))
        sources[m] = text
        for d in decl_re.finditer(text):
            name = d.group(1)
            if name in seen and seen[name] != m:
                print(f"merge_modules: name collision '{name}' in {seen[name]} and {m}", file=sys.stderr)
                return 2
            seen[name] = m

    # 2. 生成合并源：import 语句逐行保留原文（支持跨行续行，行尾逗号续行），
    #    取并集去重；声明体按原模块顺序拼接。
    import_start_re = re.compile(r"^from\s+([A-Za-z0-9_.]+)\s+import\b")
    header_imports = []          # 保留下来的 import 语句文本（含续行）
    seen_import_texts = set()    # 按语句文本去重（同一模块可多次 import 不同名字集）
    body_parts = []
    for m in mods:
        text = sources[m]
        lines = text.split("\n")
        kept_imports = []
        body_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            mt = import_start_re.match(line)
            if mt:
                if mt.group(1) not in mods:
                    # 收集完整 import 语句（续行：行尾逗号）
                    stmt = [line]
                    while line.rstrip().endswith(",") and i + 1 < len(lines):
                        i += 1
                        line = lines[i]
                        stmt.append(line)
                    stmt_text = "\n".join(stmt)
                    if stmt_text not in seen_import_texts:
                        kept_imports.append(stmt_text)
                        seen_import_texts.add(stmt_text)
                else:
                    # 被合并模块之间的 import：跳过（合并后都在同一模块内）
                    while line.rstrip().endswith(",") and i + 1 < len(lines):
                        i += 1
                        line = lines[i]
                i += 1
                continue
            body_lines.append(line)
            i += 1
        header_imports.extend(kept_imports)
        body_parts.append("\n".join(body_lines).strip())

    merged_src = "\n".join(header_imports) + "\n\n" if header_imports else ""
    merged_src += "\n\n".join(body_parts) + "\n"

    # 3. 生成合并证书：按顺序拼接各模块证书行
    cert_lines = []
    for m in mods:
        cp = os.path.join(root, cert_path_for(m))
        if os.path.isfile(cp):
            cert_lines.extend(read(cp).splitlines())
        else:
            print(f"merge_modules: warning: no cert file for {m}: {cp}", file=sys.stderr)

    # 4. 计算下游改写清单
    rewrite_imports = []   # (file_path, old, new)
    rewrite_lib = []       # (file_path, old_lib, new_lib)
    for dirpath, _dirs, files in os.walk(os.path.join(root, "src")):
        for fn in files:
            if not fn.endswith(".ac"):
                continue
            p = os.path.join(dirpath, fn)
            text = read(p)
            for m in mods:
                if re.search(rf"^from\s+{re.escape(m)}\s+import", text, re.M):
                    rewrite_imports.append((p, m, out))
                if f"lib({m})." in text:
                    rewrite_lib.append((p, m, out))
    # 证书文件中的 lib() 引用
    cert_files = []
    for dirpath, _dirs, files in os.walk(os.path.join(root, "src")):
        for fn in files:
            if fn.endswith(".jsonl"):
                cert_files.append(os.path.join(dirpath, fn))

    if args.dry_run:
        print(f"merge_modules: DRY RUN — would create {mod_to_path(out)} "
              f"({len(merged_src.splitlines())} lines), cert {cert_path_for(out)} "
              f"({len(cert_lines)} lines)")
        print(f"  import rewrites: {len(rewrite_imports)} files; "
              f"lib() rewrites in sources: {len(rewrite_lib)}; cert rewrites: "
              f"{sum(1 for p in cert_files if any(f'lib({m}).' in read(p) for m in mods))} files")
        for p, m, o in rewrite_imports[:10]:
            print(f"    import: {os.path.relpath(p, root)}: from {m} -> from {o}")
        return 0

    # 5. 执行
    write(out_path, merged_src)
    out_cert = os.path.join(root, cert_path_for(out))
    write(out_cert, "\n".join(cert_lines) + ("\n" if cert_lines else ""))

    import_bad = []
    for p, m, o in rewrite_imports:
        text = read(p)
        text2 = re.sub(rf"^from\s+{re.escape(m)}\s+import", f"from {o} import", text, flags=re.M)
        if text2 == text:
            import_bad.append(p)
        write(p, text2)
    lib_bad = []
    for p, m, o in rewrite_lib:
        text = read(p)
        text2 = text.replace(f"lib({m}).", f"lib({o}).")
        if text2 == text:
            lib_bad.append(p)
        write(p, text2)
    cert_bad = []
    for p in cert_files:
        if p in (os.path.join(root, cert_path_for(out)),):
            continue
        text = read(p)
        text2 = text
        for m in mods:
            text2 = text2.replace(f"lib({m}).", f"lib({out}).")
        if text2 != text:
            write(p, text2)
        elif any(f"lib({m})." in text for m in mods):
            cert_bad.append(p)

    # 6. 删除旧文件与旧证书
    for m in mods:
        os.unlink(os.path.join(root, mod_to_path(m)))
        cp = os.path.join(root, cert_path_for(m))
        if os.path.isfile(cp):
            os.unlink(cp)

    print(f"merge_modules: created {mod_to_path(out)} "
          f"({len(merged_src.splitlines())} lines), cert {len(cert_lines)} lines")
    print(f"  import rewrites: {len(rewrite_imports)}; lib rewrites: {len(rewrite_lib)}; "
          f"cert rewrites: {len(cert_files) - cert_bad.__len__() if False else ''}")

    # 7. 验证：verify 新模块 + 下游闭包（刷新依赖哈希/ manifest 条目；串行，防竞态）
    #    然后对闭包逐个 check --strict。
    import sys as _sys
    sys.path.insert(0, os.path.join(HERE, "..", "merge"))
    try:
        from impact_closure import build_dag, downstream_closure  # type: ignore
    except ImportError:
        print("merge_modules: cannot import impact_closure", file=sys.stderr)
        return 2
    dag = build_dag(os.path.join(root, "src"))
    # 合并后旧模块文件已删除、下游已改写为引用 out；用新模块名求闭包
    closure = downstream_closure(dag, [out])
    targets = list(dict.fromkeys([out] + closure))  # 闭包已含 out，去重
    verify_targets = []
    for t in targets:
        tp = os.path.join(root, mod_to_path(t))
        if os.path.isfile(tp):
            verify_targets.append(tp)
    for tp in verify_targets:
        r = subprocess.run([args.acorn, "verify", tp],
                           capture_output=True, text=True, timeout=3600)
        ver_out = r.stdout + r.stderr
        if r.returncode != 0:
            print(f"merge_modules: verify failed for {tp}\n{ver_out[-1200:]}", file=sys.stderr)
            return 1
        last = ver_out.strip().splitlines()[-1] if ver_out.strip() else ""
        print(f"verify {os.path.basename(tp)}: {last}")
    for tp in verify_targets:
        r = subprocess.run([args.acorn, "check", "--strict", tp],
                           capture_output=True, text=True, timeout=3600)
        ver_out = r.stdout + r.stderr
        if r.returncode != 0 or "0 searches performed" not in ver_out:
            print(f"merge_modules: strict replay failed for {tp}\n{ver_out[-1200:]}", file=sys.stderr)
            return 1
        last = ver_out.strip().splitlines()[-1] if ver_out.strip() else ""
        print(f"strict {os.path.basename(tp)}: {last}")
    print(f"merge_modules: verified {len(verify_targets)} modules (merge + closure) with 0 searches")

    if args.commit:
        subprocess.run(["git", "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-m", args.commit], cwd=root, check=True)
        print(f"merge_modules: committed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
