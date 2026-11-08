# 通用完整模拟卷 Implementation Plan

> 按任务编号实施。每项先写针对真实行为的失败测试，再用最小改动通过测试。2026-11-09 修订版。

**目标**　任何已建立课程都能保存自己的考试结构，在现有练习流程中生成、核验并找回一份按该结构编排的模拟卷。

**架构**　新增课程级考试模板和 Generate 的 `Mock exam` 选项。模板为现有配置和蓝图提供默认结构。课程分析、任务、题答、核验、Papers 和 PDF 复用同一条流水线。

**技术栈**　现有 Django/DRF、PostgreSQL、Pydantic、React、KaTeX、Chromium 和后台任务。使用现有依赖。

**依据**　[PRD](../../PRD-v1.0.md) P0-05–12、BR-07–14，[技术设计](../../technical-design-v0.2.md)，[第二轮退出条件](../../mvp-development-rounds-v0.1.md)，[U4 实施计划](2026-11-01-course-topics-workspace.md#u4跨-topic-混合练习第二轮首批)。

## 范围与取舍

- 题量、分区、分值、时长、必答或选答、可用题型和来源由课程设置提供。模板是课程数据。生产代码、通用提示词、默认值和判断规则均使用数据里的 ID 与字段。
- 首期每个课程确认版本对应一套默认模板。支持无历史卷的手填模板，也可用该课程已有的适用分析建议预填。历史参考和手填模板保留未校准状态。完整模拟卷继续按课程材料生成新题。
- 首期沿用现有服务的 2–4 道大题和现有核验预算。这是当前执行能力。模板把分区和题位存为列表，将来扩题量只需扩规划、生成及核验的能力边界。超出当前题量时显示能力限制，保留模板供后续使用。首期包含普通 `Answer all` 与 `Choose N`；多层组合选答和独立模板提取任务留待实际需要。
- 同一套模板机制适用于单 Topic 或多 Topic 课程。题型从课程允许项与当前生成能力的交集提供。新增学科题型、特殊公式或其他作答能力按实际课程需求扩展对应环节。
- QM 只用于真实验收。上传的 2024/25 mock 是四题全必答、100 分、120 分钟，A/B 分区 55/45 分，四题分别 35/20/30/15 分。该结构来自题卷物理页 2–6，作为历史参考。QM 主课程版本 3 目前确认了 Topic 1/2；真实全范围验收前，其他纳入期末范围的 Topic 需按现有流程确认到同一版本。

## 最小契约

| 对象 | 约定 |
| --- | --- |
| 课程模板 | `exam_template` 含 `sections[]`（`id`、`title`、按顺序排列的 `question_marks[]`、`selection`）、`duration_minutes`、`question_types[]`、可选 `permitted_aids` 说明和来源。`selection` 沿用蓝图的 `{mode, choose_count}`。题量、分区与整卷的卷面分及应答分由程序计算。 |
| 保存与确认 | 模板使用独立可空 JSON 字段保存在 `CourseDraft`，用已有草稿版本保存。服务端以模板实际修改时的草稿 revision 记录模板版本。已有确认接口可显式采用，将模板及来源冻结到新 `CourseVersion.frozen_payload.exam_template`。模板修改或引用失效时提示重新确认。旧课程、旧配置、运行中的快照和历史试卷按原版本读取。 |
| 依据与状态 | 引用绑定本课程材料版本与物理页。模板展示 `current_instruction`、`historical_reference` 或 `user_entry`，分析预填属于建议。沿用课程已有范围、来源和冲突信息。已结构化登记的当前考试规则与模板冲突时显示字段原因。其余来源分歧由用户审阅。依据不足时允许确认未校准模板，保留该标识至历史与 PDF。 |
| 本次配置与蓝图 | 在现有 v2 配置加 `mock_exam` 模式，复用课程版本、Topic／知识目标、难度、题型和题量字段。课程版本已绑定模板，沿用现有结构确认和快照哈希机制。使用现有 Blueprint v2、分区与题位；每道印刷题都要有配对答案。 |
| 覆盖与选答 | 模拟卷的选择界定允许出题范围。显示必然考到、取决于选答路径、本卷未覆盖的目标。每个选择的题型至少在卷面出现一次。每条合法路径的应答总分必须相同。章节练习和 U4 保留各自已有的覆盖要求。 |
| 参数修改 | 模板未改动时，程序校验默认题位、分值与选答规则。改题量、题型、范围或结构时，沿用已有蓝图审阅，显示新旧差异并重新确认。一次出卷的变更不会改写课程模板。没有明确完整范围时，界面显示所选范围与实际覆盖。 |
| 权限与运行 | 继续使用现有本地会话、课程拥有权、精确外发预检、有限重试及唯一发布机制。分析授权与规划、生成授权分开。自动化测试使用隔离数据库并拦截真实模型调用。 |

## Review Focus

1. 没有历史卷的第二门课可保存自己的建议模板，课程 A/B 互相读不到对方的材料、模板或默认值。T1、T4。
2. 不等分选答使合法路径应答总分不同。结构确认指出冲突，不提交任务。T2。
3. 可选题全部有答案，允许范围里未考到的目标继续显示，历史内容仍按冻结版本读取。T2、T3。
4. 模板变动、再改回或材料更新后，新任务需重新确认。已保存结果和原 PDF 仍能打开。T1、T3。
5. 四题实跑触及原预算时，保留阶段成果并明确卡点。用观测结果决定下一次最小扩展。T4、T5。

## 批次 1 · 保存课程模板并复用现有蓝图

### T1 · Course profile 录入与确认模板

**新增** `backend/app/courses/exam_template.py`、`backend/app/courses/migrations/0010_exam_template.py`、`backend/tests/test_exam_template.py`、`frontend/src/features/profile/ExamTemplateCard.tsx`。**修改** `backend/app/courses/models.py`、`drafts.py`、`api.py`、`confirmation.py`、`topic_confirmation.py`，以及前端 `TopicOverview.tsx`、`types.ts`。

**接口**　`validate_exam_template(template, course, *, for_confirmation) -> dict`。复用课程草稿 PATCH，以路径 `["exam_template"]` 保存，沿用草稿 revision 和幂等键。课程确认请求可显式设置 `include_exam_template`。模型输出的 Topic 建议字段继续使用原格式。

- [ ] 测试 `test_courses_keep_independent_templates_and_only_current_evidence`。课程 A 绑定自己的历史材料页，课程 B 无样卷也能确认手填模板。拒绝跨课程来源与当前规则冲突，保留来源类型。
- [ ] 测试 `test_template_edit_is_preserved_and_requires_new_confirmation`。覆盖刷新、重分析后保留手工值、材料版本变动、编辑再改回和旧版本 hash 不变。
- [ ] 在 Course profile 增加一张课程级卡片。提供分区、各题分值、选答、时长、题型和来源字段。仅在已有建议明确适用于课程级范围时提供预填，其余情况由用户填写。使用现有保存和确认反馈。未采用草稿模板时，正常课程确认仍可继续。
- [ ] 完成条件。用户保存一次即可在之后的 Generate 中读取已确认模板。初版支持人工录入及已有建议复用。自动从任意整份样卷提取结构的覆盖单独记录，AC-05-01 仅按实际验证部分报告。

### T2 · Generate 模式、结构与选答

**修改** `backend/app/generation/schemas.py`、`config_compat.py`、`planning.py`、`snapshots.py`、`api.py`、`topic_coverage.py`，以及前端 `features/generate/GeneratePage.tsx`、`config-state.ts`、`types.ts`、`StructureSummary.tsx`。**新增** `backend/tests/test_mock_exam_structure.py` 与 `frontend/src/features/generate/MockExamStructure.test.tsx`。需要提示词补充时只在现有 `backend/app/ai/prompts/blueprint.md` 加通用规则，普通练习使用原指令路径。

**接口**　复用 workspace、config、planning-preflight、plans、blueprints 与 confirmations。根据选定课程版本返回模拟卷可用性与缺口。现有蓝图保存的分区、题位和小问为题目结构的唯一来源。覆盖摘要由现有结构与路径数据派生。

- [ ] 测试 `test_mock_inherits_two_different_course_templates`。用不同题量、时长、题型和选答的两个课程验证默认值。覆盖单 Topic 与多 Topic，确认模板未就绪时返回具体原因。
- [ ] 测试 `test_mock_rejects_unequal_choice_marks_and_out_of_scope_content`。必答区 20 分，加两道各 10 分的选一题，断言卷面 40、应答 30。把一题改成 15 分后验证冲突。另验证用户能看到未覆盖目标，U4 严格覆盖回归通过。
- [ ] 规划输入带模板摘要、允许范围和来源索引。默认以程序核对分区顺序、题位、分值、选答及时间，模型安排知识目标和小问。涉及本次改动时展示差异，沿用现有确认。缺少可用教学来源或结构无法成立时返回具体错误。
- [ ] 完成条件。选定课程后即可按模板生成结构并确认。配置修改后的旧结构不可提交，历史配置能按旧版本读取。

## 批次 2 · 复用生成核验、网页和 PDF

### T3 · 用现有流水线交付模拟卷

**修改** `backend/app/generation/execution_context.py`、`snapshots.py`、`backend/app/papers/publication.py`、`reader.py`、`render.py`，以及前端 `features/papers/PapersPage.tsx`、`PaperPage.tsx`、`types.ts`。只有测试暴露边界时才调整生成或核验模块。**新增** `backend/tests/test_mock_exam_generation.py`；浏览器回归复用现有脚本模式，新增 `scripts/test_mock_exam_browser.py`。

**接口**　复用生成预检、任务、题答和导出。快照冻结模板校准状态及本次结构。题卷与评分细则按同一版本的实际分区、题号、选答和分值呈现。

- [ ] 测试 `test_mock_saves_every_printed_pair_and_exports_both_pdfs`。可选题照样有评分细则；题卷无答案；两份 PDF 与网页同版本，均显示分区和选答。
- [ ] 测试 `test_mock_stale_template_does_not_replace_old_paper_or_exports`。新模板触发新确认，旧卷仍可读取。模拟一个 PDF 失败后同内容重试，纸卷数不变，模型调用数不变。
- [ ] 复用 U4 的证据投影，选择题目所需材料。模板结构依据与题目学术依据分别保存。选答与分值由程序复核，必要的数学／语义核验、定向修复和实际进度沿用。剩余预算不足时继续记录具体阶段和候选状态。
- [ ] 网页保留答案主动打开、任务页 Generate PDFs、Papers 跳转和可折叠运行详情。PDF 和网页逐页检查长公式、表格、分页和选答说明。两份 PDF 均有效后才显示就绪。

### T4 · 证明通用性与旧流程兼容

**测试**　复用 T1–T3 的测试文件和现有 U4 回归。测试数据放在各测试夹具中。HTTP 形状有变化时更新 `contracts/openapi.yaml` 与 `frontend/src/api/generated.ts`。

- [ ] 用两套课程跑配置到双 PDF。A 用历史参考，四题、两区、全必答；B 无样卷，用三题、不同分值与时长，其中一个区选答。B 至少有一类与 A 不同的现有支持题型。
- [ ] 检查没有跨课程数据读写，且两套课程能从配置到历史分别找回。旧单章和 U4 的已保存配置、任务、PDF 与哈希仍可用。隔离验证通过后开放模拟卷提交能力。
- [ ] 复核现有调用预算与四题实跑的准备条件，确保普通失败、取消和超限均可回收。本轮先沿用现有上限和拆分规则。真实样本若暴露预算不足，先留存调用、阶段耗时及 token，定位后只调整受影响的边界。

## 批次 3 · 真实验收

### T5 · 准备 QM 并完成一份真实模拟卷

**验收记录**　`var/evals/round2/mock-exam/` 下的模板来源、范围、精确预检、调用记录、逐题复核与两个 PDF。实施完成后按项目规则更新 README 与交接。

- [ ] 确认目标期末范围下的 Topic 都有可用知识与依据，并能同版选择。QM 已有 Topic 1/2 可复用。其他 Topic 通过现有流程分析和确认。把历史结构与现行考试信息分别登记；使用 2024/25 模板时保留未校准标识。
- [ ] 用该课程的模板运行真实规划与生成，各自按精确预检取得授权。核对全部印刷小问、评分、学术来源和实质重复。验证两份 PDF、任务恢复与历史找回。
- [ ] 报告实际知识覆盖、耗时、token、修复及跳过项。已有 U4 混合练习和一份通过完整范围验收的真实模拟卷满足第二轮两类输出。若先只用 Topic 1/2，记录为局部范围样本。

## 拟运行检查与 Git 基线

命令从实际仓库根目录执行。此次只修订方案，测试和真实模型均未运行。

~~~powershell
& .\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests/test_exam_template.py backend/tests/test_mock_exam_structure.py backend/tests/test_mock_exam_generation.py backend/tests/test_multi_topic_generation.py -q
& .\.venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run
npm --prefix frontend test -- --run
npm --prefix frontend run build
~~~

正式实施时按 AGENTS.md 核对单写者和 U4 稳定基线。模板与结构一批提交，生成与交付回归一批提交。涉及课程范围和模型的动作按验收单独记录。材料、临时文件和密钥继续本地保存。
