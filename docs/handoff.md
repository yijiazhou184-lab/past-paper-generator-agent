# Codex 与 Claude Code 开发交接

## 接手入口 · 通用完整模拟卷（2026-11-09）

**当前交付**　Course overview 可录入、保存并确认课程级考试模板；Mock exam 使用确认版本里的模板，沿用组卷、核验、历史和双 PDF。普通选答保持卷面分与应答分分开，等分路径由服务端检查。通用出题依据补绑会为遗漏的已确认知识点补入现有教学证据；数学检查的 points 接受受限的有限实常量表达式。旧记录继续按原快照读取。R4 的实质重复问题与 R5 其余能力缺口仍单独跟踪。

**验证**　401 项后端测试、38 项前端测试和生产构建通过。迁移一致性和 OpenAPI 校验通过。交接前定向重跑 33 项通过。三题含选答、四题全必答两套合成课程均输出可读的题卷和评分细则。合成数据保存在隔离测试库及临时 PDF，测试完成后课程记录已清理。当前分支实现完整卷以来没有调用真实模型。

**共享工作区**　本次核对本地网站返回 HTTP 200，任务队列为空，courses 的 0010_exam_template 尚未应用。正式服务仍加载此前版本。QM 主课程版本 3 已确认 Topic 1 和 Topic 2，完整考试范围的其他 Topic 和整卷模板待准备。未重新运行 R4/R5 或生成真实完整模拟卷。

**下一步**

1. 按 AGENTS.md 核对 Git 状态并执行 `git pull --ff-only`。接手部署本机应用时重新确认任务空闲并检查待迁移列表，再运行 `& .\.venv\Scripts\python.exe backend/manage.py migrate`。使用本地启动脚本的 `restart-api` 与 `restart-workers` 载入新代码，核对 Course overview 和 Generate 页面。
2. 在现有 QM 工作区确认完整考试范围内其余 Topic，合并到同一已确认课程版本。录入并确认整卷模板；沿用旧样卷结构时保留未校准标识。
3. 分别冻结并获得规划、题答生成的精确外发授权。运行一份真实完整卷，核对实际覆盖、耗时、token、网页和双 PDF。U4 已完成，记录在本机 var/evals/round2/U4/u4-live-acceptance.md；真实输入、原材料和报告详情留在本地。

[完整模拟卷实施计划](superpowers/plans/2026-11-09-full-mock-exam.md)

## 当前实现 · U4 跨章节混合练习（2026-11-09）

Generate 支持同一确认课程版本的跨 Topic 知识选择。蓝图逐一核对允许的作答路径，展示章节覆盖、共享题和计一次的分值。新预检只取所选知识的冻结依据和每个选中章节最多两条补充比较证据。题卷按任一相关 Topic 可筛选，同一份卷仅存一条，题卷和答案 PDF 都显示冻结章节。

U4 已完成真实验收。QM 主课程版本 3 的 Topic 1/2 同卷生成 2 道大题、7 个小问，42 项必要检查均通过，两个 PDF 已导出。生成及核验耗时 157.42 秒，超过 120 秒目标。本次未触发语义拆分或修复。

U4 的独立审阅覆盖全部 7 个小问，核对了来源、双 PDF、按章节筛选和原有 5 份卷共存。

## 最新真实结果 · R4/R5 发现两类验收缺口（2026-11-08）

R4/R5 真实规划均保存，结构经用户修订确认。R4 应用成功发布，59/59 必要项通过并交付双 PDF，但独立审阅发现优化题与 R6 实质重复。R5 已保存 8 小问题答，独立复算正确，必要核验 55/57。当前契约无法直接表达题目要求的最大定义域、有符号发散极限和参数化分段最优规格。一次修复后仍为 needs_info，无 Paper 或 PDF。两个原始任务均保留。两卷都超过 120 秒，第一轮整体质量验收仍未通过。

[R4/R5 真实验收报告](round-1-live-r4-r5-2026-11-08.md)

以下为此前阶段的记录。

## 最新真实结果 · R6 人工确认结构后生成与交付通过（2026-11-08）

R6 在 18666f2 重启后的环境执行，PDF 渲染补测 2 项通过。原规划因优化题漏绑 K2 教学依据失败。基于保存输出修订后经用户确认，4 大题、10 小问、40 分、55 分钟、K2–K8。真实题答 72/72 必要项及 10/10 独立逐题审阅通过，未拆分、未修复，交付同版双 PDF。生成与导出合计 277.306 秒，未达两分钟。R2 仍跳过，R4/R5 待做。

[R6 真实验收报告](round-1-live-r6-2026-11-08.md)

以下为此前阶段的记录。

## 交给 Codex：重启服务并执行 R6（2026-11-08，Claude Code → Codex）

用户选择由 Codex 重启服务并执行 R6。本次 Claude Code 的两项改动（下两节）已提交并推送；接手按 AGENTS.md 第 6 节先 `git pull --ff-only`。

**目标**：在新代码上完成 R6 真实验收（manifest：exam_standard、4 大题、小问 3/2/3/2、每题 10 分、55 分钟、K2–K8、blueprint_group standard-4），按既有口径记录。

**接手时的状态（Claude Code 只读核对）**
- web/api/worker/dispatcher 均在运行，0 活动任务，调用记录 255；但运行的是**改动前的旧代码**，需在无活动任务时 `scripts/local.py restart-api` 和 `restart-workers` 加载。
- **PDF 导出依赖 Playwright Chromium**（`papers/render.py`）。Claude Code 环境中找不到 `ms-playwright`，全库测试 `test_paper_render.py` 两项因此失败；现有服务由 Codex 环境启动，R3 PDF 在该环境导出。因此重启须在 Codex 环境执行，重启后先确认能找到 Chromium，并在 Codex 环境补跑 `test_paper_render.py`。
- 课程版本 2 中 K2–K8 均 supported，相关依据页均已转写或不需要转写；R6 不需要新页图。10-25 至 10-31 的 7 份真实候选已含 K6–K8 与 `lhopital` 规格，d5a7434f（4 大题）必要项全部通过。
- 本次改动改变了语义核验 prompt/schema/策略，按 manifest `baseline_policy` 属新基线；R6 记录需注明，不与 R1/R3 做单因素比较。

**下一步**
1. pull、在 Codex 环境重启 API/worker、确认 Chromium 与 `test_paper_render.py`。
2. 为 R6 生成**新的规划预检**（不沿用 R1 蓝图），经用户对精确输入授权后规划一次；用户审阅、编辑并确认符合矩阵的结构。
3. 生成新的精确生成预检并取得授权后运行；独立逐小问审阅、双 PDF 导出与全页目视检查，记录 token、耗时、调用数及是否触发拆分。
4. 记录写入新的 round-1 R6 报告、README 与本文件；R2 仍 skipped、R4/R5 未执行。

