# Course Topics Workspace Implementation Plan

实施更新（2026-11-02）：用户已在主聊天授权按本计划开发。U1–U3 本地能力及 Task 11 核心检查、Task 12.1 工具已实现；真实 R1–R6/E1 和最终质量/性能验收待新的范围授权。详细实测、未执行项见 ../../batch-6-validation.md。下文侧聊时的未授权/拟运行描述保留为历史，不表示本轮已验收。

> **For agentic workers:** 按任务逐项实施与检查，步骤使用 checkbox。遵守主线单写者规则；本侧聊只规划，不调用子代理、不提交代码。writing-plans 的通用执行模板不覆盖本次侧聊边界。

**Goal:** 将固定 Topic 2 的工作区演进为整门课程的 Topic 目录、材料关联、独立审阅及知识选择。
**Architecture:** 复用 Django/React 和现有课程草稿、版本、幂等、任务及 PDF 流程。增加章节归属和版本化配置，旧冻结结果通过只读兼容投影展示；不复制按课程定制的页面。
**Tech Stack:** 当前锁定的 Django/DRF、PostgreSQL、React/TypeScript、TanStack Query、KaTeX、Python Playwright；本计划不安装或更换依赖。
**Spec:** [整课工作区设计](../../course-topics-workspace-design-v0.1.md)、[第六批计划](2026-11-01-batch-6-acceptance.md)、[原首轮计划](2026-10-19-round-1-qm.md)。

日期：2026-11-01。**用户要求更新计划，未授权本侧聊实施以下代码、迁移或真实调用。** 新字段、接口和分期为推荐；路径是拟实施文件，尚未创建。

## Global Constraints

- Course / Topic / Knowledge 身份分开；现有 config.topic_ids 实为 knowledge IDs，旧契约不能原地改义。
- 原文件、现有 CourseVersion、Task、Candidate、Paper/ContentVersion、报告、PDF 及其 hash 不改写。
- UI 使用英语，正文/设计记录中文；课程/主题内容来源于数据，不能新增 QM 专属常量。
- 选 Topic 不自动分析/生成；新预检同时显示所选 Topic、材料页段、共同证据及外发范围。
- Topic 切换与确认互不等同；Course-wide 事实变化明确标记影响范围。
- 先检查当前 Git/用户修改，按项目规则在实施主线同步；本次文档侧聊不 pull/commit/push。
- U1–U3 为第六批新增前置，U4 为第二轮首批。原 R1–R6 不因 UI 扩展而被替代。

## Review Focus

1. 旧配置字段误读或重写旧 hash：U1 的 legacy round-trip 与 U3.3 的 schema 双版本测试。
2. 共用资料/知识多重归属造成重复计数或误扩发送：U1 的去重/页段测试，U3.1 的授权范围测试。
3. 切换 Topic 时编辑、来源参数或确认状态丢失：U2 URL 与 U3.2 保存冲突/迟到响应测试。
4. 无关 Topic 缺口阻塞全课，或共同声明变化未失效：U3.2 scoped confirmation 测试。
5. 前端允许跨 Topic、后端忽略或混用版本：U3.3 能力门槛与 U4 混合覆盖/唯一版本测试。

## U1：Topic 目录、材料归属与旧数据兼容

**阶段**：第六批前置；可先于真实模型独立完成。
**文件**：
- 新增 backend/app/courses/topics.py、topic_api.py；backend/app/materials/topic_assignments.py。
- 修改 backend/app/courses/models.py、schemas.py；backend/app/materials/models.py、schemas.py、api.py；backend/config/urls.py。
- 在对应 migrations/ 新增顺序迁移（编号以开工时仓库为准），不修改已应用迁移。
- 新增 backend/tests/test_topic_catalog.py、test_material_topic_assignments.py、test_topic_legacy.py。
- 修改 contracts/openapi.yaml、frontend/src/api/generated.ts；新增 frontend/src/features/topics/types.ts。

