# Round 1 Batch 6 Acceptance Implementation Plan

> **For agentic workers:** 按 Task 11/12 的子任务执行与检查，步骤使用 checkbox。遵循主线单写者和实际可用工具；本侧聊仅更新计划，不执行代码或子代理。

**Goal:** 验证首轮真实章节练习的完整流程，保留六次 Topic 2 验收，并增加一次新 Topic 从新材料开始的完整流程记录。
**Architecture:** 复用现有课程分析、规划、生成核验、Paper 和独立 PDF 任务。新增验收配置、隔离故障测试与只读报告；新增 Topic 前置能力见 U1–U3，跨 Topic 混合生成由第二轮 U4 交付。
**Tech Stack:** 当前锁定的 Windows 项目 venv / Django / PostgreSQL / React / Playwright / KaTeX；不用原计划中尚未落地的 Docker 命令。
**Spec:** [原首轮 Task 11–12](2026-10-19-round-1-qm.md)、[首轮设计 §3.5](../../round-1-design.md)、[整课 UI 设计](../../course-topics-workspace-design-v0.1.md)、[Topic 工作区计划](2026-11-01-course-topics-workspace.md)。

日期：2026-11-01。状态：**本次用户要求更新方案；下列开发、测试、结构确认和真实调用均未执行。** R1–R6 的具体蓝图仍须运行前确认；E1 的新 Topic 与精确输入待本地核对后冻结。本文不授权新的外发或费用。

## 1. 相对原计划的调整与当前基线

- R1–R6 继续使用 Topic 2；它们重点验证生成、核验、难度/题量、历史与 PDF。
- 新增 E1，使用一个新 Topic，从新课程/新草稿状态运行真实材料导入、分析、必要澄清、确认、规划、生成、核验、网页与双 PDF。**E1 是额外一次，不占六次名额，不冒称六次变成六次全部从零分析。**
- 使用独立验收 Course 起步；可以复用同 hash 的原文解析缓存，但不能复用 Topic 2 的分析草稿、知识目标、蓝图或答案。跨 Topic 浏览/切换先以同 Course 多 Topic 的隔离 fixture 检查，E1 不要求重建真实主课程。
- 第六批之前加入 U1–U3 的目录、材料归属、动态分析、按 Topic 审阅和整课知识树单章配置。它们是新增前置开发范围；纯测试和评测记录工具可先做。
- 跨 Topic 多选的最终 UI 已设计；多章节真实组卷仍在第二轮首批 U4，不以新 Topic 单章成功替代。
- PDF 按用户主动触发，题答成功和 PDF 就绪分开；计时分别记录生成、导出、用户等待及完整系统耗时。
- 速度/模型用量专项优化按既有 backlog 后置。首轮可保留清楚的性能缺口；严重内容错误与流程缺陷必须修正或标未通过。
- 第五批记录基线：原真实任务 d5a7434f…；5 页题卷/16 页答案，导出 9.831 秒；生成约 337 秒，超 120 秒。离线 287 项全库及后续 17/26 项回归、前端 23 项是已有证据，不是本批测试结果。

## Global Constraints

- 保留原材料、所有已确认版本、旧任务/失败、Paper/PDF；测试故障不能破坏日常工作区。
- 不安装无必要新依赖；沿用 scripts/local.py 管理服务，不能重复启动后台进程。
- 正常测试禁止真实 API；真实验收只经既有精确预检与有限任务预算，未知结果不自动重放。
- 英语产品 UI/题答，中文项目说明；Topic/知识及材料编号放课程数据/验收 fixture，不能写进通用实现。
- 来源政策沿用最新用户决定：学术依据支持主要知识点、有理由的小幅扩展可接受；背景不受课程范围限制；未核实事实如实标记。
- 重复规则沿用当前 generation-v6 的题目与结论事实判定；相同方法本身不判重复。
- 本批不恢复被用户撤回的来源意图专门约束，也不增加学生逐卷人工审批步骤。验收审阅是研发活动。
- 失败占原计划位置，补测另编号；无法判断与未检查不算通过；零适用项不报 100%。

