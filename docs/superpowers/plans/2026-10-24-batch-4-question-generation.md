# 批次 4：题答生成、分层核验与必要修复

> 状态：**本地实施及验收完成，真实验证待精确范围授权**（2026-10-25）。依据：[首轮计划 Task 7–8](2026-10-19-round-1-qm.md)、[round-1 设计 §5.4–5.5、§6](../../round-1-design.md)、[AI 技术方案 §5](../../ai-technical-design-v0.1.md)，以及[批次三记录](../../batch-3-validation.md)末尾已确认的“合并确认后出题”。不改写 PRD 或首轮原计划。

## 1. 目标与边界

**目标**：从已冻结的生成输入出发，生成成对的题目和答案（AI③），经过程序检查、数学检查、独立盲解、语义核验和重复检查（AI④）。必要时只做一轮定向修复。只有通过发布门槛的候选，才标记为“可发布”。

| 本批包含 | 不包含 |
|---|---|
| 合并入口：确认结构后点 Generate practice，自动冻结快照，经预检授权后出题 | Papers 存储、网页阅读页、两个 PDF（批次 5） |
| AI③ 成对题答；受控内容块；受控素材（函数图、数据表） | 六次真实验收（批次 6） |
| 程序检查、SymPy 数学检查、盲解、语义核验、重复检查、发布门槛 | 与本人历史试卷去重（Papers 未实现前，比较集合明确为空） |
| 一轮定向修复，保留候选版本链 | 多轮自动修复、人工逐卷审批 |
| Task detail 的阶段、检查摘要、候选预览（答案需主动打开） | 完整模拟卷、多章节（第二轮） |

## 2. 合并入口（已确认的决定）

- **去掉单独的 Prepare generation 按钮**。确认结构后，点 **Generate practice**：
  1. `POST /courses/{id}/generation-preflight`：冻结快照（每个结构确认对应一份，重复调用返回同一份），并据此算出本次出题要发送的精确输入和 context hash；
  2. 弹出预检对话框，列出发送内容和限额；fixture 课程不显示授权项；
  3. `POST /courses/{id}/generations`：携带 confirmation、config hash、context hash 和幂等 key。服务端核对 hash 并写入授权 `GenerationGrant`（绑定 context hash，不沿用分析或规划的授权），然后提交 `generation` 任务。
- 现有的 `POST /generation-snapshots` 保留为内部接口，测试用；历史快照仍可在页面查看。
- 课程忙碌（已有分析、规划或出题任务在跑）时，返回现有任务的链接，不会启动第二份。

## 3. 数据

- **`CandidateVersion`**（不可变）：快照、父候选（修复时）、题答 pairs、素材、内容 hash、所属阶段、产生它的调用。修复会生成新版本，旧版本保留。
- **`CheckReport`**（不可变）：绑定候选；结构同设计 §5.5，包括每项检查的方法、结果（pass / fail / not_checked / inconclusive / not_applicable）、是否为发布必需、依据，以及重复比较的集合和覆盖说明。
- **`GenerationGrant`**（不可变）：course + context hash + 精确范围。
- 生成任务的结果写入：最终候选 ID、报告 ID、门槛结论（allowed、阻塞的检查项）。**不创建 Paper**，留给批次 5。

## 4. AI③ 题答生成

- **调用分组**：每道大题一次调用，内部最多 2 个并行。输入只包含该大题需要的内容：蓝图中的这道题（含各小问的 focus）、相关知识和方法规则（含用户偏好）、相关问题项（例如原文错误的 warning），以及该题 evidence_ids 对应的页内容（有转写用转写，否则用文字；发送前按 hash 校验未变化），还有已生成其他大题的摘要，避免题目重复。**不发送页图。**
- **输出**：沿用设计 §5.4 的 `QuestionPair`。`ContentBlock` 只允许 text、math（LaTeX）、table、asset_ref，不接受 HTML 或脚本。
  - 每个小问必须有答案，包括完整推导、最终答案、评分点、可接受的替代做法、单位和精度。
  - 评分点按替代组计分，不重复计分。
  - 每道题附带 `MathCheckSpec`，用受限表达式描述可由程序核对的结果，如导数、极限、驻点、端点值。
  - 没有官方细分评分时，`marking_basis = suggested`。
- **用户偏好的落实**：涉及有争议的原文时，按“标准解释，并在答案或评分说明中注明与原文的差异”处理。标为 WRONG 的证明只能作为找错题的素材，必须新编，不能照抄。
- **素材**：`function_graph` 只接受受限表达式 AST、坐标轴、定义域和采样设置，服务端用 SymPy 和 NumPy 采样后生成 SVG；`data_table` 作为表格内容块。不执行模型给出的任何代码。不新增依赖：SymPy 和 NumPy 已在锁定依赖中。