**接口**：
- list_topics(owner, course_id) -> TopicList；create_topic(owner, course_id, data, key) -> Topic。
- update_topic(owner, topic_id, expected_revision, patch) -> Topic。
- set_topic_assignment(owner, material_version_id, expected_revision, assignment) -> Assignment。
- adapt_legacy_course(payload, mapping) / adapt_legacy_config(config, mapping) -> 只读 v2 投影，不保存回旧记录。
- mapping 必须显式记录旧 node IDs 与 Topic 的已核实对应，不能按课程名或文件名硬编码。

**步骤**：
- [x] 写测试：同 owner 同课程 Topic ID 稳定，重名可提示但不靠名称作为身份；另一用户访问 404；过期 revision 409。
- [x] 写测试：同 PDF 关联两个 Topic 仅一份 Blob/解析；筛选返回一行；Course-wide/Unassigned 不变成 Topic；页段边界有效。
- [x] 写测试：旧 config.topic_ids 原样保留，读取投影正确；旧 course/task/paper hash 与 PDF bytes 不变。
- [x] 运行新增测试，确认缺接口时失败；实现最小目录/关联、版本化契约与兼容适配。
- [x] 同一命令复跑，通过后检查生成契约及迁移 dry-run；实施主线提交 feat: add course topic catalogue and versioned material assignments。

**拟命令**：根目录执行 .venv/Scripts/python.exe scripts/test_batch5_backend.py tests/test_topic_catalog.py tests/test_material_topic_assignments.py tests/test_topic_legacy.py -q。
**完成条件**：后台可登记/查询真实归属，原输入字节和旧结果不变。对应 AC-01-03、AC-03-02、AC-06-03、AC-11-02 的首轮相关部分。

## U2：Materials 的 Topic library

**依赖**：U1。
**文件**：
- 修改 frontend/src/features/materials/MaterialsPage.tsx、SourcePanel.tsx、相关材料样式。
- 新增 frontend/src/features/topics/TopicPicker.tsx、TopicNavigation.tsx；features/materials/MaterialTopicEditor.tsx。
- 新增 frontend/src/features/materials/MaterialsPage.test.tsx、frontend/src/features/topics/TopicPicker.test.tsx。
- 新增 scripts/test_topic_materials_view.py（明确 fixture；浏览器证据私有保存）。

**接口**：TopicPicker 接收 topics、value、onChange，不提交分析或配置；MaterialTopicEditor 使用 U1 的 Assignment revision；列表查询 key 包含 course、topic、include_shared 及筛选。
**步骤**：
- [x] 写测试：选 Topic B 不再显示 Topic 2 专属文件；公共文件需明确包含；重复关联不重复计数。
- [x] 写测试：上传在提交前显示归属；重复上传可链接已有文件；无归属留 Unassigned。
- [x] 写测试：source panel 的打开/翻页/关闭保留 Topic/search URL；后退恢复；旧响应不覆盖新筛选。
- [x] 移除写死章节卡片，接入可搜索目录、归属编辑和活动记录折叠；UI 空/错/加载使用真实状态。
- [x] 运行 vitest 定向测试和浏览器脚本，检查 1440/1024/768/320px 与键盘；实施主线提交 feat: browse course materials by topic。

**拟命令**：pnpm --dir frontend test --run src/features/materials/MaterialsPage.test.tsx src/features/topics/TopicPicker.test.tsx。
**完成条件**：同 Course 下可以查看不同 Topic 的 library；不改变源页引用、失败记录和上传成果。对应 AC-02-02/04、AC-03-02 与页面状态要求。

## U3.1：按 Topic 的材料输入与课程分析

**依赖**：U1；页面可用 fixture 独立设计，但真实 E1 必须等待此任务。
**文件**：
- 修改 backend/app/courses/context.py、analysis.py、schemas.py、api.py、clarifications.py。
- 修改 backend/app/ai/prompts/course_analysis.md；审查其中 Topic 2/材料编号/固定知识目标假设。
- 新增 backend/app/courses/topic_context.py；新增 backend/tests/test_topic_analysis.py。
- 原 qm_analysis_manifest.json 仅保留为明确的迁移/验收种子，不作为所有课程默认输入。