## Review Focus

1. “从零”测试偷偷借用 Topic 2 草稿或固定目标：U3.1 + Task 12.3 E1 的输入/来源审计。
2. 跨章节筛选影响已保存练习或关闭来源丢筛选：U2/U3 + Task 11.2 浏览器断言。
3. 用户等待被算成系统慢，或 PDF 时间被从完整交付删掉：Task 12.1 计时测试。
4. 历史增长让输入超限、重新用了已成功大题：Task 12.2 R1–R3，新 history hash、调用输入和重复结果检查。
5. 失败/补测/换版本覆盖原样本造成虚假成功率：Task 12.1 accounting 测试，Task 12.4 报告检查。

## 2. 实施顺序

U1–U3 Topic 前置 → Task 11.1/11.2 集成检查 → Task 12.1 验收工具与口径冻结 → R1–R6 → E1 → Task 12.4 汇总。
Task 11 的已有链路故障测试和 12.1 的统计工具不依赖新材料/模型，可先完成。若 E1 尚缺能力，应明确记录阻塞点；不因此把 Topic 2 六次替换掉或把 E1 写通过。

### Task 11.1：跨阶段恢复与诊断

**文件**：新增 backend/tests/test_round1_recovery.py、test_diagnostics_redaction.py；复用 test_task_lifecycle.py、test_generation_snapshot.py、test_generation_review_budget.py、test_papers.py。发现实际缺陷后才修改对应 core/tasks、generation 或 papers 模块，不先大范围重构。
**接口**：既有 submit/claim/checkpoint/cancel、生成与 export API；故障注入仅在隔离测试配置，不能提供普通用户故障开关。

- [ ] 写集成断言：双击/双标签提交、未知网络响应后同 key 重试、worker checkpoint 前后退出、旧 epoch 写回、取消与发布竞争；历史数量和内容 hash 正确。
- [ ] 写失败断言：拒答、截断、输入超限、必要语义未完成、可选项预算不足、一个 PDF 失败/丢失；候选/阶段成果保留，未检查不报通过。
- [ ] 写日志断言：用合成 secret/全文标记检测泄漏；usage 缺失保持 null，attempt 和 error diagnostic 不丢。
- [ ] 在独立随机 PostgreSQL 测试库执行，确认缺陷可复现后最小修复，再复跑相关测试。
- [ ] 无阻塞缺陷后，在主线提交 test: verify round-one recovery and diagnostics。

**拟命令**：.venv/Scripts/python.exe scripts/test_batch5_backend.py tests/test_round1_recovery.py tests/test_diagnostics_redaction.py -q。
**完成条件**：错误状态、版本、取消与唯一保存有完整断言；不把合成异常当真实质量。对应 P0-12、AC-14-03，结合各批首轮相关 AC。

### Task 11.2：页面全流程、Topic 切换与输出

**文件**：新增 scripts/test_round1_flow.py、test_round1_views.py；复用 test_workspace.py、test_course_profile.py、test_generation_workspace.py、test_batch5_browser.py；必要时扩展现有前端组件测试。
**接口**：真实产品路由与 API；隔离 fixture owner/course，不写入真实课程以制造异常。

- [ ] 检查 Materials → Profile → Generate → Task → Papers → PDFs；来源固定版本/物理页，答案未主动打开时不发答案请求。
- [ ] 在同 Course 的两个 Topic fixture 验证材料归属、共享文件、保存切章、局部确认、整课知识树、配置确认失效、历史冻结。
- [ ] 核对五视图 empty/loading/error/timeout/success/long-content；1440/1024/768/320px、键盘焦点、aria 状态、颜色对比、公式局部滚动。
- [ ] 检查刷新/后退/重新登录、迟到响应、服务重启后的原任务和 Paper 找回；无任务时才重启正常服务，故障进程使用测试实例。
- [ ] 使用已有真实材料检查 hash 与来源；用户主动新增版本另记差异，不覆盖历史。检查已生成实际双 PDF 的全页图。
- [ ] 运行 typecheck/build 和受影响组件测试；主线提交 test: cover topic navigation and end-to-end reading。

