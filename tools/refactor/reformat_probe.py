#!/usr/bin/env python3
"""reformat_probe.py — M1 实验的自动化脚本。

对给定 .ac 文件施加"语义无关"的文本变换（import 续行合并、空行归一、注释微调），
然后运行 `check --strict` 验证证书是否原样重放（0 searches）。

用法:
    reformat_probe.py <file.ac> [--acorn <bin>] [--check-only]

退出码: 0 = 重放通过; 1 = 重放失败; 2 = 参数/环境错误
"""

import argparse
import re
import subprocess
import sys
import tempfile
import os


def apply_reformat(src: str) -> str:
    """语义无关变换：import 续行合并 + 声明间空行归一 + 注释加空格。"""
    out = re.sub(r",\n\s+", ", ", src)          # import 续行合并
    out = re.sub(r"\n}\n(?=\S)", "\n}\n\n", out)  # 顶层声明后空行
    out = out.replace("/// The Bernoulli mass function with parameter `p`:",
                      "///  The Bernoulli mass function with parameter `p`:")
    if not out.endswith("\n"):
        out += "\n"
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", help=".ac 文件路径")
    ap.add_argument("--acorn", default=os.environ.get("ACORN_BIN", "acorn"),
                    help="acorn 二进制（默认 $ACORN_BIN 或 acorn）")
    ap.add_argument("--keep", action="store_true", help="保留变换后的文件")
    args = ap.parse_args()

    if not args.file.endswith(".ac") or not os.path.isfile(args.file):
        print("reformat_probe: need an existing .ac file", file=sys.stderr)
        return 2

    src = open(args.file, encoding="utf-8").read()
    new = apply_reformat(src)
    if new == src:
        print("reformat_probe: transform produced no change (file already clean)")
        return 0

    # 模块身份 = 文件路径（相对库根），必须在原路径上跑 check。
    # 默认：原位写入 + 结束后恢复原文件；--keep 保留变换结果。
    backup = None
    if not args.keep:
        fd, backup = tempfile.mkstemp(suffix=".ac.bak")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(src)
    with open(args.file, "w", encoding="utf-8") as f:
        f.write(new)

    try:
        r = subprocess.run([args.acorn, "check", "--strict", args.file],
                           capture_output=True, text=True, timeout=1200)
        out = r.stdout + r.stderr
        print(out[-1200:])
        ok = r.returncode == 0 and "0 searches performed" in out and "OK" in out
        if ok:
            print(f"reformat_probe: REPLAY OK (0 searches) — formatting does not "
                  f"invalidate certificates for {args.file}")
            return 0
        print(f"reformat_probe: REPLAY FAILED (rc={r.returncode})", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("reformat_probe: check --strict timed out", file=sys.stderr)
        return 1
    finally:
        if backup is not None and os.path.exists(backup):
            os.replace(backup, args.file)


if __name__ == "__main__":
    sys.exit(main())
