# 实验：上游合并干跑分析 + JSONL 证书合并驱动

- 日期：2026-08-06
- 仓库：acornlib-omega（HEAD a9186ce1）vs `upstream/master`（f32b0ac9）
- merge-base：ed6fe37a（"migrate to format 27"）

## 合并冲突全景（git merge-tree --write-tree，不碰工作区）

| 类型 | 数量 | 性质 |
|---|---|---|
| .ac 源码冲突 | **6** | 真实语义冲突，需人/agent 处理 |
| manifest.json 冲突 | 19 | 每 key 三方合并驱动可消解大部分 |
| 证书 .jsonl 冲突 | 82 | **按 goal 键三方合并驱动可消解大部分** |
| 合计 | 107 | 94% 是派生文件，机械可解 |

结论：**上游合并的"冲突墙"几乎全部来自证书/manifest 派生文件**——这正是
`jsonl_merge_driver.py` 与 `manifest_merge_driver.py` 存在的意义。

## JSONL 合并驱动实测（真实冲突文件）

| 文件 | 行数 | 未解决冲突 | 说明 |
|---|---|---|---|
| src/certs/add_comm_monoid.jsonl | 54 | 5 | fork churn 与上游 churn 大多不重叠 |
| src/certs/affine_subspace.jsonl | 817 | 18 | |
| src/polynomial/certs/root_bound.jsonl | 147 | 1 | 无 base 版本（两侧新增不同内容） |

未解决的 goal = 两侧真正改了同一条声明，正确出路是合并后对受影响模块跑
`verify` 重新生成（其余全部闭包 `check --strict` 0 searches 重放）。

## 对 29 步吸收计划的意义

- chunk 25（根级删除型简化扫描）的"冲突墙"主要就是这些派生文件；现在有工具了。
- 合并流水线（merge_pipeline.py）接入两个驱动后：
  `git merge --no-commit`（driver 自动处理 manifest+jsonl）→ 冲突门
  → 只处理残余 ~6 个 .ac 冲突 → 闭包 verify → 全库 strict（1m43s）。
- 全库 strict 门 1m43s 意味着"每批一次全库门"完全可负担。

## 工具

- `tools/merge/jsonl_merge_driver.py`：按 goal 键 3-way 合并（.gitattributes:
  `**/certs/*.jsonl merge=acorn-jsonl`）
- `tools/merge/manifest_merge_driver.py`：manifest 每 key 3-way 合并
- `tools/merge/conflict_marker_gate.sh`：残余标记门
