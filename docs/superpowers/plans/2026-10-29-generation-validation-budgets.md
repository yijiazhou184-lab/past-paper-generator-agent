# Generation validation budgets and progress implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.
>
> 用户已确认范围并要求本会话直接实施，沿用原生执行。当前没有上述子技能；按下面文件、接口和验证步骤完成，不再次等待方案批准。

**Goal:** 同一次 Generate 内完成紧凑、可拆分、可追踪的必要检查；可选检查预算不足可跳过。
**Architecture:** 保留 CandidateVersion / CheckReport 不可变语义，GenerationArtifact 保存各检查阶段。generation-v4 冻结检查策略、提示词和 schema；必要请求计数超限后二分，分组后做整卷检查。
**Tech Stack:** 既有 Django / PostgreSQL / Pydantic / React / pytest / Vitest / Playwright，不加依赖。
**Spec:** docs/round-1-design.md、docs/PRD-v1.0.md，以及 2026-10-29 会话确认。用户确认的新必要/可选分类优先；不新增仅核验入口、任务或恢复流程。

## Global Constraints
- 保持 60,000 input / 12,000 output、16 次模型调用、600 秒任务、240 秒单次、一次修复轮次。
- 必要：结构与分值、核心数学与条件、盲解一致性、知识与方法/明确偏好、基本难度、实质原创性、整卷一致性。
- 可选：措辞润色、额外解法建议、细粒度难度建议、非必要背景引用补充核实。解题所需事实仍属必要检查。
- 可选仅在必要全部通过后运行，最多一次请求，20,000 input / 4,000 output、至少 60 秒剩余时间；不足或服务失败记 not_checked。
- 必要分类由代码确定，not_checked/inconclusive/不合法 not_applicable 不能放行。
- 保留来源分层、小幅合理扩展、原材料与历史结果、版本冻结、取消/租约/幂等、未知结果不自动重放。
- 仅对确定的输入计数超限自动拆分；不静默删减必要内容；新策略需新 context hash。
- 英文产品；答案、检查推理和可透露答案的细节须主动打开。
- 历史任务 32bb6d9c 仅离线回放，不改写、不新增真实调用、不冒充新验收。

## Review Focus
- 单题仍超限：保留阶段成果且不放行（Task 2/3）。
- 可选失败不降级必要项，取消/完整性错误必须传播（Task 2/3）。
- 分组漏题、重复类别、遗漏整卷检查阻止发布（Task 2）。
- worker 取消/租约过期不得写阶段与最终报告（Task 3）。
- 阶段更新、刷新不得泄露答案或一直显示旧报告（Task 4）。

## Task 1: Frozen policy and compact input
**Files:** create backend/app/generation/review_policy.py, review_input.py; modify content_schemas.py, content_fixtures.py, execution_context.py, runtime.py, backend/app/ai/prompts/semantic_review.md; test backend/tests/test_generation_review_input.py.
**Interfaces:** build_review_input(context, payload, local, blind, duplicates, question_ids, mode='required') -> dict; compact_expression(node) -> str; REVIEW_POLICY / REQUIRED_CATEGORIES / OPTIONAL_CATEGORIES.
- [x] 先写断言：不丢数学运算树/定义域、相关知识筛选、材料去重及用途/版本绑定、无 SVG、无原地修改。
- [x] 确认新测试失败后实现确定性投影；原 AST 继续保存并用于本地检查。
- [x] generation-v4 冻结新策略与 schema，旧授权不复用；运行来源和上下文回归。

## Task 2: Bounded required and optional review
**Files:** create backend/app/generation/semantic_review.py; modify reviewer.py, repair.py, runtime.py, backend/app/ai/invocations.py; test backend/tests/test_generation_review_budget.py.
**Interfaces:** run_semantic_review(...) -> (checks, repair_requests); run_optional_review(...) -> checks; normalise_review(...) -> checks.
- [x] 测试整卷超限后二分到组/题，分组后整卷核验；单题超限如实失败；不重试未知付费结果。
- [x] 初始必要请求一次；只对 TOKEN_BUDGET_EXCEEDED 拆分，最多四题/深度二。
- [x] 代码决定必需类别覆盖；缺项/重复/来源不足阻塞。
- [x] 必要通过后可选请求，预算不足跳过；不后台补跑。
- [x] 修复前预留最坏调用数：2*修复题数 + 必要复核最坏次数；不足保留报告。
- [x] 计数遵守更小的阶段输入限额和任务剩余时间；全部生成仍走总预算。

## Task 3: Durable stages and partial reports
**Files:** create backend/app/generation/check_progress.py; modify reviewer.py, checks.py, content_api.py; test backend/tests/test_generation_check_progress.py.
**Interfaces:** save_check_stage(token,candidate,name,checks,**details); progress_report(candidate) -> dict | None.
- [x] 保存结构、数学、盲解、检索、语义分组、可选阶段 artifact，绑定候选 hash/策略。
- [x] 部分报告 complete=false，含必要待检查占位；最终 CheckReport complete=true。
- [x] 错误说明已保存题答和停止阶段，保留错误 code。
- [x] 测试取消/过期 token、幂等与校验、旧记录兼容、部分结果 API 隔离。

## Task 4: Existing UI and integration
**Files:** modify frontend/src/features/generate/CandidatePreview.tsx and CandidatePreview.test.tsx; add scripts/test_review_budget_view.py / fixture helper as needed; update README.md, docs/batch-4-validation.md, docs/handoff.md.
- [x] 展示阶段进度、必要/可选结果和跳过提示；无 Resume validation。
- [x] 用报告版本更新已打开的详情；刷新默认关闭答案。
- [x] 前端断言覆盖部分报告、可选跳过成功、主动答案、最终轮询。
- [x] 旧真实候选离线回放，记录输入尺寸及数学结果；无 API。
- [x] 后端测试、前端测试/类型/构建、Django check/迁移检查；启动已有服务并检查合成成功/中断页面。
- [x] 文档分清真实历史/离线回放/fixture；提交并 push。

拟执行命令（完成前不代表已运行）：
```powershell
& .\.venv\Scripts\python.exe -m pytest backend/tests -q -c backend/pytest.ini
pnpm --dir frontend test --run
pnpm --dir frontend typecheck
pnpm --dir frontend build
& .\.venv\Scripts\python.exe backend/manage.py check
& .\.venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run
& .\.venv\Scripts\python.exe scripts/local.py start
```


## 执行结果（2026-10-29）

四项任务已实现。最终后端225 passed（248.24秒），前端19 passed，类型/构建/Django/迁移检查/OpenAPI通过；Playwright6组通过，0 JS错误、0登录后写请求。无依赖和数据库迁移，无真实模型或官方计数调用。真实旧候选离线回放从201,697降至174,982字符，8项结构/引用基础与26项数学检查通过；新真实token数与语义质量未验证。合成页面及下一步见docs/handoff.md，详细证据见docs/batch-4-validation.md。模型名称和官方目的地未改变。

实现中补充：分组来源判断只接受当前输入实际包含的证据；不支持紧凑表示的数学规格保留原AST，避免诊断/修复依据丢失。最终API schema未变化，无需生成新客户端类型。
