# 第三批实施与验证记录

日期：2026-10-23–24（Asia/Shanghai）。范围：首轮计划 Task 5–6，配置、AI②蓝图规划、结构校验与确认、冻结生成输入。首轮正式计划和已有需求文档未改写；执行细化记录见 [第三批计划](superpowers/plans/2026-10-23-batch-3-blueprints.md)。

## 结论与边界

第三批本地功能已实现并通过检查。实际服务、数据库、队列与浏览器上的完整流程使用明确标记的独立 fixture 课程；真实规划模型调用 **0 次**，PlanningGrant **0 条**。真实 AI②的数学/教学适合性、耗时和费用尚未验收，不能用 fixture 结果代替。

真实 QM 课程 `68caa35d-6e08-42d7-84bd-70a23e369b1f` 的用户修改草稿 revision 3 保持不变，确认版本数仍为 0。本批不替用户消除前批读取缺口或确认课程。65 个原始路径 hash 全部一致，11 个已导入唯一材料的解析结果保留；原材料和历史原型未改写。

本批输出止于 `GenerationSnapshot`。首轮 Task 6 中“开始生成”的后端版本校验已预留；有效绑定暂返回 `QUESTION_GENERATION_NOT_AVAILABLE`（501），失效绑定拒绝；UI 的 Generate practice 禁用并说明第四批边界。没有伪造题答生成任务、题卷、答案或两个输出 PDF。AI③/④属于第四批，网页成卷与 PDF 属于第五批，六次真实验收属于第六批。

## 实际交付

| 领域 | 文件与行为 |
|---|---|
| 配置及不可变记录 | `backend/app/generation/models.py`、两份 migration：GenerationDraft、Blueprint、StructureConfirmation、GenerationSnapshot、PlanningGrant。配置 CAS revision；其他四类记录有模型与数据库 UPDATE 拒绝保护 |
| 结构契约 | `generation/schemas.py`：2–4 大题、三档难度、三类作答要求；每题小问、知识、来源、素材；独立计算总分、选答分数和覆盖。不相信模型自报汇总，不静默删除所选知识或题型 |
| AI② | `generation/planning.py`、`ai/prompts/blueprint.md`：冻结已确认课程与精确输入；保留教学/历史/声明分类；只规划结构，不生成题答；严格 schema 仍需业务校验 |
| 规划运行 | `core/management/commands/plan_practice_one.py`、`core/queue.py`：沿用持久任务、epoch、心跳、deadline、调用记录和唯一发布；过时排队任务在调用前结束；已在途迟到结果可保留为历史但不能覆盖当前配置；取消后禁止发布 |
| 修改与确认 | `generation/snapshots.py`：结构每次编辑生成新不可变修订；程序重算分数和差异；确认绑定课程版本、配置 revision/hash、蓝图 ID/hash。3→4→3 也不会恢复旧确认 |
| 冻结 | 包含课程 payload、证据版本、声明、配置和蓝图版本/hash、确认 ID、历史截止、限额版本。历史内容 ID 为空，明确标记尚无 Papers；不声称已执行历史去重 |
| API | `generation/api.py`、`config/urls.py`、`contracts/openapi.yaml`、`frontend/src/api/generated.ts`：工作区、配置保存、规划预检/提交、结构读取/编辑/确认、输入冻结与读取；Session、CSRF、归属校验沿用现有基础 |
| 页面 | `frontend/src/features/generate/{GeneratePage,StructureSummary,config-state,useAction,types}` 与 `generate.css`；左配置右结构、手机单列、来源跳转、差异、显式保存、确认、历史输入快照、空/加载/失败/超目标状态 |
| 恢复与冲突 | 配置与提交使用稳定请求 key；未知结果在当前标签 sessionStorage 恢复；显式重试使用原 key；双标签 409 保留本地编辑供比较。字段错误显示可读路径/原因 |
| 旧结果找回 | `features/tasks/TaskPage.tsx` 显示规划阶段、模式和调用记录；原始蓝图可直接查看，不随后续结构编辑或参数变化而改变 |
| 启动 | `scripts/local.py restart-workers` 仅重启本项目 worker/dispatcher，存在 queued/processing 任务时拒绝；避免为队列代码更新重启数据库。本批未增加依赖 |

接口路径均以 `/api/v1/courses/{course_id}` 为前缀：

- `GET /generation-workspace`；`PATCH /generation-config`。
- `GET /planning-preflight`；`POST /plans`。
- `GET/PATCH /blueprints/{id}`；`POST /blueprints/{id}/confirmations`。
- `POST /generation-snapshots`；`GET /generation-snapshots/{id}`。
- `POST /generations`：只校验当前绑定并如实返回后续能力未实现，不提交任务。

