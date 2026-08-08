# 上游 PR：verify --save-partial

- PR: https://github.com/acornprover/acorn/pull/63
- 分支: OmegaCombinator/acorn#feat/verify-save-partial（基于 v0.2.6）
- 内容: verifier.rs + bin/acorn.rs（25 行）——搜索失败时保存已证证书，增量续搜
- 测试: nat/semiring 3624 goals，清空证书后存 11/15 行，二轮只搜缺失 4 个
- cargo fmt/check/test（1419）全过
