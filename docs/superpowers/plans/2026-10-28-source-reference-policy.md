# 来源分层与生成容错 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** 区分知识依据与背景参考，允许有教学依据的相邻扩展，避免单个额外引用中断整轮。
**Architecture:** generation-v3 冻结来源策略；保留 evidence_ids 为学术/教学依据，新增 background_references。来源异常进入候选检查与既有一轮修复，而非成对题答结构异常。旧任务、报告与授权不变。
**Tech Stack:** Django / Pydantic / React / Vitest / pytest / Playwright，无新依赖或迁移。
**Spec:** 本会话 2026-10-28 用户要求；docs/round-1-design.md；docs/superpowers/plans/2026-10-24-batch-4-question-generation.md。

## Global Constraints
- 背景参考不受课程或题目来源白名单约束；可以是外部文献、通用情境、课程背景。未经验证不声称官方或已核实；不自动联网抓取。
- 学术依据需要支撑主要知识点。少量辅助/相邻扩展可接受，由语义核验说明；不设未经确认的百分比阈值。
- 没有核心教学依据、实质偏离知识目标、缺少必需核验仍阻止发布，但保存候选并允许既有一轮定向修复。
- 新来源策略/提示词/schema 进入 context hash；不复用旧授权为新上下文自动调用模型。
- 保留材料、历史任务及模型原始返回；答案与可能泄露答案的背景说明在主动打开答案后展示。
- 使用当前 dev 工作区，单人顺序修改；用户已要求直接实施，无需再次确认执行方式。指定执行子技能未安装，按现有项目工作流执行。

## Review Focus
- 课程背景带有题外 ID：只记录来源提示，不中断；能进入完整候选及核验（Task 1/2）。
- 外部背景 URL/未知引用：不作教学证明、不自动抓取、不生成危险链接（Task 1/3）。
- 所有学术依据均缺失或实质越界：候选可见、报告阻止发布、定向修复（Task 2）。
- 一条语义检查引用不合法：不污染其他题目的全部检查（Task 2）。
- 历史数据缺少新字段/刷新/答案隐私/来源版本：可读兼容，旧终态不改（Task 3/4）。

### Task 1: 来源契约与生成输入
**Files:** 新增 backend/app/generation/source_policy.py；修改 content_schemas.py、content_validation.py、execution_context.py、generator.py、runtime.py、content_fixtures.py、AI prompts；新增 backend/tests/test_generation_sources.py。
**Interfaces:** source_diagnostics(context, pair) 返回确定性分类；source_review_input(context, pairs) 返回分类与有界证据摘要；source_catalog(context) 提供冻结元数据。
- [x] 写失败测试：额外背景 ID 不中断，未知引用保留诊断，无教学依据不获放行。
- [x] 运行测试确认失败，再实现契约、冻结策略与提示词。
- [x] 验证 schema 所有字段显式 required；旧 payload 在本地校验入口补空背景字段，原记录不变。

### Task 2: 核验、局部修复与版本
**Files:** 修改 checks.py、reviewer.py、repair.py；扩展 source tests / execution tests。
**Interfaces:** 必需 source_basis 本地检查与 source_alignment 语义判断；非必需来源提示。引用警告不等于学术正确性通过。
- [x] 添加场景：核心+相邻依据可通过模拟语义判断；背景不替代核心依据。
- [x] 添加场景：必要来源判断失败只修复对应题，保留其他题；无语义结论仍阻断。
- [x] 实现来源检查与精确诊断；语义引用问题仅作用于对应检查，保留其他结论。
- [x] 冻结策略/schema 变更使旧上下文无法继续；相同新版本仍遵守复用、取消和发布机制。

### Task 3: 页面与只读接口
**Files:** 修改 content_api.py、CandidatePreview.tsx、candidate.css；新增 SourceReferences.tsx；扩展 API / React tests。
**Interfaces:** 只读候选提供学术来源状态、背景数量；答案端点提供完整背景参考及说明。
- [x] 知识依据显示 planned/additional/background-only/unresolved；未知来源无失效链接。
- [x] 背景参考独立显示，外部 URL 仅 http/https 可点击；不自动验证外部内容。
- [x] 验证隐藏答案时不提前加载背景说明/答案；同版本物理页可找回；历史字段兼容。

### Task 4: 回归、真实记录离线复核与交接
**Files:** 新增 scripts/audit_source_policy.py；更新 README.md、docs/batch-4-validation.md、docs/handoff.md。
- [x] 在内存中使用新策略校验历史任务 8f2e167c 的四组已保存返回；不改原任务、不调用模型、不宣称完整语义通过。
- [x] 后端相关测试及全量回归；前端测试/类型/构建；Django check、迁移一致性、git diff --check。
- [x] 使用合成工作区运行本地浏览器验收；保留清晰 fixture 标识，无真实模型请求。
- [x] 复用本地服务，展示页面，记录实际结果；提交并 push。

拟运行命令（执行后在验证记录登记实际结果）：
- .venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests/test_generation_sources.py -q
- .venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests -q
- pnpm --dir frontend test --run
- pnpm --dir frontend build
- .venv/Scripts/python.exe scripts/audit_source_policy.py 8f2e167c-6d30-4dcf-9bcb-70caacd7c59e


执行记录：2026-10-28 完成四项；后端207 / 前端16通过，浏览器7组通过，真实历史四组结构离线通过；详见 docs/batch-4-validation.md。本次0真实模型请求。当前只实现来源异常的可继续核验/定向修复，不泛化为任意损坏 schema 的无限重试。执行子技能未安装，按用户直接实施授权和项目单写入规则在本会话完成。