**拟命令**：.venv/Scripts/python.exe scripts/test_round1_flow.py --fixture；.venv/Scripts/python.exe scripts/test_round1_views.py --fixture；pnpm --dir frontend typecheck；pnpm --dir frontend build。
**完成条件**：完整流程可用，所选 Topic 不串数据，界面与后台能力一致；对应 AC-03-02、AC-06-01/03、AC-07-02、AC-10、AC-11、AC-12 的首轮子集。

### Task 12.1：冻结 manifest、rubric 与记录工具

**文件**：新增 evals/__init__.py、evals/round1/{__init__.py,manifest.yaml,rubric.yaml,records.py,run.py,report.py}；新增 backend/tests/test_eval_accounting.py；报告目标 docs/batch-6-validation.md。
**接口**：
- run_acceptance(manifest_path: Path, run_id: str, grant_reference: str | None) -> RunRecord；默认只预检，不发真实请求；显式 --execute 且授权匹配才调用既有任务服务。
- collect_run(run_id: str, task_ids: list[str]) -> RunRecord；只读现有成果、日志和 hash。
- summarise_runs(records: list[RunRecord], rubric: Rubric) -> AcceptanceReport。
- report 不直接调用模型；原始证据保存 var/evals/round1/{run_id}/{attempt_id}/，Git 只保存计划与脱敏结论。

RunRecord 至少包含：
run_id、planned_slot、baseline_version、course/topic/knowledge/material/parse/blueprint/history/prompt/model/limits IDs/hash、任务/attempt/调用 IDs、状态、各阶段时间、真实 usage 或 null、费用估算与价格来源或 unknown、Paper/Content/PDF hashes、检查报告、逐题复核依据、额外复测关联。

- [ ] 写统计测试：6 个原位置含一次失败仍 planned_total=6；E1 单列；补跑不替换失败；三次同配置为三个新意图，网络重试不变新意图。
- [ ] 写时间测试：排队/自动重试/修复纳入所属阶段；生成与 PDF 用户等待间隔单列；并行调用时长不相加冒充墙钟时间；缺 PDF 的交付为 incomplete。
- [ ] 写版本测试：中途换 prompt/模型/限额产生新 baseline_version，不能混成单一冻结基线；未知 token/cost 不记零。
- [ ] 实现记录/预检/收集/报告工具，复用已有调用与授权校验，禁止自动循环直到成功。
- [ ] 将下方 R1–R6/E1 以及评分口径写入 manifest/rubric；运行测试，主线提交 feat: record reproducible round-one acceptance runs。

**拟命令**：.venv/Scripts/python.exe scripts/test_batch5_backend.py tests/test_eval_accounting.py -q；.venv/Scripts/python.exe evals/round1/run.py --manifest evals/round1/manifest.yaml --run R1 --preflight。
**完成条件**：缺授权时只能导出预检；所有失败、重试、等待和版本可审计。对应 AC-14-04、NFR-01/02 计时口径。

## 3. R1–R6：Topic 2 六次验收矩阵

全部 chapter practice、全必答，选择 Calculation、Explanation / proof、Applied optimisation 三类；小问数在蓝图确认时锁定。以下是验收配置，不是产品永久题量/分值规则。