**风险**：4 题卷的必要语义输入此前为 57k–60k（旧投影）；现投影下 3 题为 39k，R6 可能首次真实触发拆分，调用上限 16 次可能吃紧。两分钟目标预计仍不达标。

**未验证**：两项改动未经真实模型运行；前端未改未测；`test_paper_render.py` 需在有 Chromium 的环境复核。未跟踪的 `docs/multi-course-compatibility-design-v0.1.md`（待用户确认的方案）和 `小学语文课件/` 是用户文件，未提交、勿处理。

## Claude Code：可选核验去掉背景引用一项（2026-11-08）

- 用户决定：可选建议核验去掉 `background_references` 一项（此前 R3 中该项因可选输入不含教材摘录而 2 项无法判断）。只做这一项，其他未动。
- 改动：`review_policy.py`（三项可选类别，`review-policy-v4`）、`content_schemas.py`（`ReviewCheck.category` 去掉该值）、`semantic_review.md`（可选类别说明）、`check_progress.py`（未完成报告的可选占位读取任务冻结策略）；新增两项回归在 `test_generation_check_progress.py`。
- 不变：题答 `background_references` 字段及其展示、必要核验、来源规则、`PIPELINE_VERSION`；`generation_basis` 不含核验策略，已验证大题仍可跨任务复用。
- 验证：全部 `test_generation*.py` 加 `test_source_originality.py`、`test_intra_paper_rule.py` 共 **118 passed / 144.81 秒**，Django check 0 issues，`git diff --check` 通过。未跑全库和前端测试（前端未改），未调用真实模型，未重启服务；已随交接提交。
- 下一步：运行中的 API/worker 仍是旧代码，下一次真实生成前用 `scripts/local.py restart-api` 和 `restart-workers`（无活动任务时）加载，再取新预检；旧预检和授权不能沿用。R4–R6 状态与上一节相同。

### 页图转写来源由服务器绑定（2026-11-08，同一会话，用户要求实施）

- 依据：[A+B 实测](batch-6-live-start-2026-11-02.md)第 63 行的建议（E1 p44 因模型回抄 hash 出错而 `MODEL_SOURCE_MISMATCH`）。
- 改动：`ai/visual.py` 拆分出模型输出类型 `VisualTranscriptionModelOutput`（无 `source`），`check_transcription` 改为附上服务器来源后校验；`visual_transcription.md` 改为“不要返回来源”；`materials/transcription.py` 用新输出类型调用，抽出 `verify_page` 在发送前和返回后各核对一次，`cached` / `page_states` 接受 `CACHE_COMPATIBLE_VERSIONS` 中的旧版本结果，旧契约排队的页报 `TRANSCRIPTION_CONTRACT_CHANGED` 不发送。版本 `r1-visual-transcription-2-server-source`。输入仍带完整 source，调用记录 metadata 保留来源 hash。
- 兼容决定（本会话实施时确定，需用户知悉）：旧版本 39 条转写继续当作有效缓存；旧授权不延用到新版本请求。本机只读核对：QM done 27、E1 done 11 / failed 1（p44），调用记录不变。
- 未改：批次一 `ai/validation.py` 页面核对的来源比对、课程分析与生成流程、前端。
- 验证：`test_visual_contract.py`、`test_visual_transcription.py`、`test_visual_analysis.py` **51 passed**（新增 6 项：模型 schema 不含 source、服务器来源写入结果与调用记录、模型返回 source 被拒、调用期间页面变化不缓存、旧版本转写仍命中缓存、旧契约排队页不发送）。后端全库（含上方可选核验改动）**376 passed、2 failed / 312.08 秒**：2 项为 `test_paper_render.py` 在本机缺少 Playwright Chromium（`chrome-headless-shell.exe` 不存在）而失败，未安装浏览器，需在有 Chromium 的环境复核。Django check 0 issues，`makemigrations --check` 无变化。前端未改未测。未调用真实模型，未重启服务；已随交接提交。
- 下一步：E1 p44 或其他未转写页需按新版本取得逐页授权后再发送；API/worker 重启后才加载新代码。

## 最新真实结果 · R3 两份历史卷去重通过（2026-11-07）

R3 沿用 R1 蓝图并冻结 H0 与 R1-retest-02，3 道全新大题、8 小问，未发现实质重复。56/56 必要项与 8/8 独立逐题审阅通过，完成同版双 PDF。8 次模型和 8 次计数共 147,436 模型 tokens，生成和导出 250.056 秒，未达两分钟目标。R2 仍跳过，三份历史卷场景未覆盖，R4–R6 待执行。验收数据及 PDF 留在本机，服务继续运行。

[R3 真实核验报告](round-1-live-r3-2026-11-07.md)

## 最新真实结果：新版 R1/E1 均已完成题答与双 PDF（2026-11-06）

用户要求用新版本重新运行真实 R1/E1。本次 R1-retest-02 与 E1-retest-02 均 completed、独立八小问审阅 passed：R1 58/58 必要项通过、一轮 Q2 修复、题卷 4 页/答案 10 页；E1 新确认课程 version 1，六目标、两题八问，34/34 必要项通过且无修复、题卷 3 页/答案 7 页。原失败与 R2 skipped 保留，R3–R6 未执行，不能宣布第一轮全部验收完成。

R1 相同输入的三道旧初稿按哈希复用，执行新版真实核验和修复；不是三题重新生成。新版字段诊断引导 Q2 使用受支持的等价因式分解，精确答案保持，根式点字符串本身仍未扩展支持。E1 从新课程理解、正常目标确认到新规划/题答/PDF，未复用 Topic 2 理解或题答。个别源页疑点和既有用户偏好属性均保留。

本次共 15 模型+15 计数请求（含一次已知 400），277,407 tokens，记录 209→239，全部有终态，无未知或自动重放。R1 生成+导出 232.122 秒，E1 171.838 秒，均未达两分钟；E1 分析 85.645 秒、规划 35.053 秒另列。费用 unknown，R1 复用样本不充当全新出题性能基准。

E1 初次官方计数拒绝新输出 schema，未执行分析模型；本地修正 AnalysisOutput 的 strict required/default，保持旧草稿读取兼容，新 schema r1-course-draft-2-strict-decisions。48 项相关离线回归通过。收集器补齐实际课程确认解决 analysis needs_info 的精确版本关联，13 项回归通过，原 Task 不改状态。真实浏览器 9 组/0 JS 与 KaTeX 错误/0 业务写入，四 PDF 下载 hash 一致；24 页已渲染查看。R1 答案近空白页/孤表头、单数 1 marks 文案作为非阻塞排版项保留。完整记录见 [本次真实结果](round-1-live-r1-e1-2026-11-06.md)。

