# 上游 PR：verify --save-partial

- PR: https://github.com/acornprover/acorn/pull/63
- 分支: OmegaCombinator/acorn#feat/verify-save-partial（基于 v0.2.6）
- 内容: verifier.rs + bin/acorn.rs（25 行）——搜索失败时保存已证证书，增量续搜
- 测试: nat/semiring 3624 goals，清空证书后存 11/15 行，二轮只搜缺失 4 个
- cargo fmt/check/test（1419）全过

## 上游 Issue #64：∈ 糖 replay 不稳定

- https://github.com/acornprover/acorn/issues/64
- 现象：模块移动后 `check --strict` 对 `x0 ∈ Ideal.zero[T0]` 目标 replay 失败
  （certificate trace br step does not apply——reduction 产生逆否方向，
  canonical 比较不等价）
- 分析：∈ 是 contains 语法糖；证书 goal 无类型信息，re-elaboration 不稳定
- 建议修复方向：① claim 序列化时脱糖为 .contains 形式；② trace 步骤比较
  对布尔等值归约方向不敏感；③ 查 skolem 结构随实例作用域变化的原因
