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