可操作：[R1 题答与两 PDF](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/papers/56e659eb-596d-4573-99ab-193e92075866)；[E1 题答与两 PDF](http://127.0.0.1:5173/courses/1aeae0e0-c154-4dae-b3e6-fa9b214840d7/papers/0bc9dff2-cceb-4c6a-a5f0-c684cedbb4fc)。本次有限调用结束，不自动再发任务；服务保留运行。

下一步：R3–R6 尚未执行；若继续历史增长验收，需明确 R2 skipped 后的关联方式，不能覆盖原 R1 绑定；完善分页和性能。旧 E1 needs_info 与计数失败记录保留，但已通过正常 CourseVersion 确认的那次分析不再误判成功 Paper 的整条闭环失败。用户其他文档和课件不处理。

以下均为此前阶段的历史记录，以本节为最新状态。


## 当前实现：R1 明确修复原因与通用课程确认（2026-11-06）

已完成本侧聊批准的两组本地改造。R1 修复请求由程序附带必要失败的题/小问/字段/实际值/错误代码/允许格式；缺少明确动作不盲目修复，保留一次修复及必要 gate。课程问题使用类型化操作，选择保存与应用分开；有效声明排除被取代项；确认按所选目标及必要前置，目录汇总和局部材料缺口分别处理。相关决定或确认范围变化会使旧确认不能用于新生成。

新版本 generation-v7-repair-diagnostics / r1-course-analysis-5-decisions；已备份并应用 courses.0009_user_decision_metadata，OpenAPI/前端类型已同步，无新增依赖。服务从 dev 仓库复用及重载。实际验证：后端全量 365 passed，最后课程输入补充后定向 38 passed；前端 36 passed、生产构建通过，Django/迁移/契约检查通过。本机证据和兼容边界见 [验证记录](repair-and-course-confirmation-validation-2026-11-06.md)。

真实调用新增 0，模型记录仍 209；旧 3,228 条业务记录和 46 个文件未改。两门合成课程通过浏览器流程；真实 E1 只读保持 revision 4、无确认版本、旧回答已保存但仍待解释，历史根节点未自动重分类。原 R1 仍失败，尚未证明新修复提示能通过真实验收。继续真实 R1/E1 前必须审阅并授权新输入，旧预检不可复用。

下一步属于主线程真实验收，不由本次侧聊自动执行：处理/审阅 E1 旧草稿与必要材料缺口，确定真实所选目标；使用新预检运行获准 R1/E1，再核查题答、必要检查、token/耗时及 PDF。R2 skipped、R3–R6 未执行的状态保留。下方为历史记录，旧“待实施/当前”说法以本节为准。


## 当前验收：E1 获准分析已完成，仍需课程草稿处理（2026-11-03）

用户已明确确认“使用标准数学定义，并注明资料差异”，并允许按 6dc34c33… 精确快照运行一次 E1 后续分析。该次调用已执行：task fd64ee51-0e51-44ce-9ff8-0f1ae39d9c31 返回 needs_info；API/解析正常，4 个知识节点为部分支持，没有 token 超限。官方计数 10,771；实际输入/输出 10,771 / 6,906，合计 17,677 tokens；模型 78.750 秒，系统墙钟 84.611 秒。新增 1 模型+1 计数，调用记录 207→209；没有自动重试。

获准输入仍包含旧的“Codex 临时、用户尚未确认”说明，模型据此重复提出惯例选择。这是确认信息与冻结输入未同步的问题，不应再次要求用户选择。未改写获准快照或历史响应；已通过正常澄清回答保存实际人类确认，明确取代临时说明，当前草稿 revision 4。该确认是练习偏好，不是官方事实。新精确预检 826fce3f… 仅本地准备、execution_authorized=false，未再次外发；本次一次分析的授权已使用。

E1 暂无 CourseVersion、规划、题答或 PDF。章节总节点、连续性、最值存在性、介值/不动点四项仍 partial；当前整章确认会阻塞全部 partial 节点，新澄清也触发重新分析。下一步应先处理确认信息同步，以及“章节总节点/个别不可读例题”与实际练习所需知识的区别，保留真实缺口，避免盲目重复付费调用；未实施范围放宽或绕过 gate。Lecture 1 物理 p38（印刷 39）已做本地页图核对，明确写在定义域上连续；未创建正式视觉转写记录、未发新页图。

R1 一次补测仍 failed（必要数学检查不支持根式点字符串）；R2 保持用户指定 skipped；R3–R6 未执行。本次仅运行真实分析及本地核对，没有新增产品代码/依赖/迁移，也未重跑全库或浏览器端到端。Django check 0 issues；web 和实际 API /api/v1/session 均 HTTP 200，0 活动任务。完整记录及前次代码测试见 [R1/E1 实测记录](batch-6-r1-retest-e1-2026-11-03.md)。原材料、原结果和用户未跟踪文件保持。

## 当前局部更新：按小问汇总知识覆盖（2026-11-03）

本侧聊用户明确要求：模型设计每个小问的考核知识，程序汇总大题/整卷；不再分析主考/辅助，也不按旧矩阵固定 Q2=K5 等逐题分配。仅此局部实现，未继续父线程真实任务。

- schemas.py 新增 PlanningQuestion / PlanningBlueprintPayload，模型 schema 不含 question.knowledge_ids 或 coverage；materialize_planning_blueprint 从 parts 稳定去重派生两项，再按旧 blueprint-v2 存储。旧 blueprint-v1/v2 冻结读取验证不自动纠正；编辑保存 recalculate=True 重算汇总。
- planning.py 冻结 planning-v3-part-coverage / r1-planning-3-part-coverage / part-knowledge-union-v1，并另存 blueprint_schema_version=blueprint-v2。新输出经派生后进入原发布/唯一保存/版本绑定；schema/prompt/hash 已变化，旧预检不能用于新调用。
- evals/round1 当前 manifest 删除 question_knowledge 固定分配，保留整卷 knowledge 与题数/小问数/分值/时间等原矩阵；check_matrix 只验证整卷知识集合，不规定各大题分配。旧运行快照、授权文件、失败记录不改；这是用户新决定造成的新 manifest 基线，不适用于重写旧成绩。
- 61 项定向回归通过 / 20.87 秒（planning_coverage、planning_execution、blueprint_rules、generation_snapshot、eval_accounting）。测试使用独立随机库、真实密钥移除和传输阻断。两条已有 accounting 测试的 finished_at 在 create 前生成会偶发早于 created_at，现仅修正测试夹具为确定性时间，不放宽真实时间检查。
- 原 R1 响应离线回放：旧规则仍复现 QUESTION_COVERAGE_MISMATCH；去掉旧模型汇总字段后按新契约派生，通过正常覆盖/来源校验，原文件哈希不变、原 Task 仍 failed。原提案仍是 11 小问/48 分/80 分钟，未保存/确认，也未符合数值验收矩阵。
- 调用记录前后均 188；无真实模型调用、业务任务/版本写入、服务重启、新依赖或迁移。工作区其他用户文档及课件未动。

下一步仅供主线程接手：在安全的正常部署/重载节点加载代码并生成新规划预检；原失败不自动恢复。A+B 真实状态和 E1 尚待处理事项见下节。来源哈希回抄问题仍未实施，不与本次知识汇总混为已解决。完整计划/检查见 [本次局部记录](superpowers/plans/2026-11-03-planning-part-coverage.md)。

## 当前交接：A+B 已执行，R1 规划失败、E1 新草稿已保存（2026-11-02）

用户已回复“允许 A+B，并确认验收口径”，此前“等授权”状态已失效。工作目录仍为 C:/Users/Yijia/dev/past_paper_generator，单写者；没有第二轮开发。

- R1 task d08de7d8-643d-4d07-9319-862ccb7314ce：实际一次模型调用返回 parsed，但 Q2 大题目标只有 K5、小问含 K2/K5，QUESTION_COVERAGE_MISMATCH；原失败保留。模型原提案 11 小问/48 分/80 分钟。本地依矩阵整理的 8 小问/30 分/40 分钟提案通过 validate_blueprint/check_matrix，位于 var/evals/round1/R1/reviewed-matrix-proposal.{json,md}，未发布/未确认，不冒充模型成功。
- E1 转写 task 84b790d4-05d7-45aa-b2ee-cab7af8b1884：精确 12 页、并发 2，11 有效，Lecture 1 物理 p44 的 parse_content_hash 回抄重复导致 MODEL_SOURCE_MISMATCH；任务 succeeded 不代表所有页成功，没有重发。
- 同 22 页+11 有效转写+原用户声明派生分析 hash be89bce08f32129f049c1987d78b1f51d63f7f59d265d3c947ba09ca25586e69，在 A+B 父范围内重新核对并授权；task 1affd130-d954-4f58-92f8-3f4557b2d940 succeeded。新草稿 fd02fd70-69b9-45b3-bdf1-bcfec7589e08 / revision 1，6 子知识组、9 方法、8 issues、1 needs_confirmation。没有复用 Topic 2 理解/知识 ID，没有自动确认版本。
- 实际 14 模型+1 计数，输入 65,512、输出 30,077，共 95,589 tokens；记录总数 173→188。全部有终态，无未知/截断/超时、无自动重试，费用 unknown。规划/转写/分析系统墙钟 44.373/116.837/93.950 秒；没有本批 generation+export 性能结论。
- evals/round1/collect.py 补齐阶段 state/result/error/checkpoint 和内部逐页失败 notes；9 项隔离回归通过（20.67 秒）。真实页面 6 组只读检查通过，0 JS 错误/0 业务写/0 新调用。全库回归未重跑。
- 原 25 材料/PDF 文件哈希不变；旧 2,438 行中 2,437 原字段保持，唯一变化是获准 R1 save_config 更新的可变 GenerationDraft，不是旧冻结内容损坏。用户已有 docs/multi-course-compatibility-design-v0.1.md、 小学语文课件/ 保留，未处理或提交。

下一步：
1. 先处理 R1 冗余目标元数据的规划稳健性，再经正常保存/审阅路径采用矩阵；原任务保持 failed，补测独立编号。不得修改旧 Task 为成功。
2. E1 在产品 Course profile 处理现有惯例选择，建议标准定义并注明差异；不能代用户认证原材料。p44 缺口及 p40 revenue 版式疑点可不选用，不把整章补齐作为统一门槛。p40 页图不在 A+B 12 页图范围内，不可顺手发给 API。
3. 本次规划/转写/分析授权已用；没有题答生成授权。R1–R6/E1 均无本批真实题答或新 PDF，后续各自确认蓝图和新精确生成范围后执行，逐题审阅和全部页图检查后才能判定通过。
4. 工程建议（未实施）：planning 摘要目标/coverage 由 parts 确定性派生；转写来源 hash 由服务器绑定，模型只返回页面内容。仍要校验选中范围、实际证据和页版本，不能直接放宽现有来源不匹配检查。改契约须新预检。
5. rubric/Codex 独立逐作答单元审阅已确认，原 manifest/rubric 哈希保持，人工确认单独保存在 var/evals/round1/approval-2026-11-02-A-B.json。

可操作：[E1 新草稿](http://127.0.0.1:5173/courses/1aeae0e0-c154-4dae-b3e6-fa9b214840d7/profile?topic=2948d0da-c723-4cea-bb6b-386d0be37caa)；[R1 失败任务](http://127.0.0.1:5173/tasks/d08de7d8-643d-4d07-9319-862ccb7314ce)。scripts/local.py start 已复用服务，API/web/worker/dispatcher/本地 PostgreSQL 保留运行，0 活动业务任务。详细证据和复现入口见 [A+B 实测](batch-6-live-start-2026-11-02.md)。

以下保留此前交接状态作为历史，以本节为准。

## 历史交接：第六批本地实现提交后的待授权状态（2026-11-02）

用户已授权依据最新第六批计划开发，常规实施不需逐批确认。工作目录 C:/Users/Yijia/dev/past_paper_generator；主分支单写者。U1–U3 与 Task 11/12 工具已落地，详见 docs/batch-6-validation.md。U4 跨 Topic 混合生成仍留第二轮。

已完成：目录/材料归属、动态页段分析、Topic 隔离的审阅和确认、配置 v2/知识树、冻结章节摘要/Papers 筛选；原 v1 配置和冻结结果保持不变。额外修复 Windows 数学子进程退出竞争及数据库临时故障的可重试脱敏反馈。

验证：完整隔离后端 318 passed / 454.37 秒；随后诊断/章节接口/验收工具 11 passed / 22.41 秒；前端 31 passed 和生产构建。收尾对人工声明冻结/缺失证据拒绝补充了 13 项定向回归，已通过；旧来源 Back/Forward 和迟到响应隔离也已实际验证。合成浏览器流程至题答与双 PDF 成功；五页四屏宽、错误/超时、主动答案、重复追加链接和版本冲突恢复通过。真实 R1–R6/E1 没有执行；不要把 fixture-browser-flow 的 PDF 或旧第五批样本填入名额。

本地 E1：course 1aeae0e0-c154-4dae-b3e6-fa9b214840d7，topic 2948d0da-c723-4cea-bb6b-386d0be37caa，Topic 1 Limits and continuity。三份 PDF 已正常导入并解析，22 页选定，12 页需要转写。仅复用 Lecture 1 同哈希解析，没有复用 Topic 2 理解。精确页段见 evals/round1/e1-materials.json、var/evals/round1/E1/selection.json。

下一步：
1. 等待用户答复本聊天的范围确认；其可审阅文件 var/batch6-real-preflight.md。申请 A=R1 一次规划，B=E1 12 页转写及同 22 页/转写结果的一次课程分析，同时确认 rubric/审阅者。没有答复就不要真实调用。
2. A 的 planning context hash 为 e11eec77fdef8a8a5f25c99f09b1fc8634b64c579240c828fcfb3d8cdb22e15d；文件 var/evals/round1/R1/ff9f58ac-969e-42b4-bc84-eff68395ce55/preflight.json。如输入/prompt 变化，重建并比较，不套旧授权。
3. B 的转写 scope_hash 为 132187abfb75df81d1deb1ffe0a37e180ed67be5ef7542f4d88cc0606c63d5e1；精确 entries 在 var/evals/round1/E1/transcription-preflight.json。必须仅发送所列 12 页，不能 schedule 整章所有待转写页。转写后重新冻结同 22 页派生分析，并记录授权来源/父预检。
4. 运行 evals/round1/run.py 默认只做预检；真实 --execute 需要当前 AnalysisGrant/PlanningGrant/GenerationGrant ID。R1 规划后经正常产品编辑/确认匹配矩阵的蓝图；R2/R3 必须复用 R1 同蓝图并冻结实际历史。
5. 七次题答生成仍各自需要已确认结构与相应精确生成授权。记录全部失败/补测/可选未查/实际用量和时间；逐题审阅并全页查看新 PDF 后再写 12.4 退出结论。

重要事实：私有基线 var/batch6/before-u1.dump、before-u1.json；旧 2,438 行原字段与原 25 文件哈希保持。新增元数据列不作为旧内容字段比较。ModelInvocation 仍 173，本批新增真实调用 0。测试 fixture 与 evals 原始证据、材料/.env 都不提交。

服务：API 8000、web 5173、worker/dispatcher 和本地 PostgreSQL 由 scripts/local.py 维护；当前均运行。无活动业务任务时再 restart-workers。start 会复用进程，不另起重复服务。主课程和第五批真实 Paper/PDF 可继续浏览。

保留未纳入本轮的用户文件 docs/multi-course-compatibility-design-v0.1.md。下方为历史交接，状态以本节和第六批验证记录为准。


## 当前实现：第五批已完成（2026-11-01）

第一轮 Task 1–10 已实现。成功任务保持题目阅读和主动开答案，答案区下方的 **Generate PDFs** 启动独立导出并跳转 Papers detail；**Run details** 默认折叠。题答成功即冻结保存，PDF 失败不撤销题答；重试使用同内容且不调用模型。Papers 可找回固定版本和两个文件；Generate another practice 先复核当前课程版本与配置，仍需保存、规划和确认。

实测：后端全库 **287 passed / 246.54 秒**，最终渲染/分页/并发补充 **17 passed / 45.73 秒**；前端 **23 passed**，类型、构建、Django 与迁移一致性检查通过。重启后浏览器 8 组检查通过、0 JS 错误；实际题卷 **5 页**、答案 **16 页**，最终导出 **9.831 秒**，全部 21 页转图核对。本批模型调用记录前后均 **173**，新增 **0**。

[直接打开真实题卷及两个 PDF](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/papers/45f3f96e-3478-475c-b839-d85ca7e1c2dd)。原真实生成约 **5m37s**，两分钟目标仍未达标；**第六批六次真实验收尚未执行**。新增历史输入的真实 token 和多样性尚未检验。完整检查、失败修正、文件和边界见 [第五批记录](batch-5-validation.md)。

API、worker/dispatcher 已重启加载本批代码，web/数据库运行；使用 scripts/local.py start 复用服务。本机两份 papers 迁移已应用，backfill_papers 已保存 10 个旧成功任务（含明确标记的 fixture，不代表 10 次真实验收）。其他既有数据库迁移后可运行 backend/manage.py backfill_papers；该命令可重复执行，零模型调用、不自动导出。PDF 保存在被忽略的 var/data/papers/，与数据库共同保留。缺失文件可同内容重导出。

下一步是第一轮第六批，需按新预检确认真实调用；本批没有进入第二轮。独立已有未跟踪文档 docs/multi-course-compatibility-design-v0.1.md 保留原位，未纳入本次修改/提交。接手基线 18a18ab，已知 generation-v6 侧聊成果先保存为 71ae8de，pull --ff-only 已是最新；第五批提交以 git log 为准。

下文保留历史记录，当前状态以上述本节为准。

## 当前实现：来源判重前四项已完成（2026-11-01）

用户要求实现方案前四项，并由用户自行从网站发起真实运行。本次没有代用户运行模型。

- **规则与契约**：`generation-v6` / `review-policy-v3` / `originality-policy-v2`。精简 `source_overlaps` 每条为 `subpart_id`、`source_id`、可空的 `same_stimulus` / `same_conclusion`、可空短 `note`（最多 300 字符）。没有 `same_reasoning` 或模型判重字段；课程来源与卷内比较均按同题且同结论判重复，标准方法可复用。
- **实现入口**：新增 `generation/source_originality.py`，复用既有每大题最多 6 段的检索结果，为每小问选至多 2 个不同来源页；`review_input.py` 传入目标，`semantic_review.py` 保存事实并由代码生成 `semantic:qN:originality`。缺项、冲突、未知 ID 或没有可用比较目标不会自动通过。`check_progress.py` 汇总分组成果并进入报告 hash，`repair.py` 将确定重复纳入已有一次定向修复；无需新增阶段或页面。
- **版本绑定**：schema、提示词、策略及版本进入当前预检 context hash，runtime 校验冻结策略。旧失败任务保持原记录；不要求重规划现有已确认结构，用户在 Generate 点击 Generate practice 获取新预检后自行运行。
- **实际检查**：所有 `backend/tests/test_generation*.py` 加 `test_source_originality.py`、`test_intra_paper_rule.py`，**116 passed / 168.61 秒**；随机独立测试数据库，阻断真实 OpenAI 请求。Django check **0 issues**；git diff --check 通过。此前 67 项是撤回专门约束的独立记录，不当作全库覆盖。
- **工作台**：[QM Generate](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/generate)。API 和 worker/dispatcher 已用既有脚本重启加载代码，前端继续运行；只读浏览器核对已确认四大题、生成按钮可用、旧候选四大题可读、答案默认关闭；0 JS 错误，登录后 0 写请求。没有点击真实生成或提交预检。
- **本地证据**：`var/source-overlap-v6-local-check-2026-11-01.json`、`var/screenshots/source-overlap-v6-generate.png`（均 Git 忽略）。纯本地构造当前上下文得到 33 个冻结来源页；调用记录前后均 **153**，活动业务任务 **0**。真实 token、拆分耗时、质量及端到端是否通过尚未测量。
- **交接边界**：本次侧聊代码与文档修改留在工作区，未 pull/commit/push；保留已有修改及独立的 `docs/multi-course-compatibility-design-v0.1.md`，未进入批次 5/6。下一步由用户在网页运行，再依据新任务的实际报告评估。下文为历史记录，待实施/服务状态以本节为准。

## 历史侧聊决定：撤回专门分类和约束（2026-10-31）

- 用户撤销此前关于故意错误示例的专门处理要求。生成内容统一走普通正确性核验，实际错误由现有修复阶段处理；不按来源的意图、标签或相关题型额外禁止。
- 已删除上一轮新增的清单函数及专用测试，撤回四阶段输入字段和五份提示词的专门约束；新页图/页面核对 schema 仅保留通用 finding 类别。历史标签只读保留，不改来源、确认版本或任务记录。
- 新增两项转写契约回归：新请求不要求意图分类，旧标签及原文仍保持不变。2026-11-01 完成定向回归：visual_contract、visual_transcription、generation_sources、generation_review_budget、generation_execution 共 **67 passed，93.05 秒**。独立随机命名临时测试库在结束后删除，测试阻断真实 API；此前 45 passed 属于已撤回版本。
- 来源比较方案已去掉特殊判重例外及 same_reasoning 必需输出；`source_overlaps` schema 和普通来源的代码判重仍待实施，旧任务原创性失败尚不能宣称解决。
- 未调用真实模型、未新建真实生成任务、未修改网站流程或重启服务。当前为主聊天可接续的本地文件修改，未 pull/commit/push。

## 接手核查（2026-10-31，Codex）

本次仅交接、定向验证和恢复既有服务。接手基线ae894d6；git status干净，git pull --ff-only已是最新，HEAD与origin/main一致。未实施待确认的原创性方案，未发起规划、生成或其他真实模型调用。

### 代码、任务与决定状态

- 已核对主要实现提交：e8632c0（generation-v5的卷内规则、数学能力及core/auxiliary）、5fbb3b2（前端数学角色、离线评测/回放）、27a8d5a（生成专用限额、跨任务复用）。之后是运行记录与待确认方案的文档提交。
- 以数据库实际记录确认最新真实任务仍为b02101f9-4b54-4571-8df3-da3c75f10d56；候选/报告hash有效，最终75必要项74pass、1fail，唯一阻塞semantic:q3:originality。11模型+11计数均有终态，287,060 tokens，494.485秒，语义输入57,027/58,054，没有拆分。
- 冻结蓝图68a09ab1的q3d实际内容已核对并保留。此前基于来源类型认定该小问被禁止的要求已被用户撤销，不再据此强制重规划。
- [2026-10-30方案](superpowers/plans/2026-10-30-source-originality-rule.md)仍待用户确认。其记录的两项用户决定与实施方案的确认状态分开保留；本次交接不代替方案批准。
- 后续来源判重改动以最新方案为准，沿用现有页面及输入绑定机制；是否复用由实际快照、提示词和输入一致性决定。批次5/6仍未进入。

### 本次实际验证

- 定向回归：test_intra_paper_rule.py、test_math_capability.py、test_generation_output_and_reuse.py，**27 passed，34.21秒**，隔离测试数据库且阻断真实API传输。
- Django check：0 issues；makemigrations --check --dry-run：No changes detected。
- Playwright只读页面5组通过：最新真实任务/4题15问、唯一阻塞、主动打开15份答案、双版本和刷新、Generate页入口；0 JS/KaTeX错误，登录后0写请求。截图已查看。
- 当前Codex环境已有Chromium可执行文件，直接使用成功；没有安装依赖。下文“本机无Chromium”是Claude当时环境记录，不适用于本次检查。
- Claude此前252项后端、19项前端及构建结果作为既有记录保留，本次未重跑全量，不能将其写成本次实测。

### 服务恢复与发现

- 接手时web/dispatcher运行，API/worker停止，API及代理请求失败；业务数据库可连接，没有queued/processing任务。
- 使用现有scripts/local.py start复用并补起。2026-10-31 23:24:15（Asia/Shanghai）核对：web/api/worker/dispatcher均为本项目活动进程；5173前端、8000 session和5173代理session均HTTP200；0活动任务。
- 模型调用记录总数前后均153，新增0。没有重跑旧任务；原材料、课程确认、候选和报告均未改。
- worker旧日志包含数据库连接超时，API旧日志没有直接异常。现有证据不能确定两进程停止的共同根因；恢复后的检查正常。
- 运行地址：http://127.0.0.1:5173 。最新任务：http://127.0.0.1:5173/tasks/b02101f9-4b54-4571-8df3-da3c75f10d56 。内置浏览器打开请求返回queued，页面可用性由Playwright验证。

### 交接时发现的说明差异

1. README操作说明仍残留600秒/12k统一上限，已在本次文档更新中纠正为实际900秒及分阶段上限。
2. **待修的产品文案**：GenerationLaunch.tsx:40的预检摘要仍用scope.call_seconds显示所有调用“each up to 240 seconds”，实际question_pairs/repair使用generation_call_seconds=300。完整展开scope包含实际字段，但主摘要不准确。此次未改代码，应在下一次真实运行前同步该摘要并验证。
3. 旧交接及待确认方案提到Prepare generation，但当前网页实际入口为Generate practice，点击后打开精确预检；不要按不存在的按钮编写操作步骤。

本机证据（Git忽略）：var/handoff-check-2026-10-31.json、handoff-after-2026-10-31.json、handoff-browser-2026-10-31.json、screenshots/handoff-2026-10-31-latest.png。以下内容保留为历史交接记录；服务和环境当前状态以上述核查为准。

---


## 最新交接（2026-10-30，Claude Code → Codex）

- **代码状态**：最新实现为 generation-v5 加上生成专用上限和跨任务复用（`27a8d5a`）。之后只有文档提交，没有未提交改动。验证：后端 252 passed（220.7 秒）、前端 19 passed、生产构建通过。
- **最近一次真实运行**：`b02101f9-4b54-4571-8df3-da3c75f10d56`，failed / REQUIRED_CHECKS_BLOCKED，只剩 `semantic:q3:originality`（q3c 与课程例子解题路径相同）。候选 `b7abb94e`（v1）、`0afc9ea9`（v2），未发布。拆分未触发。详见[第四批记录](batch-4-validation.md)末节。
- 当时提出的来源分类和禁用方案已被用户撤销；有效的来源比较要求及实施状态见[当前方案](superpowers/plans/2026-10-30-source-originality-rule.md)，不按本历史段落恢复已删除的约束。
- **历史下一步安排已作废**：后续工作以最新用户决定及当前方案为准，不由本记录触发新的规划或生成调用。
- **未验证事项**：拆分在真实运行中从未触发；新方案的任何部分都未实现、未测试。
- **服务状态**（交接时检查）：PostgreSQL（54330）、web（5173）、dispatcher 在运行；**API（8000）和 worker 已停止**，原因未查（api.log 最后一条请求在 06:13，无报错）。没有排队或运行中的任务（只有 3 个早期的 needs_info 分析/规划任务）。接手后用 `.venv/Scripts/python.exe scripts/local.py start` 补起。
- 本机当前用户没有 Playwright Chromium，安装前需用户同意。

---

以下为 2026-10-29 的交接内容，保留供参考：

更新：2026-10-29，Claude Code。**最新实现为 generation-v5**（提交 `e8632c0`、`5fbb3b2` 及之后的文档提交，以 `git log -1` 为准）。新的出卷预检已生成，**尚未授权、尚未运行**。详见[第四批记录](batch-4-validation.md)末节“generation-v5”。

## generation-v5 要点（用户决定，2026-10-29）

- 卷内题间重复：只有“题目相同且结论相同”才算重复。审阅只报告两项事实，由 `generation/originality_policy.py` 判定，检查项为必要项 `paper:intra_duplicates`。与课程原题、历年卷的比较保持原规则。
- 数学：`math_bounds.py` 用区间证明定义域；绝对值尖点分段；`MathCheckSpec.role` 区分 core 和 auxiliary（auxiliary 未判定时不阻塞但记录，判 fail 仍阻塞；旧规格按 core）。
- 拆分设计不改。下次真实运行若触发拆分，专门记录分组、调用次数、耗时和整卷检查结果。
- AGENTS.md 第 3 节：产品代码和提示词不写死课程或科目内容；既有内容按 OPT-03 移出。
- 评测样例 `backend/tests/fixtures/intra_paper_overlap_eval.json` 和 `scripts/eval_overlap_facts.py` 只做预检和评分，不发送请求；真实抽测需另行授权。

## 下一步

1. 已授权运行一次 generation-v5（任务 `e94322bf`）：Q4 生成输出达到 12,000 上限被截断。随后按用户决定实现了生成专用的 20k 输出 / 300 秒单次 / 900 秒总时限，以及跨任务复用已验证大题（`27a8d5a`）。用户授权后运行 `b02101f9`：Q1–Q3 复用，Q4 新生成；494.5 秒，287,060 tokens；最终只剩 `semantic:q3:originality` 一项阻塞（q3c 与 M14 p4 例子解题路径相同，按与课程材料比较的原规则判定），未发布。拆分未触发（语义输入 57,027 / 58,054）。下一步需要用户决定如何处理“与课程例子同路径”这类原创性问题；授权前不发起付费调用。
2. 本机当前用户没有 Playwright Chromium，安装前需用户同意；之前 Codex 的 Playwright 检查是在它自己的环境里运行的。

---

以下为 Codex 2026-10-29 早些时候的交接内容（generation-v4），保留供参考：

## 工作区与协作

- 唯一活动仓库：C:/Users/Yijia/dev/past_paper_generator，main，既有origin。OneDrive副本已停用。
- 接手按AGENTS.md：git status、git pull --ff-only、AGENTS/README/git log/本文件。同一时间只由一方改文件、数据库和服务。
- 当前运行脚本：.venv/Scripts/python.exe scripts/local.py start。不要启动重复进程。
- 项目内PostgreSQL实际数据在var/postgres-20261023/，端口54330；var/postgres/是旧保留副本。原材料和var/data、var/models、.env.local不进Git，不能认为clone自带这些数据。

## 用户最新确认

核验是同一次Generate内的阶段，不做独立核验页面、Resume validation、专用核验任务或仅继续核验接口。三项范围：

1. 精简核验输入，保留必要数学、课程与来源依据。
2. 精简后仍超限时按题/组拆分，保留整卷检查，重新考虑调用与修复预算。
3. 逐阶段保存，必要检查通过即可成功；可选项预算不足可跳过并如实记录。

必要包含结构/分值/配对、核心数学与条件、盲解一致性、知识/方法/明确偏好、基本难度、实质原创性、整卷一致性。可选仅是额外润色/解法建议/细难度建议/非必要背景引用补充。可选失败不允许将必要项降级。

来源政策仍是source-policy-v1：学术依据支撑主要知识，可接受有理由的小幅扩展；背景不限制课程来源，未核实不当成官方事实。影响解题成立的背景事实仍由必要条件/推理检查负责。

## 已实现与代码入口

- review_policy.py：冻结必要/可选类别与可选预算；execution_context.py冻结generation-v4、review-policy-v1、提示词及schema。旧授权/hash不能静默用于新策略。
- review_input.py：保留运算顺序的带括号数学表示，不化简掉定义域孔洞；不支持时保留原AST和说明。相关课程筛选、正文区间去重、版本/物理页/内容hash与用途关联，去除SVG正文。原候选不改。
- semantic_review.py：先整卷必要核验；只有官方计数超限才二分，最多4题/7个树节点。分组后追加整卷检查。缺项、重复判断、仅目录ID而无当前输入证据都不能放行。未知模型结果不拆分或自动重放。
- 保持60k/12k、16次模型调用、600秒、一轮修复。repair.py按2*修复题数+最坏必要复核次数预留调用，不够就保留报告。
- 可选阶段只在必要全通过后执行，最多一次20k/4k请求；至少60秒余量，计数10秒/模型45秒。预算不足/服务失败记not_checked，取消/租约/完整性错误仍传播；没有后台补跑。
- check_progress.py / reviewer.py：结构、数学、每题盲解、检索、语义分组、可选结果保存为不可变GenerationArtifact。最终CheckReport仍不可变；中断时构造complete=false的部分报告及必要待检查占位，不能成功。
- content_api.py / CandidatePreview.tsx：同一任务内展示阶段题号和必要/可选结果。详细推理须主动Show answers；报告版本更新会刷新已打开详情。历史无报告任务不补造检查结果。
- 无新增依赖或数据库迁移；OpenAPI验证输出与既有contracts/openapi.yaml一致。

## 验证与可操作页面

已运行：
- 后端完整223 passed（239.43秒）；最后的边界修正专项25 passed（75.19秒）及投影4 passed（15.73秒）。最终再次完整回归：**225 passed，248.24秒**。
- 前端19 passed、类型检查和生产构建通过。
- Django check 0 issues；makemigrations --check --dry-run无差异；OpenAPI验证通过且无变化。
- Playwright6组、0 JS错误、登录后0写请求：可选跳过可成功、阶段展示、必要中断保留成果、答案主动打开/刷新、390px、旧真实失败不改状态。截图已查看。
- 上述属于实现阶段验证：后端测试阻断真实OpenAI传输。后续本次真实运行另有12次模型+12次计数，详见下文；没有重新运行上述全量回归。

合成演示（课程a1d95d44，B4-REVIEW-FIXTURE，不代表模型质量）：
- 成功且可选跳过：http://127.0.0.1:5173/tasks/ba5ca16b-99e9-4b79-b8fa-4e5329dc11fc
- 必要核验中断、q1成果保留：http://127.0.0.1:5173/tasks/bec205be-1814-4606-a403-0cad78f8a5ef

本机证据：var/review-budget-fixture.json、var/review-budget-browser-check.json、var/screenshots/review-budget-*.png。
内置浏览器打开请求返回queued；实际页面可用性已由Playwright验证。

## 最新真实数据状态

真实QM课程68caa35d-6e08-42d7-84bd-70a23e369b1f，确认version2；快照68a09ab1-6059-4b59-a4af-6d3b880f1b2d（4大题/15小问/60分/90分钟建议作答时长）。

最新任务7496b3cb-8a75-46bf-9840-a1839f193f5d，2026-10-29 18:20:41–18:30:16，执行574.929秒。
- 新context hash 99c7a804c9634108ee3253302c0262fb086849d4db7cb438cecdd90fa51da567。33页及整个input与上一真实任务32bb6d9c一致，无新页图。
- 用户明确授权在新预检下运行一次，已通过网页新预检提交；该次运行结束，不据此自动再发起付费生成。
- 官方gpt-6.1-sol，store:false；12次模型、12次计数，全部completed，模型全部parsed，无未知结果、超时或输出截断。
- usage输入251,203、输出64,410、合计315,613。费用未查询；cached 8,282已含输入、reasoning 5,811已含输出。
- 语义输入57,426/59,784，模型耗时58.653/59.715秒。均未超60k，真实拆分没有触发，拆分耗时仍待实测。最终只剩216-token输入余量。
- 生成四题后首轮检查发现Q3原创性及定义域验证问题，系统完成一次Q3定向修复，再核验整卷；其余三题和独立解题复用。
- 最终failed / REQUIRED_CHECKS_BLOCKED：87必要项78pass、3fail、5inconclusive、1not_checked。16可选语义项因必要项未过跳过，不是可选token超限。
- 修复后Q3(d)重复Q1(d)的振荡函数与解题路径，构成题间提示；数学工具不能处理部分三角/对数定义域和绝对值辅助最值。这不是已证明极限答案错误。
- 候选v1 d0e3f82f-50a7-4694-8e82-431dc99dfa1a；v2 94917b7c-f194-431c-90ba-01d5d7e821c8。两份完整CheckReport均保存；未发布。
- 页面：http://127.0.0.1:5173/tasks/7496b3cb-8a75-46bf-9840-a1839f193f5d 。可切Saved candidate，Show answers后看Detailed check report。
- 离线回放重现5个本地阻塞，候选/报告hash通过；真实页面6组检查通过、0 JS/KaTeX错误、登录后0写请求。原记录没有修改。

本机忽略证据：var/generation-v4-live-preflight.{json,md}、generation-v4-live-receipt.json、generation-v4-live-observation.json、generation-audit-7496b3cb-8a75-46bf-9840-a1839f193f5d.json、generation-v4-live-browser-check.json、generation-v4-live-final-status.json。完整含时序报告见[真实实测](batch-4-live-generation-v4-2026-10-29.md)。

旧32bb6d9c保留：原generation-v3语义输入67,531超限，未调用语义模型且没有完整报告。本次没有恢复或改写它。此前离线同内容201,697→174,982字符（−13.25%）只代表字符变化，不能和本次不同候选的实际token直接作因果比较。

## 下一步与未验证事项

建议范围尚未实施：
1. 增强修复时的全卷去重：输入已有其他题摘要，但模型仍重复了决定性表达式和证明步骤；需要更明确的避免重用约束及本地结构检查，不能把共享课程方法一律视为重复。
2. 补数学定义域/界证明、分段处理和检查能力约定。当前每个模型提供的数学规格都作为必要项，新增辅助规格会额外阻塞；需按核心结论和辅助证据分别明确责任，不擅自将未知改pass。
3. 容量仍紧，真实拆分与可选预算分支未覆盖；574.9秒也未达两分钟目标。先在本地用本次保留数据检查上述问题，再安排新的明确真实运行。

当前单次运行已结束，没有继续付费调用授权。不得把旧Grant或密钥存在理解为无限重跑。若用户明确提出下一次运行，沿用既定数据范围并核对新预检，无需重复询问已授权内容。

核验仍属于Generate，不加Resume validation。批次5（阅读/PDF/发布）和6（六次验收）未进入；不要把本次失败实测计为六次验收通过。

历史记录：
- 344da144：第一次真实候选及未放行检查保留，修复needs_info。
- bda61a74：Q1输出截断；仅Q2完整保存。
- 9033ae45：用户取消，两次模型请求结果/用量未知，不按零费用处理或重放。
- 8f2e167c：旧引用白名单失败；原记录保留，之后已实现来源分层。
- 00dd1359：来源分层合成演示，0模型调用。

scripts/audit_generation_task.py适用于本次7496b3cb（已执行）；原32bb无完整报告，仍应使用audit_review_projection.py。测试/演示helper会新增独立fixture，不改真实课程。


## 最终运行状态

2026-10-29 18:34:23：web/api/worker/dispatcher均为本项目活动进程；5173、8000/API session、前端代理session均200。0活动任务，本次24条调用记录均有终态，结束后0新增调用。服务保留运行，证据var/generation-v4-live-final-status.json。页面可直接访问，无需重复启动。
