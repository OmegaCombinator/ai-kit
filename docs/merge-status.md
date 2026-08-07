# 上游吸收完成 ✅（2026-08-07）

## 结果

`OmegaCombinator/acornlib-omega` main: `a9186ce1..74687ddb`（merge upstream/master f32b0ac9）

- **101653/101653 OK**（verify），`check --strict` **0 searches**（3m19s @ -j8）
- 比 fork 原版多 ~2500 个目标（上游新增定理/简化吸收）
- fork 独有内容完整保留；上游简化（proof-local 删除）吸收
- erdos396.ac（6 月战役移植）暂缓：其证明引用合并前的 list/nat API，
  保存在 `translate/erdos396-pending/` 待适配

## 工具链成果（全部实测）

1. **manifest/jsonl merge driver**：证书按 goal 键三方合并（修复 delete-side bug）
2. **union_sources.py**：接口文件声明级并集（fork 源码保序 + 上游独有声明追加；
   修复 attributes 复数、instance 同名、多行参数截断三个 bug）
3. **fix_certs.py**：按"源码来源"恢复对应侧完整证书（union 会丢目标）
4. **merge_repair.sh / unblock_merge.py**：收敛循环
5. **acorn 0.2.6 `--save-partial`**（增量搜索补丁，patches/0001）：
   搜索失败时保存已证目标证书，下次续搜——实测 3624 goals 的模块，
   清空证书后第一轮存 11/15 行，第二轮只搜缺失 4 个

## 关键教训

- 证书必须整库用同一版本生成（0.2.4/0.2.6 格式不同）
- 接口文件的正确合并 = fork 完整源码 + 上游独有声明追加（不是单侧）
- 上游独有接口声明若依赖 fork 没有的上游 API → 保留 fork 接口、排除该上游模块
- 全库 strict 门 3m19s 使"每批一次全库门"完全可负担

## 下一步

src/ 重组（org_map.json 已备好，535 模块领域映射）→ move_module.py 逐批移动。
