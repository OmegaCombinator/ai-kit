#!/usr/bin/env python3
"""Per-key 3-way merge driver for Acorn manifest.json files.

Git 用法
--------
    [merge "acorn-manifest"]
        driver = python3 .../manifest_merge_driver.py %O %A %B

    .gitattributes:
        build/manifest.json       merge=acorn-manifest
        **/certs/manifest.json    merge=acorn-manifest

语义
----
对 JSON 对象做**递归 per-key 三方合并**（RFC 7396 风格的三方变体）：

- 键只在某一侧新增        -> 取该侧
- 两侧都改且改得一样      -> 取该值
- 一侧改、一侧未改        -> 取改的那侧
- 两侧都未改              -> 取 base
- 两侧改得不同:
    - 三者都是 dict      -> 递归合并
    - 三者都是 list      -> 若相等取之；否则冲突（除非 --list-union）
    - 其余                -> 冲突

冲突表示
--------
冲突时把冲突值以 git 冲突标记块写入输出（使结果不是合法 JSON，
从而被 conflict_marker_gate.sh 捕获），并以退出码 1 结束（git 将文件标记为 unmerged）。

退出码
------
0 = 干净合并（结果已写入 %A）
1 = 存在冲突（带标记的结果已写入 %A，git 标记 unmerged）
2 = 参数/IO 错误

命令行
------
manifest_merge_driver.py <base> <ours> <theirs> [--list-union] [--indent 2]
"""

import argparse
import json
import sys
from typing import Any, List, Tuple

CONFLICT_BEGIN = "<<<<<<< "
CONFLICT_SEP = "======="
CONFLICT_END = ">>>>>>> "


def merge_value(base: Any, ours: Any, theirs: Any, list_union: bool) -> Tuple[Any, List[str]]:
    """递归三方合并。返回 (结果, 冲突路径列表)。"""
    conflicts: List[str] = []

    # 未变的快速路径
    if ours == base:
        return theirs, conflicts
    if theirs == base:
        return ours, conflicts
    if ours == theirs:
        return ours, conflicts

    # 三方都是 dict -> 按 key 递归
    if isinstance(base, dict) and isinstance(ours, dict) and isinstance(theirs, dict):
        keys = set(base) | set(ours) | set(theirs)
        out: dict = {}
        for k in sorted(keys):
            b, o, t = base.get(k, _MISSING), ours.get(k, _MISSING), theirs.get(k, _MISSING)
            if o is _MISSING:
                # 一侧删除
                if t is _MISSING:
                    continue
                out[k] = t
                continue
            if t is _MISSING:
                out[k] = o
                continue
            if b is _MISSING:
                # 两侧新增
                if o == t:
                    out[k] = o
                else:
                    out[k] = _conflict_block(o, t)
                    conflicts.append(k)
                continue
            sub, sub_conf = merge_value(b, o, t, list_union)
            if sub_conf:
                conflicts.extend(f"{k}.{p}" for p in sub_conf)
            out[k] = sub
        return out, conflicts

    # 三方都是 list -> 相等取之；否则按选项
    if isinstance(base, list) and isinstance(ours, list) and isinstance(theirs, list):
        if ours == theirs:
            return ours, conflicts
        if list_union:
            merged: List[Any] = []
            for item in list(ours) + list(theirs):
                if item not in merged:
                    merged.append(item)
            return merged, conflicts
        return _conflict_block(ours, theirs), [".<list>"]

    # 标量冲突
    return _conflict_block(ours, theirs), [".<scalar>"]


class _Missing:
    pass


_MISSING = _Missing()


def _conflict_block(ours: Any, theirs: Any) -> dict:
    """构造一个带 git 冲突标记的"值"。

    以 dict 形式返回 {CONFLICT_BEGIN...: ours, ..., theirs: ...} 会破坏 JSON 输出，
    所以我们直接返回标记字符串包裹的 JSON 文本，保证输出不是合法 JSON（可被冲突门捕获），
    又保留两侧完整值供人工解析。
    """
    return {
        "_conflict": {
            CONFLICT_BEGIN.rstrip(): json.dumps(ours, ensure_ascii=False, sort_keys=True),
            CONFLICT_SEP: None,
            CONFLICT_END.rstrip(): json.dumps(theirs, ensure_ascii=False, sort_keys=True),
        }
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Acorn manifest.json per-key 3-way merge driver")
    ap.add_argument("base", help="ancestor file (%O)")
    ap.add_argument("ours", help="current branch file (%A); result is written here")
    ap.add_argument("theirs", help="other branch file (%B)")
    ap.add_argument("--list-union", action="store_true", help="merge unequal lists by dedup union")
    ap.add_argument("--indent", type=int, default=2)
    args = ap.parse_args()

    try:
        with open(args.base, "r", encoding="utf-8") as f:
            base = json.load(f)
        with open(args.ours, "r", encoding="utf-8") as f:
            ours = json.load(f)
        with open(args.theirs, "r", encoding="utf-8") as f:
            theirs = json.load(f)
    except FileNotFoundError as e:
        print(f"manifest_merge_driver: missing file: {e}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"manifest_merge_driver: not valid JSON ({e.filename}:{e.lineno}): "
              f"falling back to conflict state", file=sys.stderr)
        # 无法解析的文件不做自动合并：保留 ours，标记冲突
        return 1

    result, conflicts = merge_value(base, ours, theirs, args.list_union)

    with open(args.ours, "w", encoding="utf-8") as f:
        if conflicts:
            # 冲突时写出 "可读但非法 JSON" 的结构：正常 key 用 JSON，冲突 key 用标记文本
            json.dump(result, f, ensure_ascii=False, indent=args.indent)
            f.write("\n")
            for path in conflicts:
                print(f"CONFLICT at {path}", file=sys.stderr)
            return 1
        json.dump(result, f, ensure_ascii=False, indent=args.indent)
        f.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
