#!/usr/bin/env python3
"""union_sources.py — 接口/公共文件的双侧声明级并集合并。

背景：合并树里同一接口文件（如 list/interface.ac）被两侧都改过时，
"取单侧"会丢掉另一侧需要的导出。正确做法：按顶层声明名取并集——
fork 版优先（保持 fork 模块可重放），上游独有声明追加到末尾。

用法:
    union_sources.py --root <repo> --files a.ac,b.ac [--prefer fork|upstream]
"""

import argparse
import os
import re
import subprocess
import sys

DECL_START = re.compile(
    r"^(theorem|define|let|structure|inductive|typeclass|instance|attribute|attributes)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)")


def split_declarations(text: str):
    """把文件切成 [头部(imports/注释/指令), (声明名, 声明文本)...]。

    声明边界：见到开 `{` 后才算进入声明体；深度归零且行尾 `}` 才算结束。
    无括号声明（let x = ... / 单行 define）到行尾或下一声明/空行结束。
    """
    lines = text.split("\n")
    header = []
    decls = []  # (name, [lines])
    i = 0
    current_name = None
    current = []
    brace_depth = 0
    seen_open = False
    in_decl = False
    while i < len(lines):
        line = lines[i]
        m = DECL_START.match(line)
        if m and not in_decl:
            if current_name:
                decls.append((current_name, current))
            current_name, current, in_decl = m.group(2), [line], True
            brace_depth = line.count("{") - line.count("}")
            seen_open = "{" in line
            if seen_open and brace_depth <= 0 and line.rstrip().endswith("}"):
                # 单行声明
                decls.append((current_name, current))
                current_name, current, in_decl = None, [], False
            i += 1
            continue
        if in_decl:
            current.append(line)
            if not seen_open:
                seen_open = "{" in line
                brace_depth = line.count("{") - line.count("}")
            else:
                brace_depth += line.count("{") - line.count("}")
            if seen_open and brace_depth <= 0 and line.rstrip().endswith("}"):
                decls.append((current_name, current))
                current_name, current, in_decl = None, [], False
            elif not seen_open and (
                line.strip() == "" or DECL_START.match(line) or i == len(lines) - 1
            ):
                # 无括号声明结束
                if line.strip() != "" or current[-2:]:
                    pass
                decls.append((current_name, current))
                current_name, current, in_decl = None, [], False
            i += 1
            continue
        header.append(line)
        i += 1
    if current_name:
        decls.append((current_name, current))
    return header, decls


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--prefer", choices=["fork", "upstream"], default="fork")
    args = ap.parse_args()
    root = os.path.abspath(args.root)

    for f in args.files:
        def get(ref):
            r = subprocess.run(["git", "show", f"{ref}:{f}"], cwd=root,
                               capture_output=True, text=True)
            return r.stdout if r.returncode == 0 else None

        fork_text = get("HEAD")
        up_text = get("MERGE_HEAD")
        if fork_text is None or up_text is None:
            print(f"skip {f}: missing side", file=sys.stderr)
            continue
        if fork_text == up_text:
            print(f"skip {f}: sides identical")
            continue

        h_fork, d_fork = split_declarations(fork_text)
        h_up, d_up = split_declarations(up_text)

        def key(item):
            # instance/attribute 用完整首行做键（如 `instance Nat: Zero` 与
            # `inductive Nat` 同名但不同）；其余用声明名。
            name, lines = item
            kind = lines[0].split(" ", 1)[0]
            if kind in ("instance", "attribute"):
                return ("sig", lines[0].strip())
            return ("name", name)

        fork_names = {key(d) for d in d_fork}
        up_names = {key(d) for d in d_up}

        only_up = [d for d in d_up if key(d) not in fork_names]
        only_fork = [d for d in d_fork if key(d) not in up_names]
        print(f"{f}: fork decls {len(d_fork)}, upstream decls {len(d_up)}, "
              f"only-upstream {len(only_up)}, only-fork {len(only_fork)}")

        # 输出 = fork 完整源码（保持原序，含指令/注释原位）+ 上游独有声明追加末尾。
        # 这样 numerals/attributes 等非声明行不会被打乱到头部。
        merged = fork_text.rstrip() + "\n\n"
        extra = only_up if args.prefer == "fork" else only_fork
        for n, t in extra:
            merged += "\n".join(t) + "\n\n"
        merged = merged.rstrip() + "\n"
        with open(os.path.join(root, f), "w", encoding="utf-8") as out:
            out.write(merged)
        print(f"wrote union {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
