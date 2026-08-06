# tools/merge — 合并自动化工具集

把"手工合并 46 个分支 + 每次全库 strict"降为"机械合并 + 闭包定向重证 + 全库门"。

## 组件

| 工具 | 作用 | 输入 → 输出 |
|---|---|---|
| `manifest_merge_driver.py` | manifest.json 每 key 递归三方合并（git merge driver） | `%O %A %B` → 合并结果写回 `%A`；冲突退出码 1 |
| `conflict_marker_gate.sh` | CI 门：任何 jsonl/manifest 出现 `<<<<<<<` 即失败 | git 跟踪文件扫描 → 0/1 |
| `impact_closure.py` | 依赖闭包影响面计算 | `--changed` 或两份 manifest → 拓扑序受影响模块 |
| `merge_pipeline.py` | 端到端流水线（规划中） | 分支列表 → 报告 |

## manifest merge driver 安装

```sh
# 仓库根目录 .gitattributes
cat >> .gitattributes <<'EOF'
build/manifest.json       merge=acorn-manifest
**/certs/manifest.json    merge=acorn-manifest
EOF

# gitconfig（仓库级）
git config merge.acorn-manifest.driver \
  "python3 $PWD/tools/merge/manifest_merge_driver.py %O %A %B"
git config merge.acorn-manifest.name "Acorn manifest per-key 3-way merge"
```

语义要点：只有同模块 hash 在两侧都被改且改得不同才冲突（保留上游无关模块 churn，
只加本分支自己的模块——与 acornlib 既有合并规则一致）。

## 合并流水线（推荐顺序）

```
① git merge <branch>            # .ac 源合并（通常干净）
② merge driver 处理 manifest    # 见上；冲突时按标记人工/agent 解决
③ conflict_marker_gate.sh       # 任何残留标记即失败
④ impact_closure.py             # 计算受影响闭包
⑤ 闭包定向 verify（串行！写 manifest 有竞态）
⑥ 全库 check --strict -jN       # 只读，可并行；要求 0 searches
⑦ 通过才 merge（merge queue / bors 风格）
```

## 实测数据（acornlib-omega，2026-08）

- 模块 DAG：312+ 个 .ac 文件，import 语法 `from <module> import <name>`
- manifest：根 `build/manifest.json` = `{version, modules: {mod: blake3}}`；
  模块级 `src/<mod>/certs/manifest.json` = `{interface, implementation: {file: hash}, dependencies}`
- 预期自动化比例：50–70% 全自动 / 20–35% 半自动 / 5–15% 人工
