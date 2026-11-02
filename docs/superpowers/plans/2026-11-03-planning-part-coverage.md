# Planning Part Knowledge Aggregation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 模型只填写每小问实际考核的知识点，程序汇总大题和整卷覆盖。

**Architecture:** 将新模型输出与现有存储蓝图分开。新输出省略 question.knowledge_ids 和 coverage；程序从 parts 派生后进入现有蓝图校验/保存。编辑保存也重算这两个派生字段；冻结历史只读验证保持原状。

**Tech Stack:** Python / Django / Pydantic / pytest；不新增依赖。

**Spec:** 本侧聊用户 2026-11-03 的明确决定（不判断主考/辅助；不固定每大题的知识分配），以及 docs/batch-6-live-start-2026-11-02.md 的原故障证据。此用户决定覆盖旧验收矩阵中逐大题知识分配。

## Global Constraints

- 只改此知识覆盖契约及相应测试/交接；不改来源转写、题量分值或模型运行限额。
- 小问仍须使用选定知识和有效教学证据，每种合法选答必须覆盖全部已选知识与题型。
- 既有 blueprint-v1/v2 存储和历史任务/原始模型响应不改写；新规划 schema/prompt/hash 另版本。
- 无真实模型调用、业务任务提交、服务重启或业务数据修改。
- 本侧聊由当前助手本人执行，不使用子代理，不沿用父线程的后续开发授权。

## Review Focus

- 模型 schema 不再要求或允许重复汇总知识字段：检查 schema 字段及多小问汇总。
- 小问有多个知识、重复/顺序不同：汇总稳定且去重，输入对象不变。
- 小问越界或教学证据不足：原必要校验继续拒绝。
- 编辑删除/改动小问后旧汇总失效：保存重算；冻结 v1/v2 不被自动纠正。
- 旧任务/授权：新输出 schema/hash 不套旧预检；验收只约束整卷知识，不锁定逐大题分布。

---

### Task 1: 新模型契约与程序汇总

**Files:** backend/app/generation/schemas.py；backend/app/generation/planning.py；backend/app/generation/snapshots.py（仅确有必要时）；backend/app/ai/prompts/blueprint.md；backend/tests/test_planning_coverage.py。

**Interfaces:** 新 PlanningOutput 使用仅小问含 knowledge_ids 的输出结构；materialize_planning_blueprint(payload) -> dict 返回现有 blueprint-v2。validate_blueprint(..., recalculate=True) 重算知识汇总，普通冻结校验保持严格。

- [x] 编写 schema、稳定汇总、非法知识/证据、编辑重算、旧版严格校验测试并确认失败。
- [x] 实现新 schema、纯函数汇总、新规划版本、提示词和正常保存接线；不删除小问知识。
- [x] 运行新测试和 planning/blueprint/snapshot 定向回归；模型传输仅 mock。

### Task 2: 验收分配与交接

**Files:** evals/round1/run.py；evals/round1/manifest.yaml；backend/tests/test_eval_accounting.py；README.md；docs/handoff.md；本计划。

**Interfaces:** check_matrix 继续校验大题数、小问/分值、时间和锁定状态；知识只按整卷 run.knowledge 校验，不再读取 question_knowledge 分配。

- [x] 补任意逐题分配但整卷覆盖正确、整卷漏项/越界仍拒绝的测试并确认失败。
- [x] 删除当前 manifest 的固定逐题分配，保存新 policy 字段；旧运行私有快照不变。
- [x] 运行专项回归；离线回放原失败响应，记录它通过新覆盖契约但仍需按题量/分值编辑的边界。
- [x] 更新 README/交接/检查记录，明确没有重跑真实任务、没有重启服务。
- [x] 核查仅本次文件进入稳定提交并 push；其他用户文件保持。

执行说明：用户已经明确要求本局部实施，按该授权直接执行；技能中的额外实施选择不再重复询问，也不启用本侧聊禁止的子代理。以上仅为本次实现说明，不是新的真实 API 授权。


## 实际实施与验证

- 实现文件：backend/app/generation/schemas.py、planning.py、backend/app/ai/prompts/blueprint.md；未改 snapshots.py，因为既有编辑入口已经使用 recalculate=True，直接接入新增汇总逻辑。
- 验收文件：evals/round1/run.py、manifest.yaml；新增 backend/tests/test_planning_coverage.py。test_eval_accounting.py 仅修正两个夹具的 finished_at 在创建前生成导致偶发负耗时的问题，未修改记录器或真实计时要求。
- 新模型输出只要求每 part 的 knowledge_ids；question-level IDs 和 coverage 在新输出中禁止填写。派生函数不修改原输入，排序去重，不推断额外知识。保留所有选定范围、教学证据、题型和合法选答检查；没有引入主考/辅助分类。
- 新冻结版本 planning-v3-part-coverage / r1-planning-3-part-coverage / part-knowledge-union-v1；blueprint_schema_version=blueprint-v2。模型 schema/prompt 新 hash 与旧授权不同；当前 manifest 删除逐大题分配产生新基线，旧私有快照不变。
- 初始 9 项新规则测试在旧实现下失败，另修正新测试模块导入路径后单独复现旧逐题分配错误。首次批量运行暴露上述两个旧夹具的时间顺序问题；修正夹具后最终结果如下。未把失败尝试计为通过。
- 定向命令已运行：.venv/Scripts/python.exe scripts/test_batch5_backend.py -c pytest.ini tests/test_planning_coverage.py tests/test_planning_execution.py tests/test_blueprint_rules.py tests/test_generation_snapshot.py tests/test_eval_accounting.py -q。
- 结果：61 passed / 20.87 秒，独立随机 PostgreSQL 测试库，测试移除真实密钥并阻断未 mock 的官方 API。Django check 0 issues，git diff --check 通过；没有重新跑后端全库、前端构建或浏览器测试，因为本次没有前端改动。
- 原 R1 保存响应离线验证：旧结构复现 QUESTION_COVERAGE_MISMATCH；仅去除原模型重复汇总字段，保留所有小问目标，再经新契约派生后通过原正常验证。原 Task 仍 failed，原响应/预检文件 hash 不变；11 小问/48 分/80 分钟未自动采用，也没有宣称满足数值矩阵。
- 私有回放记录：var/planning-part-coverage-offline-2026-11-03.json（Git 忽略），调用记录前后均 188，无新模型调用。
- 本次没有写生产 Task / Blueprint / CourseVersion，没有重启 API/worker 或调用真实模型，没有处理 E1 页图来源哈希问题。运行中的服务须在主线程正常安全重载时加载此代码，后续真实调用先生成新预检。
