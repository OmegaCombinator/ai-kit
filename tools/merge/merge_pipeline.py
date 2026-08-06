#!/usr/bin/env python3
"""merge_pipeline.py — Acorn 分支合并流水线（机械部分编排）。

把"手工合并分支 + 每次全库 strict"降为：

    ① 源合并       git merge --no-commit <branch>（.ac 源，通常干净；
                   manifest.json 由 git merge driver 处理，见 tools/merge/README.md）
    ② 冲突门       conflict_marker_gate.sh（任何 jsonl/manifest 残留标记即失败）
    ③ 影响面       由 manifest diff 求改动模块 → impact_closure 求受影响闭包
    ④ 定向重证     闭包内模块按拓扑序 verify（写 manifest，必须串行）
    ⑤ 全库门       check --strict -j N（只读，可并行；要求 0 searches）
    ⑥ 报告         输出 totals / searches / elapsed

用法:
    merge_pipeline.py --repo <acornlib> --branch <name>
                      [--acorn <bin>] [--strict-jobs 8]
                      [--dry-run] [--commit "msg"] [--json]

注意: 本脚本不改 git 历史，只跑验证并报告；落地（merge/commit/push）由
调用方/CI 决定，或在 --commit 显式给出时执行。
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "conflict_marker_gate.sh")
IMPACT = os.path.join(HERE, "impact_closure.py")


def sh(repo, args, timeout=3600, check=True, capture=True):
    r = subprocess.run(args, cwd=repo, capture_output=capture, text=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError(f"command failed ({r.returncode}): {' '.join(args)}\n"
                           f"{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r


def git(repo, *args, **kw):
    return sh(repo, ["git", *args], **kw)


def changed_ac_files(repo, base, head):
    """两个 ref 之间改动的 .ac 文件列表（相对路径）。"""
    r = git(repo, "diff", "--name-only", base, head)
    return [l for l in r.stdout.splitlines() if l.endswith(".ac")]


def main() -> int:
    ap = argparse.ArgumentParser(description="Acorn merge pipeline (mechanical part)")
    ap.add_argument("--repo", required=True, help="acornlib 仓库根")
    ap.add_argument("--branch", required=True, help="要合并的分支名")
    ap.add_argument("--acorn", default=os.environ.get("ACORN_BIN", "acorn"))
    ap.add_argument("--strict-jobs", type=int, default=8)
    ap.add_argument("--strict-scope", choices=["full", "closure"], default="full",
                    help="full=全库 check --strict（集成门，默认）；closure=只查受影响闭包（开发期快速迭代）")
    ap.add_argument("--dry-run", action="store_true", help="只报告计划，不跑验证")
    ap.add_argument("--commit", default="", help="验证通过后提交信息（可选）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = os.path.abspath(args.repo)
    report = {"repo": repo, "branch": args.branch, "steps": {}}
    t0 = time.time()

    # 0. 前置检查
    st = git(repo, "status", "--porcelain")
    if st.stdout.strip():
        print("merge_pipeline: worktree not clean", file=sys.stderr)
        return 2
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "rev-parse", "--verify", args.branch)  # 分支存在性
    base_manifest = os.path.join(repo, "build", "manifest.json")
    report["steps"]["preflight"] = {"head": head, "elapsed": round(time.time() - t0, 1)}

    # ① 源合并
    git(repo, "merge", "--no-commit", "--no-ff", args.branch)
    report["steps"]["merge"] = {"ok": True}
    # 记住合并前 manifest 以便 diff（用 git show 取 base 版）
    base_manifest_sha = None
    try:
        base_manifest_sha = git(repo, "rev-parse", f"{args.branch}^:build/manifest.json",
                                check=False)
        if base_manifest_sha.returncode != 0:
            base_manifest_sha = None
    except RuntimeError:
        base_manifest_sha = None

    # ② 冲突门
    r = sh(repo, ["bash", GATE], check=False)
    report["steps"]["conflict_gate"] = {"ok": r.returncode == 0}
    if r.returncode != 0:
        print("merge_pipeline: conflict markers found — aborting", file=sys.stderr)
        git(repo, "merge", "--abort")
        return 1

    # ③ 影响面：以 merge --no-commit 后的暂存差异为准（最可靠），
    #     .ac 文件变化 -> 模块名 -> impact_closure 求受影响闭包
    staged = git(repo, "diff", "--cached", "--name-only").stdout.splitlines()
    changed = []
    for f in staged:
        if f.endswith(".ac") and f.startswith("src/"):
            changed.append(f[len("src/"):-3].replace(os.sep, "."))
    changed = sorted(set(changed))
    closure = json.loads(sh(repo, [sys.executable, IMPACT, "--root", repo,
                                   "--changed", ",".join(changed),
                                   "--json"]).stdout)["affected_closure"]
    report["steps"]["impact"] = {"changed": changed, "closure_count": len(closure)}
    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    # ④ 定向重证（串行写 manifest）
    verify = {"modules": [], "searches": 0, "elapsed": 0.0}
    tv = time.time()
    for mod in closure:
        path = os.path.join(repo, "src", mod.replace(".", os.sep) + ".ac")
        if not os.path.isfile(path):
            continue
        r = sh(repo, [args.acorn, "verify", path], check=False)
        out = r.stdout + r.stderr
        searches = 0
        import re
        m = re.search(r"(\d+) searches performed", out)
        if m:
            searches = int(m.group(1))
        verify["modules"].append({"module": mod, "rc": r.returncode, "searches": searches})
        verify["searches"] += searches
        if r.returncode != 0:
            print(f"merge_pipeline: verify failed for {mod}", file=sys.stderr)
            git(repo, "merge", "--abort")
            return 1
    verify["elapsed"] = round(time.time() - tv, 1)
    report["steps"]["verify_closure"] = verify

    # ⑤ 全库门（--strict-scope closure 时只查闭包；check 一次一个 target，逐个跑）
    if args.strict_scope == "closure":
        targets = [os.path.join(repo, "src", m.replace(".", os.sep) + ".ac")
                   for m in closure if os.path.isfile(
                       os.path.join(repo, "src", m.replace(".", os.sep) + ".ac"))]
        if not targets:
            targets = [os.path.join(repo, "src")]
        # check 不接受目录；全库模式不带 target（默认扫 src/）
        cmd = lambda t: [args.acorn, "check", "--strict", "--jobs", str(args.strict_jobs), t]
    else:
        targets = [None]  # None -> 不带 target
        cmd = lambda _t: [args.acorn, "check", "--strict", "--jobs", str(args.strict_jobs)]
    strict = {"rc": 0, "scope": args.strict_scope, "targets": len(targets)}
    tv2 = time.time()
    for t in targets:
        r = sh(repo, cmd(t), check=False, timeout=7200)
        out = r.stdout + r.stderr
        strict["rc"] = r.returncode if r.returncode != 0 else strict["rc"]
        if r.returncode != 0:
            strict.setdefault("failures", []).append({"target": t or "src/", "tail": out[-800:]})
            print(f"merge_pipeline: strict gate failed for {t or 'src/'}", file=sys.stderr)
            break
    strict["elapsed"] = round(time.time() - tv2, 1)
    report["steps"]["full_strict"] = strict
    if r.returncode != 0:
        print("merge_pipeline: full strict gate failed", file=sys.stderr)
        git(repo, "merge", "--abort")
        return 1

    # ⑥ 提交（可选）
    if args.commit:
        git(repo, "add", "-A")
        git(repo, "commit", "-m", args.commit)
        report["steps"]["commit"] = {"ok": True}

    report["elapsed_total"] = round(time.time() - t0, 1)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"merge_pipeline: OK — changed {len(changed)} modules, "
              f"closure {len(closure)}, searches {verify['searches']}, "
              f"total {report['elapsed_total']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