| Run | 难度 / 大题数 | 每题分值；小问数 | 建议作答分钟 | 目标与比较 |
|---|---|---|---:|---|
| R1 | Exam-standard / 3 | 12/8/10；3/2/3 | 40 | K1/K2 求导与可导；K5 定理论证；K3/K4 极值与应用 |
| R2 | 同 R1 | 同 R1 | 40 | 同确认蓝图、新题，比较初始历史 H0 与 R1 |
| R3 | 同 R1 | 同 R1 | 40 | 同确认蓝图、新题，比较 H0 与 R1/R2，记录历史增长的用量变化 |
| R4 | Foundation / 3 | 12/8/10；3/2/3 | 35 | 同三类与知识组，更明确的提示和较少组合步骤 |
| R5 | Challenge / 3 | 12/8/10；3/2/3 | 45 | 参数/条件论证与组合加深，保持已确认来源政策 |
| R6 | Exam-standard / 4 | 10/10/10/10；3/2/3/2 | 55 | Q1 K2/K7；Q2 K5；Q3 K3/K4/K8；Q4 K6 |

K1 定义与可导；K2 求导规则/高阶；K3 极值；K4 应用；K5 Rolle/MVT；K6 L’Hôpital；K7 隐函数；K8 单调性。K 标签只作为此验收的材料映射，不进入通用产品常量。

R1–R3 共用确认课程与蓝图，分别冻结实际历史；已有成功大题不得直接复用为“新练习”。R4–R6 各自确认蓝图。旧网页四大题/60 分结果保留为历史参考，不替换本矩阵，也不充当其中一次运行。

当前计划限额按已实现范围冻结核对：每次生成最多 16 次模型调用、900 秒、一次修复；输入 60k；生成/修复 20k 输出与 300 秒，其他必要阶段 12k/240 秒；独立导出 120 秒、每文件最多一次自动重试。规划、分析/转写及计数请求单独登记，不能误以为六次验收仅会产生 6 个请求。执行前以当次预检实际值为准，改变限额需新版本和相应授权。

### Task 12.2：执行并逐题审阅六次

**依赖**：Task 11 通过；12.1 manifest/rubric、课程及结构确认、真实输入授权已冻结。
**文件**：使用 12.1 工具，更新 docs/batch-6-validation.md；实际输出只入 var。

- [ ] 顺序运行 R1–R6，每次先审阅精确预检与授权，登记开始状态；不并行启动不同实验来掩盖资源竞争。
- [ ] 用正常 Generate 流程生成；成功后由验收操作者显式执行 Generate PDFs，记录该操作时间，不改变产品的主动导出 UX。
- [ ] 逐题核对条件、方法、结论、评分、来源支持、范围边际解释、重复及盲解/数学检查覆盖。
- [ ] 核查网页与同版两个 PDF；所有页转图查公式、表格/图形、跨页与答案隔离。
- [ ] 记录首次失败、修复前后、可选未检查、未知情况、是否拆分；补测命名 Rn-retest-01 并保留原记录。

**拟命令**：.venv/Scripts/python.exe evals/round1/run.py --manifest evals/round1/manifest.yaml --run R1 --execute --grant-ref <reviewed-reference>；其余按对应 run 单独执行。这只是拟接口，不声称命令已经存在或跑通。
**完成条件**：六个原计划位置都有完整记录；有未解决严重内容错误则相应验收未通过。只有六次均成功才有六份完整结果和 12 个 PDF，不能用 fixture/旧样本补数。

## 4. E1：新增一个 Topic 的完整流程验证

**用途**：验证新内容、新草稿路径与课程数据驱动能力；不是跨科目全面支持证明，也不是跨 Topic 混合卷。
**配置建议**：一个非 Topic 2、材料和现有题型/核验能力相适配的新 Topic，Exam-standard、2 大题；具体知识、题型、分值、小问数与时长由该章依据和蓝图确认，不沿用 Topic 2 的 K1–K8 或固定结构。

### Task 12.3：新 Topic 从材料到双 PDF