**接口**：build_topic_analysis_context(course, target_topic_ids, material_selection, base_revision) -> AnalysisContext；material_selection 由确定的版本和页清单构成。输出包含 target_topic_ids、知识归属、共同/局部声明、受影响问题；沿用既有受限预检、grant 与 task。
**步骤**：
- [x] 写非 Topic 2 fixture：输入不包含 K1–K8 或 Mxx 常量仍可形成合法草稿；不凭文件名或教材序号冒充考试事实。
- [x] 写授权测试：共享文件只发送显式必要页；新增 Topic/页图/历史参照改变 context hash；浏览列表不会调用模型。
- [x] 写合并测试：分析 Topic B 不覆盖 Topic A 的人工编辑；模型意外返回未选 Topic 的修改应拒绝并记录，不自动应用。
- [x] 实现动态材料/页选择与按目标分析结果校验，提示词中课程事实从 input 读取；不新增多学科能力包。
- [x] 运行隔离测试及既有课程分析回归；实施主线提交 feat: scope course analysis to selected topics。

**拟命令**：.venv/Scripts/python.exe scripts/test_batch5_backend.py tests/test_topic_analysis.py tests/test_course_analysis.py tests/test_course_execution.py -q。
**完成条件**：新 Topic 能从自身资料进入分析/澄清，不套用 Topic 2 的知识；真实能力由后续 E1 验证。对应 AC-04-02/03、AC-05-03。

## U3.2：Profile 的 Topic 审阅、保存与确认

**依赖**：U3.1。
**文件**：
- 修改 backend/app/courses/drafts.py、confirmation.py、models.py、schemas.py、api.py；新增确认范围相关迁移。
- 修改 frontend/src/features/profile/ProfilePage.tsx、types.ts、useDraftSave.ts、profile.css。
- 新增 frontend/src/features/profile/TopicOverview.tsx、TopicProfile.test.tsx；新增 backend/tests/test_topic_confirmation.py。
- 继续复用 topics/TopicPicker。

**接口**：confirm_topics(owner, course_id, expected_revision, base_course_version_id, selected_topic_ids, key) -> CourseVersion。
同一 course/draft revision 不同确认子集以 confirmation fingerprint 区分；同请求重放返回同版本。新 CourseVersion 的 topic_manifest 只含实际确认内容及有效保留的旧主题快照。

**步骤**：
- [x] 写测试：Topic B 有阻塞问题时 Topic A 仍可确认；共同声明改变影响 A/B 时各自需明确复核。
- [x] 写测试：确认 A 不夹带 B 未保存/未审阅编辑；旧 Version hash 不变；同 revision 分别确认 A/B 不违反错误的唯一约束。
- [x] 写前端测试：切换前保存成功、保存失败保持草稿、过期响应、刷新和返回；未分析 Topic 不显示 Topic 2 内容。
- [x] 实现 Course overview / Topics 选择器、按 Topic 展示与澄清、范围明确的 Review & confirm；调整服务器确认唯一约束并保留旧记录。
- [x] 运行确认与保存测试，核查反馈写明 Topic 与版本；实施主线提交 feat: review and confirm course topics independently。

**拟命令**：.venv/Scripts/python.exe scripts/test_batch5_backend.py tests/test_topic_confirmation.py tests/test_course_drafts.py -q；pnpm --dir frontend test --run src/features/profile/TopicProfile.test.tsx src/features/profile/useDraftSave.test.ts。
**完成条件**：切章不丢编辑，局部缺口不误阻塞全课，共同规则不漏复核。对应 AC-06-01/03、AC-04-03、AC-11-02。

## U3.3：整课知识树与单 Topic 生成接入

**依赖**：U3.2；第六批完成范围。
**文件**：
- 新增 frontend/src/features/generate/TopicKnowledgeSelector.tsx、TopicKnowledgeSelector.test.tsx。
- 修改 GeneratePage.tsx、types.ts、config-state.ts、StructureSummary.tsx、GenerationLaunch.tsx。
- 修改 backend/app/generation/schemas.py、planning.py、snapshots.py、execution_context.py；新建 config_compat.py。
- 修改 PapersPage.tsx、PaperPage.tsx、TaskPage.tsx、backend/app/papers/reader.py 的冻结 Topic 摘要展示。
- 新增 backend/tests/test_topic_generation_config.py；同步契约。