复用成功调用只在原任务的调用 checkpoint 内发生；新规划提交是明确的新任务，不宣称实现跨任务语义缓存。课程确认和结构确认均不把 user_statement 升格为官方事实。

## 实际检查

以下均为已运行结果，使用本机 Python/Node 服务；没有运行原计划中拟定的 Docker 命令或 Node Playwright e2e 命令。

| 检查 | 结果与覆盖 |
|---|---|
| `python -m pytest -c backend/pytest.ini backend/tests -q --basetemp=var/pytest-batch3-evidence-final --tb=short` | **98 passed，91.43 秒**；独立 PostgreSQL 测试库。新增三组测试共 35 项，覆盖分数、选答、混合覆盖、来源、所有权、幂等、不可变记录、取消/迟到、未知模型/拒绝/截断/信息不足、忙碌时禁止旧结构冻结；历史卷不能单独代替每题的教学依据 |
| `pnpm --dir frontend test --run` | **12 passed**；7 项配置绑定/恢复测试与 5 项原课程保存回归 |
| `pnpm --dir frontend build` | TypeScript 与 Vite 生产构建通过；1653 modules，无构建错误 |
| `manage.py check`、`makemigrations --check --dry-run` | 系统检查 0 issues，迁移无遗漏；generation 0001/0002 已应用 |
| `manage.py spectacular --file contracts/openapi.yaml --validate`、`pnpm --dir frontend api:types` | 校验与生成通过，预检 schema 命名冲突已修复，无最终导出警告 |
| `scripts/test_generation_workspace.py` | **13 项通过**，实际 API/后台 worker/浏览器；见下表。模拟数据不调用模型 |
| `scripts/test_course_profile.py` | **9 项通过**；真实草稿只读检查，编辑/两次确认/澄清只作用于新建 B2-TEST 课程 |
| `scripts/test_workspace.py`、`scripts/test_ai_validation_view.py 32726231-997a-4c00-825d-60fbafc282d0` | **8 + 7 项通过**；材料/来源/旧真实调用记录回归，不重新调用模型 |
| 保存结果页面只读检查 | **3 项通过**：旧任务原始三大题、刷新保留身份与分值、无 JS 异常；JSON 记录在 `var/batch3-saved-task-checks.json` |
| `manage.py audit_batch1` | **65 个原始路径，0 hash 差异**；11 个唯一材料现有解析保留，记录 `var/batch1-audit.json` |

浏览器第三批的 13 项检查：

1. 真实 QM 没有确认版本，Generate 显示回 Course profile 的入口，不能提交规划。
2. fixture 规划经过实际队列/worker 产出三大题结构；刷新找回同一任务。
3. 编辑小问分值及建议时长，确认失效；服务端重算总分并保存独立修订。
4. 选答分值不一致返回可读错误，不能确认；错误结构未保存。
5. 确认绑定与输入快照刷新可恢复；没有冒充生成题答。
6. 3→4→3 在未保存和保存后均不能恢复旧结构确认。
7. 四大题新计划显示实际结构与程序差异。
8. FX01 来源链接打开同一合成 PDF 版本第 1 页，刷新保留。
9. 两个标签发生真实 HTTP 409；保留本地编辑直至显式选择。
10. 故意中断一个本地配置 PATCH，刷新后保留输入与请求 key，再次保存成功。
11. 390px 宽度没有横向溢出；桌面及手机截图留存。
12. 后续四大题配置不改变原三大题快照。
13. 没有未捕获浏览器 JavaScript 异常。

初次测试的失败有保留：结构规则先以未实现异常失败后实现；前端构建曾因 unknown 输出类型失败并修复；浏览器脚本曾在未关闭的模态框后误操作背景、标签定位过宽，均修正后重新执行。课程页回归还发现了实际缓存问题：刚确认版本 2 时 Generate 先采用缓存中的版本 1。现仅允许未编辑的默认配置随新确认版本更新，已保存、已编辑、已恢复输入保留；新增两项单测及完整课程页回归通过。旧任务查看检查首次匹配到三条重复分值文字，收窄至第一题后通过。

## 可查看的结果与证据

