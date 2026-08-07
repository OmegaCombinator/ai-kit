# 增量搜索：acorn verify --save-partial（acorn 0.2.6 补丁）

> 需求来源：合并上游时搜索超时丢失已证目标，每次重跑全量重搜。
> 用户建议：搜索失败时保存已找到的部分结果，下次增量续搜。

## 机制（源码调查）

- `verify` 逐 goal 搜索（`verify_lowered_items` 循环不提前中止），已证目标
  累积在 `new_certs`（builder.rs）；
- 但落盘门在 verifier.rs：`if !self.builder.status.is_error() { update_build_cache }`——
  **只要有一个 goal 失败，整个模块的缓存都不保存**，已证目标全部丢弃；
- `update_build_cache` → `save_merging_old` 本身支持"合并旧证书+写新 JSONL"；
  失败模块（content_hash=None）不写 manifest 条目 → 下次 verify 会重处理该模块
  并重放已保存的部分证书 → 天然增量。

## 补丁（patches/0001-verify-save-partial-incremental-search.patch）

1. `verifier.rs`：Verifier 加 `pub save_partial: bool` 字段；
   落盘门改为 `!status.is_error() || save_partial`；
2. `bin/acorn.rs`：Verify 加 `--save-partial` flag；
   `write_cache` 在 save_partial 时置真；`--read-only` 与 `--save-partial` 互斥。

## 实测（acorn 0.2.6 + 补丁，fork-clean 树 nat/semiring，3624 goals）

| 步骤 | 结果 |
|---|---|
| 清空证书 + `--ignore-hash --save-partial` | 3620/3624 证出，4 超时；**证书落盘 11/15 行（已证部分）** |
| 再次 `--ignore-hash --save-partial` | **只搜索缺失 4 个**，3620 个从缓存重放 |

## 使用

```sh
# 对超时模块反复跑，每轮只搜剩余目标，收敛到全证
acorn verify --save-partial src/nat/semiring.ac
# 批量：for f in $(cat failing.txt); do acorn verify --save-partial $f; done
```

## 构建

```sh
# acorn 0.2.6 源码（git worktree @ v0.2.6）
cargo build --release --bin acorn
# 二进制存档：workspace/acornlib/bin/acorn-0.2.6-save-partial-linux-x64
```