## 5. AI④ 核验

依次执行，每一步都写入报告：

1. **程序检查**：题号和数量与蓝图一致；每个小问的分值与蓝图一致，总分正确；每个小问都有答案；评分点之和等于小问分值（替代组按组内最大值计）；知识和题型覆盖与蓝图一致；内容块与素材合法；引用的证据都在快照内。
2. **数学检查**：对 `MathCheckSpec` 用 SymPy 做符号或数值核对，限定定义域，设置超时和复杂度上限（受限 AST，禁止任意函数）。无法检查的记为 not_checked，不能算作 pass。
3. **独立盲解**：每道大题一次调用，只给题目和课程方法，**不给生成的答案**。之后由程序比较盲解和生成答案的最终结果；不一致的地方交给语义核验判断。
4. **语义核验**：整卷一次调用，检查题意是否清楚、方法是否在范围内、答案论证是否成立、难度是否符合 Exam-standard、条件是否充分、用户偏好是否落实，并判断与比较集合是否实质重复。
5. **重复检查**：比较集合由本地检索产生，从本课程的历年卷、附加题、复习题等材料中，按题干文字和数学结构（规范化后的 LaTeX 记号）取候选；报告列出实际比较了哪些材料。历史试卷集合为空时如实写明。“只换了数字、解题路径相同”判为实质重复。
6. **发布门槛**：只要有发布必需项的结果是 fail、not_checked 或 inconclusive，就不允许发布。

**修复**：门槛不通过且问题可以修复时，只对涉及的大题调用一次 AI③（同一 schema，并附上问题说明），生成新候选；然后重跑相关的数学检查、盲解，以及整卷的结构、范围和重复检查。仍不通过时，任务以 failed 或 needs_info 结束，保留全部候选和报告，**不标记“已核验”**。

## 6. 任务、限额与恢复

- 阶段依次为：Checking inputs → Generating questions and answers → Program checks → Blind solving → Semantic review → Repairing → Final checks → Complete。每个阶段都写 checkpoint；恢复时复用已完成的大题，结果不确定的调用不重放。
- 限额沿用快照中的 `r1-limits-proposal-1`：每任务最多 16 次调用（3 次生成 + 3 次盲解 + 1 次核验 + 修复时 ≤3 + 复核 ≤4），任务截止 600 秒，修复 1 轮。
- 每次 AI③ 和 AI④ 调用前，先用官方计数接口确认输入在 60k tokens 以内，与课程分析的做法一致。计数调用单独记录，不占 16 次额度。
- **建议的单次时限：生成和盲解 240 秒，核验 240 秒**。课程分析实测用了 164 秒，所以 150 秒偏紧。确认本计划即视为同意这个时限。
- PRD 的 120 秒目标针对完整出卷（含网页和 PDF）。本批串行加并行的调用很可能超过这个时间，届时如实记录实测耗时，不压缩检查步骤来凑时间。

## 7. 页面

- **Generate 页**：确认结构后显示 Generate practice。点击后弹出预检对话框，授权后跳转到 Task detail。
- **Task detail**：显示实际阶段、每次调用的记录和检查摘要（各结果的数量，以及阻塞项及原因）。候选预览默认只显示题目，答案和评分需要点 “Show answers” 才展开。门槛结论用中性措辞：通过时写 “Checks passed for this candidate · publication arrives in batch 5”，不写“已核验正确”。

## 8. 实施步骤（每步测试后单独提交）

1. **合并入口**：preflight 和 generations 接口、`GenerationGrant`、任务骨架和 fixture 适配器；移除 Prepare generation 按钮；更新 OpenAPI 和类型。
2. **AI③**：schema、提示词 `question_pairs.md`、按大题分组生成、checkpoint、程序检查、内容块与素材渲染（SVG）。
3. **AI④**：SymPy 数学检查、盲解（`blind_solver.md`）、语义核验（`semantic_review.md`）、重复检索、发布门槛。
4. **修复**：`repair.md`、新候选版本、复核范围。
5. **页面**：Task detail 的阶段、检查摘要、候选预览。
6. **验证**：后端和前端全量测试；在 fixture 课程上用浏览器走完整流程；更新 README 和验证记录。

