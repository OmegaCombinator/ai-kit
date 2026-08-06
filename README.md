# ai-kit — 工具与知识库，服务于 Acorn / acornlib 的 AI 驱动形式化

`ai-kit` 是 OmegaCombinator 组织下为 **Acorn 证明助手**（Rust 实现，ML 引导证明搜索）及其标准库
**acornlib** 准备的开放工具箱与知识库。它的目标是把"多智能体形式化战役"从手工密集型流程，
变成一套可复用、可验证、可持续的工具链。

## 背景与问题

- Acorn 标准库由多智能体系统 Suzumio 驱动（PM + formalizer-N + scout + verifier + librarian + devops），
  以"数学领域分支"的形式持续产出（2026-06 战役：46 个 accepted refs，~+15k 行源码）。
- 瓶颈不是"写证明"，而是**合并与证书重放**：证书（`src/<module>/certs/<module>.jsonl`，
  manifest 用 blake3 内容寻址）在每次上游合并/重构后都要重放（`check --strict`，0 searches），
  全库约 10 万条定理，成本极高。
- Acorn 证书的设计（每 claim 一条 goal+proof，按名字解析，官方注明"对重构稳健"）是业内最好的形状之一
  （按语句粒度重放只有 Metamath 能做到），**缺的是工具化**。

## 仓库结构

```
docs/                   知识库与路线图
  roadmap.md            主路线图（优先级排序）
  research/             三份调研报告（自动合并 / 并行形式化 / Erdős 单位距离反例）
  acorn-tools-proposal.md   39 个 acorn-tools 子命令提案（AST parser、downstream-checks 等）
tools/                  可执行工具
  merge/                合并自动化：manifest merge driver、冲突门、影响面计算
  refactor/             AST 重构工具（规划中，见 docs/roadmap.md）
patches/                Acorn 编译器/CLI 补丁（规划中）
trackers/               战役进度与 PR 追踪存档
translate/              实际翻译/形式化工作（规划中）
```

## 快速开始（合并工具）

```sh
# 1. manifest.json 每 key 三方合并驱动
python3 tools/merge/manifest_merge_driver.py --help

# 2. 安装为 git merge driver（.gitattributes + gitconfig）
cat >> .gitattributes <<'EOF'
build/manifest.json      merge=acorn-manifest
**/certs/manifest.json   merge=acorn-manifest
EOF
git config merge.acorn-manifest.driver \
  "python3 $PWD/tools/merge/manifest_merge_driver.py %O %A %B"

# 3. CI 冲突标记门（任何 jsonl/manifest 出现 <<<<<<< 即失败）
bash tools/merge/conflict_marker_gate.sh

# 4. 影响面计算（给定改动模块，输出需重验的依赖闭包）
python3 tools/merge/impact_closure.py --root acornlib --changed src/list/list_sum.ac --json
```

## 原则

- **验证门不可省**：合并结果必须过 `check --strict`（0 searches）；工具只减少重放范围，不取消验证。
- **先工具后内容**：优先建设能复用的工具，再用工具加速内容生产。
- **机械的归脚本，语义的归人/agent**：纯机械部分（源合并、manifest 驱动、冲突检测）自动化；
  语义冲突与证明修复留给 agent + 人工评审。
- **内容寻址是核心**：manifest 的 blake3 哈希就是缓存键；未变的模块可证明不受影响。