**接口**：PracticeConfig v2 使用 selected_topic_ids / knowledge_ids；validate_topic_selection(config, course_version, capabilities) -> ValidatedSelection。capabilities 来自后端能力状态，U3.3 mixed_topic_practice 为 false；v1 重试不经新配置改写。
**步骤**：
- [x] 写旧配置兼容测试：相同旧内容不新算 hash；新配置拒绝跨版本或跨课程知识 ID。
- [x] 写知识树测试：搜索/折叠保留选择；全选跳过不可用项并说明原因；共享知识 ID 去重；浏览操作不使确认失效。
- [x] 写配置测试：知识/Topic 改动使蓝图确认失效，改回也不恢复；选择第二个 Topic 时能力未开放则明确不可提交，后端也拒绝。
- [x] 接入任意已支持 Topic 的单章规划与生成；当前题型/检查器不适用时返回能力缺口，不按名称套用 QM 优化题。
- [x] 实现 Task/Paper 的冻结主题标签与筛选、旧配置复用差异；运行相关测试后提交 feat: select practice knowledge from a course topic tree。

**拟命令**：.venv/Scripts/python.exe scripts/test_batch5_backend.py tests/test_topic_generation_config.py tests/test_generation_snapshot.py tests/test_papers.py -q；pnpm --dir frontend test --run src/features/generate/TopicKnowledgeSelector.test.tsx src/features/generate/config-state.test.ts。
**完成条件**：产品能浏览整课目录并从不同 Topic 分别生成单章练习；E1 可走正常 UI；不声称跨 Topic 出卷已完成。

## U4：跨 Topic 混合练习（第二轮首批）

2026-11-09 本地实施状态。已完成配置、覆盖、来源范围、页面和双 PDF 兼容，后端 49 项、前端 37 项及生产构建通过。正常入口的隔离流程验证位于 backend/tests/test_multi_topic_generation.py。当前真实 QM 版本仅有 Topic 2，待第二章确认和两阶段精确授权后执行真实多章节验收。


**依赖**：U1–U3、第一轮第六批记录。不是本次文档任务授权执行的内容。
**文件**：
- 修改 generation/schemas.py、planning.py、execution_context.py 与规划提示词，新增 backend/app/generation/topic_coverage.py。
- 修改 TopicKnowledgeSelector.tsx、StructureSummary.tsx、GenerationLaunch.tsx、PapersPage.tsx、PaperPage.tsx。
- 新增 backend/tests/test_multi_topic_planning.py、test_multi_topic_generation.py；新增 scripts/test_mixed_topic_flow.py。
**接口**：validate_topic_coverage(config, blueprint, course_version) -> CoverageReport；报告区分 printed、attempt、跨 Topic 题的唯一分值，以及 required / optional 覆盖。

**步骤**：
- [ ] 写测试：两个 Topic 的知识可选，同一知识去重；混入其他课程/版本拒绝；小题覆盖必须来自冻结选择。
- [ ] 写覆盖测试：选定知识过多/题量过少有明确冲突；跨 Topic 题不重复计分；所有允许选答路径遵守冻结覆盖规则。
- [ ] 开放 mixed_topic_practice 后端能力并接通前端选择；显示每 Topic 覆盖和结构变化；必要证据有界检索，不发送整库。
- [ ] 测试旧卷与新卷并存、再次生成差异及两个 PDF 的主题摘要；独立真实多章节任务需精确预检授权。
- [ ] 取得至少一份真实多章节练习证据后，记录第二轮对应验收；提交 feat: generate checked mixed-topic practice。

**完成条件**：整课多 Topic 的知识选择真正影响生成与核验。完整模拟卷仍需第二轮后续的全卷模板、题量及选答任务，不能以该任务替代。

## 执行与交付

- 每项的测试命令均为拟运行，尚未执行；首次实施需核对模块实际路径和锁文件。测试使用隔离数据库且阻断真实 API。
- U1–U3 完成后执行第六批 Task 11，再冻结 R1–R6 / E1；U4 不计入第一轮六次成功数。
- 更新 README 的实际能力、OpenAPI、验证证据和主线 handoff；稳定点分步提交，真实材料和 var 不提交。
- 本设计已自审：用户三页要求分别对应 U2/U3.2/U3.3+U4；所有五个 Review Focus 有指定测试。自审不等于运行通过。