**fixture 测试**要覆盖以下情况：
- 缺答案、小问重复、评分点重复计分、分值与蓝图不一致；
- 不安全的素材表达式；
- 输出被截断、模型拒答；
- 失败的大题重试时，不重做已完成的大题；
- 门槛对 not_checked 和 inconclusive 一律拒绝；
- 只换数字的重复题被识别出来；
- 洛必达第二次应用不成立时，判为 fail；
- 平方根求导缺少定义域时，不能判为 pass；
- 有界优化题检查了端点；
- 盲解请求中不含答案；
- 第二轮修复被拒绝；
- 取消后，迟到的结果不发布；
- 跨课程访问被拒绝。

## 9. 真实调用（实施完成后，需要你授权）

在当前已确认的结构上点 Generate practice，此时会冻结或复用快照 `7e2a758e`。我先把预检的精确输入给你看，内容包括：每道大题发送的页、知识、方法和偏好，调用上限，模型。你授权后才提交。完成后记录实际耗时、tokens、检查结果和门槛结论，并对照原页抽查题答，标注为“执行工具抽查（本次为 Codex）”，不作为认证。

## 10. 完成标准

- fixture 流程端到端可用；所有检查结果的状态彼此不混淆；门槛不放行任何未通过的必需项；修复链可以追溯。
- 真实运行一次（需授权），如实报告结果，不论门槛是否通过。
- 不声称题目质量、难度校准或两分钟目标已经达标。这些在批次 6 的六次验收中判定。

## 11. Codex 执行清单（2026-10-24）

用户已明确开始批次 4，包含计划的 240 秒单次限额。真实外发仍按第 9 节单独授权。

- [x] 1. execution_context.py、models.py、api.py、queue.py 与 Generate 页：预检、冻结、独立授权、任务骨架；test_generation_preflight.py 验证幂等、过期、忙碌和跨课程拒绝。
- [x] 2. content_schemas.py、generator.py、assets.py、question_pairs.md：成对题答、受限素材与分组持久化；test_question_pairs.py / test_generation_execution.py 验证缺答案、评分、恢复与取消。
- [x] 3. math_checks.py、checks.py、duplicates.py、reviewer.py、blind_solver.md / semantic_review.md：分层检查和门槛；test_generation_checks.py 验证定义域、端点、洛必达、盲解隔离和非通过状态。
- [x] 4. repair.md、generator.py / reviewer.py：一轮修复、候选链和重检；测试限制修复目标、拒绝第二轮、复用已完成分组。
- [x] 5. CandidatePreview.tsx、TaskPage.tsx、content API：题目与答案分离请求、主动打开答案、报告与来源；前端和浏览器测试覆盖恢复、长内容和错误。
- [x] 6. 全量后端 / 前端、fixture 浏览器流程、OpenAPI、README、batch-4-validation.md、handoff.md；精确列出实际运行及未运行项，提交并推送。

所有步骤沿用现有租约、锁、幂等和不可变数据库触发器；本地测试使用独立测试库和 fixture 课程。真实材料只按精确授权运行。实际执行结果记录在验证文档。

数学检查资料核对（2026-10-24）：SymPy 官方 [calculus](https://docs.sympy.org/latest/modules/calculus/index.html) 与 [solveset 使用指南](https://docs.sympy.org/latest/guides/solving/solve-equation-algebraically.html)。采用显式实数定义域和完整有限解集检查；不支持或无法判定时保留非通过状态。隔离子进程限制每次检查 8 秒，不将超时作为正确性证据。


执行结果（2026-10-25）：本地六步完成，详见 [第四批验证记录](../../batch-4-validation.md)。第9节的真实运行于 2026-10-25 获授权并执行一次，任务 344da144-1127-46b2-b137-4707f98a6a04 终态 failed / GENERATION_NEEDS_INFO。完整候选与原报告保留，未通过门槛；9 次模型调用、202,836 tokens、385.842 秒。2026-10-26 完成实现问题修复、195 项后端与15项前端检查及合成闭环。修复后真实模型验证尚未执行，新预检和边界见 handoff；不得把已用过的一次授权视为无限重试。符号检查启动与计算现分别限20秒和8秒，同轮复用隔离进程；真实模型/任务限额不变。


后续实测（2026-10-28）：用户明确允许修复版预检再运行一次。任务 bda61a74-c5e9-4639-adc3-08b4d35655b5 因第一题输出截断停止，第二题完整保留；2 次模型调用、57,281 tokens、158.914 秒。未进入数学/盲解/语义/修复阶段，没有完整候选或核验报告。此次已授权运行结束，未自动重试；详情以 batch-4-validation.md 最新记录为准。既有后续优化排期保持。