- [ ] 先只读核对现有材料，选定一个合适 Topic；记录选择理由、能力边界和精确物理页，不把缺全课材料/当前期末公告当统一启动门槛。
- [ ] 创建独立验收 Course 与 Topic；经正常上传/关联进入解析，可复用相同文件 hash 的解析结果，记录缓存命中；课程理解必须新产生。
- [ ] 从 UI 选择该 Topic 的必要页进入分析预检，取得该用途/页段/页图的授权。模型提出必要澄清时在产品内保存答案及来源，更新草稿；没有真实缺口时不人为制造付费轮次。
- [ ] 验证草稿与材料属于新 Topic，不含 Topic 2 固定目标；编辑保存、确认当前 Topic，规划并确认 2 大题结构。
- [ ] 真实生成与核验，主动打开答案及导出两个 PDF；刷新/重新登录能找回。全链所有任务分别关联至 E1。
- [ ] 逐题复核和全页 PDF 检查；列出当前能力缺口。若所选 Topic 需要新检查器/题型，先报告 unsupported，不把另一科目能力包开发隐含塞进本批。

**完成条件**：从新材料到新确认版本、题答和双 PDF 的真实证据齐全；若遇能力阻塞，保留明确 E1 未通过/未执行状态，不能凭六次 Topic 2 成功宣称新 Topic 可用。E1 费用与时长单独统计。原有主课程及 Topic 2 成果不受影响。

## 5. 质量口径、时间与启动条件

建议 rubric：
- 确定性结构、题答对应、锁定题数/分值要求 100%；必要检查全部通过。
- 每个作答单元记录 correct / minor_issue / major_issue / cannot_judge；无未解决严重错误才可判该卷内容通过；minor_issue 有依据地登记。
- cannot_judge / not_checked 不计正确；全部适用核心项的复核覆盖单列。主观难度/风格与原创性评语不当作模型自评分金标，具体阈值/评审人运行前冻结。
- 学术来源支撑主要知识点；少量合理扩展记录理由。背景来源不限课程范围，但未经核实不得称事实已证实。
- 上传来源和个人历史的重复命中分别统计；同一题多次命中不重复计入分子。
- 评测审阅不增加产品里的“用户必须批卷才可生成成功”步骤。

时间字段：analysis首次响应/澄清后系统时间/用户等待；planning 单列；generation 从受理到题答保存，含队列与自动重试；export 从显式受理到双文件有效；题答与导出之间用户等待单列；完整系统耗时含两阶段系统处理，用户等待剔除但不删除 PDF/排队时间。并行阶段用墙钟区间，不把模型耗时简单相加。

正式真实调用前集中确认：具体课程/Topic/材料及必要历史输入范围、manifest/rubric/评审人、模型与限额版本和可用账户条件。本次计划不是新 API 授权。优先复用近期有效的接入验证证据；如需要新的鉴权/schema 验证，独立登记并纳入授权，不重复为“连接测试”发送课程资料。

### Task 12.4：汇总与第一轮退出

**文件**：更新 docs/batch-6-validation.md、docs/round-1-validation.md、README.md、docs/handoff.md；原始记录 var/evals/round1/。
- [ ] 生成质量、功能、恢复、性能、token/费用、知识覆盖六个独立结论；R1–R6/E1/故障 fixture/额外补测分开。
- [ ] 报告完整结果分布和每个原位置；性能超 120 秒记未达标，不通过平均值或删失败美化。
- [ ] 列出尚未实现的全部 MVP 范围，包括跨 Topic 混合卷 U4、完整模拟卷、多学科/格式/线上；第一轮结论不扩展成完整产品验收。
- [ ] 在主线完成稳定提交与推送；保存可操作链接、两类 PDF、来源与版本、真实启动说明。未完成项继续保留 handoff。

**完成条件**：首轮范围内严重问题均处理或明确未通过；每一结论能回到真实记录。性能缺口可作为后续优化项继续迭代，不能声称已满足正式发布全部要求。E1 是否通过单列；未完成 E1 则新增 Topic 验收未完成。

## 6. 本次计划自审

已检查：六次保留为 Topic 2、E1 额外；U1–U3 与第二轮 U4 的能力边界；新材料不借用旧理解；旧契约/hash 不改；主动 PDF 计时；失败和额外调用不遗漏。文件和命令均标拟实施，没有运行开发测试或模型。
