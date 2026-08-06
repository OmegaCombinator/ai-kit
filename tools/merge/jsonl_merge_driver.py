#!/usr/bin/env python3
"""jsonl_merge_driver.py — 证书 JSONL 的按 goal 键三方合并驱动。

证书文件每行一条记录 {goal, proof}；goal 是规范化后的定理陈述，天然是行的身份键。
两边分支通常各自改了**不同 goal** 的行（fork 重放 churn vs 上游 churn 互不重叠），
逐 goal 三方合并可以把绝大多数"文本冲突"自动消解：

- 只在一侧出现的 goal    -> 取该侧行（按出现顺序追加到对应位置）
- 两侧相同               -> 取任一侧
- 一侧改、一侧未改       -> 取改的那侧
- 两侧都改得不同         -> 冲突（标记）

Git 用法（.gitattributes）:
    **/certs/*.jsonl  merge=acorn-jsonl
    [merge "acorn-jsonl"] driver = python3 .../jsonl_merge_driver.py %O %A %B

退出码: 0 = 干净；1 = 存在冲突（带标记结果已写入 %A）。
"""

import argparse
import json
import sys


def load(path):
    """返回 {goal: line_text, order: [goal,...]}；保留原始行文本。"""
    records = {}
    order = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                goal = rec.get("goal")
            except json.JSONDecodeError:
                goal = None
            if goal is None:
                goal = "__unparsed:" + line[:80]
            if goal not in records:
                records[goal] = line
                order.append(goal)
    return records, order


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("ours")
    ap.add_argument("theirs")
    args = ap.parse_args()

    b_rec, b_order = load(args.base)
    o_rec, o_order = load(args.ours)
    t_rec, t_order = load(args.theirs)

    goals = list(b_order)
    for g in o_order:
        if g not in goals:
            goals.append(g)
    for g in t_order:
        if g not in goals:
            goals.append(g)

    conflicts = []
    out_lines = []
    for g in goals:
        b, o, t = b_rec.get(g), o_rec.get(g), t_rec.get(g)
        if o is None and t is None:
            continue
        if o == t:
            out_lines.append(o if o is not None else t)
            continue
        if b == o:
            out_lines.append(t)
            continue
        if b == t:
            out_lines.append(o)
            continue
        if o is None or t is None:
            # 一侧删除、一侧修改 -> 取修改侧（删除通常由 verify 重建，保守取修改侧）
            out_lines.append(o if o is not None else t)
            continue
        # 真冲突：两侧都改了同一 goal 且不同
        conflicts.append(g)
        out_lines.append(f"<<<<<<< ours {g[:60]}")
        out_lines.append(o)
        out_lines.append("=======")
        out_lines.append(t)
        out_lines.append(f">>>>>>> theirs {g[:60]}")

    with open(args.ours, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))
        if out_lines:
            f.write("\n")

    for g in conflicts:
        print(f"CONFLICT goal: {g[:120]}", file=sys.stderr)
    print(f"jsonl_merge_driver: {len(out_lines)} lines, "
          f"{len(conflicts)} unresolved conflicts", file=sys.stderr)
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