- 模拟 Generate：<http://127.0.0.1:5173/courses/5557e765-063f-4170-a75d-970799a675f1/generate>，在内置浏览器保留。
- 真实 QM Generate 门禁：<http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/generate>。
- 模拟原始三题任务：<http://127.0.0.1:5173/tasks/150b61f9-4a5d-409b-ab66-1e19e97c7a3d>；22.5 分、40 分钟仅是测试数据。
- 模拟最新四题任务：<http://127.0.0.1:5173/tasks/ff7e43ae-c66f-4112-b9bf-dc065f530234>；36 分、55 分钟仅是测试数据。
- 快照：`734fba79-6b52-415d-b61c-bc99ca043bb2`（三题，人工结构修改后）；`20e1815e-ba9e-4f8d-8134-682572fb2eb2`（四题）。页面 Prepared inputs 可打开。
- 测试证据：`var/batch3-browser-checks.json`、`var/batch3-database-check.json`、`var/batch3-saved-task-checks.json`、`var/batch2-browser-checks.json`；截图 `var/screenshots/generate-overview.png`、`generate-desktop.png`、`generate-mobile.png`、`planning-task-original.png`。

`var/` 中是私有运行数据，保持 Git 忽略；上述 fixture、失败测试和原任务均保留，未清理用户历史。服务启动入口与复跑脚本见 [README](../README.md)。

## 对应验收与尚未执行

| 验收 | 本批证明范围 | 后续证明范围 |
|---|---|---|
| AC-07-01 | 章节模式、三档难度、2–4 大题与三类题型字段有效；蓝图不得缺所选类型/知识 | 真实模型难度适合性、成卷输出；完整模拟卷不在首轮 |
| AC-07-02 | 参数变化显示差异、失效确认拒绝；后端版本绑定生效 | 正式题答任务创建接入与成卷对照 |
| AC-07-03 | 本次配置独立、课程默认不改写；分数/时长是可编辑建议 | 真实样本的结构与时长校准 |
| AC-07-04 | 小问预计/锁定状态及程序计数 | 第四批验证最终题答实际数量与锁定一致 |
| AC-12-01 | 幂等提交、双标签冲突、任务/快照刷新恢复，规划唯一发布 | 正式题卷唯一发布与 Papers 找回 |

真实 AI②尚缺两个前置条件：系统完成原有课程读取缺口处理并获得可用确认版本；用户对届时展示的精确规划输入授权。第二批授权用途只含课程分析，不能自动改作规划。已有 API key，无需再次提供。本批没有新外发范围请求，因为当前还没有可运行的真实确认版本。

后续可独立推进题答契约、程序核验、素材与 PDF 渲染、故障/恢复测试；真实模型基线需要上述前置条件满足后再执行。第三批的 API 接入代码已就绪，不能据此声称已验证教学质量或两分钟目标。

时效性参考：2026-10-23 查阅 [OpenAI Structured Outputs 官方文档](https://developers.openai.com/api/docs/guides/structured-outputs)，确认需显式处理拒绝/不完整输出，并保留独立业务校验。没有据此新增价格或模型性能结论；沿用既有官方 Responses 适配器，`store:false` 不代表零数据保留。

## 真实 AI② 规划验证（2026-10-24）

前置条件已满足：真实 QM 课程有了确认版本 1（`43a7db06-2d04-40f8-9b50-65a6ad307c0e`，来自 revision 6，由用户在页面上确认）；用户在 Generate 页面保存了配置 revision 1。用户随后在对话中授权 context hash `78ad48defe67b7ed6ba67386b9df2cd317bc956fac2f7816673158ebfd6996a6` 的规划输入，写入 1 条 `PlanningGrant`。发送内容为冻结的课程版本、配置、两条用户声明和 45 页来源索引；**不含原页文字、页图或转写**。本地准入估算 45,308 字节，规划阶段仍按字节判断准入。

配置：章节练习，Exam-standard，3 道大题，题型为计算 / 解释证明 / 应用优化，8 个知识组全部选中。

| 项目 | 实际值 |
|---|---|
| Task | `780eb12c-24ea-4a3b-aa20-ed0909e36320`，succeeded |
| 调用 | 1 次，`gpt-6.1-sol`，`store:false`，51.1 秒；input 14,710，output 3,211（含 reasoning 222），total 17,921 |
| 提交到终态 | 55.4 秒（排队 1.4 秒） |
| 蓝图 | `b72acc98-afb7-4ff8-a834-e1e03e5b90fc`：3 道大题、12 个小问，19 + 18 + 23 = 60 分，全部必答；建议 80 分钟；程序重新汇总的分数与印刷分数都是 60；8 个知识组和 3 种题型都覆盖到 |
| 原始记录 | `var/batch3-live-780eb12c-24ea-4a3b-aa20-ed0909e36320.json`（本地私有） |

内容观察，属于结构规划，不代表题目质量：
- Q1 覆盖导数定义、单侧导数、求导法则、隐函数求导。
- Q2 覆盖 Rolle 和中值定理、L'Hôpital（含对错误重复应用的诊断）、单调性。
- Q3 是带闭区间可行域的利润优化，区分局部分类和全局结论，并沿用 critical point 只指 f′=0 内点的约定。
- 蓝图说明会避开有争议的原文陈述，改用新编例子；它还写明，用户尚未回答的那个练习偏好问题不视为已回答。

**发现的问题**：小问标签的 schema 上限是 30 个字符（`generation/schemas.py:38`）。严格结构化输出会强制这个上限，所以模型原始输出中的标签在 30 字符处被截断，例如 “(a) Derivative from the limit,”。程序校验本身没有错误，但标签显示不完整。是否放宽上限、或把短标签和小问说明拆开，需要用户决定；改动会改变 schema 和 context hash，需要重新规划。

尚未执行：结构确认、冻结生成输入，这两步由用户在页面上操作；AI② 的教学适合性和耗时只有这 1 次样本，不代表稳定水平；实际扣费未查询。

### 修复：小问编号与考点说明分离（blueprint-v2）

用户选择了拆分方案。提交 `e32a324`：
- `label` 只允许单个小写字母，每道大题内按 a、b、c… 连续编号；schema 里写有 pattern，程序再校验一遍。
- 新增必填字段 `focus`（不超过 200 字符），用来说明这一小问考什么，不写题面内容。
- 提示词和 schema 都升为 `blueprint-v2`。
- 旧的 v1 蓝图（包括真实蓝图 `b72acc98` 和 fixture 蓝图）仍按 v1 规则校验，照常可以编辑和确认；编辑时不能悄悄换版本；模型新产出的蓝图必须是 v2。
- 结构编辑页面只在 v2 蓝图上显示 focus，并支持修改。

检查：后端 pytest **149 passed**（新增 8 项）；前端 tsc、vitest 12 项、build 通过；OpenAPI 无变化；内置浏览器只读检查，真实课程的旧蓝图照常显示，没有控制台错误。

新的规划预检（只读，**未授权**）：context hash `b0262a8d18c5049d3f3360275618e782fe4887ba1cb64c52cd9ea3785a3c8d8a`。输入内容与上次授权的 `78ad48de…` 完全相同，包括确认版本 1、配置 revision 1、两条声明和 45 页来源索引；变化只有提示词和 schema（v2）。本地准入估算 45,863 字节。

### v2 重新规划（用户授权 context `b0262a8d…`）

| 项目 | 实际值 |
|---|---|
| Task | `7647b9e5-a4ab-459c-b51a-6fcb05ce7a08`（parent `780eb12c`），状态 **needs_info**，没有蓝图 |
| 调用 | 1 次，8.8 秒；input 14,826，output 241，total 15,067；提交到终态 12.5 秒 |
| 原始记录 | `var/batch3-live-7647b9e5-a4ab-459c-b51a-6fcb05ce7a08.json`（本地私有） |

模型要求先回答课程草稿里那个尚未回答的 `needs_confirmation` 问题，即五处原文问题按什么方式出题：反函数复合、平方根定义域、正则性断言、极限去向冲突、全局最优缺少论证。可选做法是：(a) 只作为批判性材料保留；(b) 用标准解释并注明差异；(c) 暂不纳入。它同时确认极值和 critical point 的约定已经定下，不再重开。

上一次 `780eb12c` 的输入只是提示词和 schema 不同，模型直接给出了蓝图，并写明“没有把这个问题当作已回答”。两次结果说明，这个未答的问题会让规划结果不稳定；这次 needs_info 有可能和 v2 提示词有关，但仅凭一次样本无法判断。按设计，needs_info 是一个真实的终态：当前结构没有被替换，`b72acc98`（v1）仍是当前蓝图，确认等操作不受影响。如何处理这个问题由用户决定。

### 课程 version 2 上的规划预检（只读，未授权）

用户确认了课程 version 2（`fc4cae89-1988-48e9-8540-52c3b97541bc`，来自 revision 8，包含两条练习偏好），并在 Generate 页面改选 version 2，保存为配置 revision 2：章节练习、Exam-standard、3 道大题、3 种题型、8 个知识组全选。

规划预检的 context hash 为 `d04032bb5dc0011ab0f6fd520e617d02af89a97deaeabaf615ef46bc5da1eaf0`，使用 blueprint-v2 提示词和 schema。发送内容是 version 2 的冻结课程（含 10 个问题项、8 条方法规则、6 条范围声明、2 个已回答的澄清问题，以及 3 大题 × 20 分、90 分钟的建议模板）、3 条用户声明和 45 页来源索引；不发送原页文字、页图或转写。本地准入估算 49,075 字节；最多 2 次调用，任务时限 180 秒，单次 150 秒。

### 课程 version 2 上的真实规划（用户授权 context `d04032bb…`）

| 项目 | 实际值 |
|---|---|
| Task | `19d0368b-8420-4295-90e2-aab1e82b487d`（parent `7647b9e5`），succeeded |
| 调用 | 1 次，59.3 秒；input 15,884，output 3,625（含 reasoning 200），total 19,509 |
| 提交到终态 | 63.9 秒（排队 1.7 秒），在 180 秒任务时限内 |
| 蓝图 | `77475f5e-5ff9-4c41-85f9-d6a3ec3b168f`，**blueprint-v2**，已成为当前结构 |
| 原始记录 | `var/batch3-live-19d0368b-8420-4295-90e2-aab1e82b487d.json`（本地私有） |

结构（程序已重新汇总校验）：3 道大题全部必答（每题单独一节），共 13 个小问，22 + 18 + 20 = 60 分，建议 95 分钟，小问数量未锁定；8 个知识组和 3 种题型全部覆盖。各小问标签依次为 a、b、c…，都有完整的 focus，例如 Q1(a) “First-principles differentiation and tangent-slope interpretation”。上一版的标签截断问题没有再出现。

- Q1 求导基础（22 分）：导数定义与切线斜率、单侧导数、求导法则与定义域、高阶导数与正则性、隐函数求导。
- Q2 定理与极限（18 分）：Rolle 和中值定理的条件与结论、导数界论证、洛必达法则及其重复适用性检查、对错误重复使用的诊断。
- Q3 商业建模（20 分）：闭区间可行域、边际解释、驻点与局部分类（含二阶导数检验失效的情况）、单调性、端点比较得出全局结论。

用户偏好已体现在模型的 differences 中：采用邻域局部极值并保留 critical point 约定；涉及平方根或反函数时，注明原文定义域不完整或恒等式印错，不把它们当作正确结论使用；极限去向必须明确；错误诊断使用新编题，不照抄标为 WRONG 的证明；全局最优必须说明可行域，近似值要标明。

尚未执行：结构确认、冻结生成输入，这两步由用户在 Generate 页面操作。

### 结构确认与输入冻结：批次三真实验证完成

用户在 Generate 页面确认了蓝图 `77475f5e…`（revision 1，未修改），随后点击 Prepare generation。以下核对只读本地数据：

| 项目 | 结果 |
|---|---|
| 结构确认 | `40c52d02-a555-49f7-95f7-6988ca9d6ea8`，绑定配置 revision 2、课程 version 2、蓝图 hash；`binding_valid = True` |
| 生成输入快照 | `7e2a758e-7e7e-4a03-b618-e7c12d56b708`，schema `generation-input-v1`，mode live；payload hash 校验通过 |
| 内容一致性 | 快照中的蓝图、课程 payload、配置，与蓝图记录、课程 version 2 冻结内容、配置 revision 2 **完全相同**，各自的 hash 也一致；含 3 条声明、45 页来源索引 |
| 历史 | `history_cutoff` 已冻结；`history_content_ids` 为空，`history_status = not_available_before_paper_storage`，因为 Papers 尚未实现，所以不声称已做历史去重 |
| 生成限额 | `r1-limits-proposal-1`：16 次调用、1 轮修复、600 秒，供批次四使用 |

**批次三验收结论**：配置、AI② 规划、结构编辑与确认、冻结生成输入四个环节，都已在真实课程上走通。验证范围限于本次流程能证明的内容：
- 配置变更会产生新确认；
- 程序会独立重算分数和覆盖；
- 绑定校验有效；
- 快照不可变，且与来源一致。

没有证明的内容：AI② 的出题适合性（只有 3 次样本，其中 1 次 needs_info）、实际扣费，以及六次真实出卷验收（属于批次六）。在批次四接入前，Generate practice 仍返回未实现状态。

本轮发现并修复的问题：小问标签截断（改为 blueprint-v2）；澄清回答没有附带原问题；分析单次时限过短（课程分析放宽到 300 秒）。另外，规划在用户偏好未回答时会返回 needs_info，这是真实终态，当前结构不会被覆盖。
