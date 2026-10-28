# Codex → Claude Code 交接

更新：2026-10-28 23:26，Asia/Shanghai。**当前代码基线为 84ac319；本次仅完成交接文档和只读状态核查，没有开发、模型重跑或服务重启。** 以本文为最新状态，历史明细见 [第四批验证记录](batch-4-validation.md)。

## 1. 工作区与接手步骤

唯一活动仓库：C:/Users/Yijia/dev/past_paper_generator。main 分支，origin 为既有 GitHub 私有仓库。C:/Users/Yijia/OneDrive/past_paper_generator 已停用，不在旧副本修改。

在活动仓库内按 AGENTS.md：

    git status
    git pull --ff-only
    git log --oneline -10

然后读 AGENTS.md、README「当前实现」、本文，以及：
- docs/round-1-design.md
- docs/superpowers/plans/2026-10-19-round-1-qm.md（六批次、12 个任务）
- docs/superpowers/plans/2026-10-24-batch-4-question-generation.md
- docs/superpowers/plans/2026-10-28-source-reference-policy.md
- docs/round-1-optimization-backlog.md

本次交接后 Codex 停止修改，由 Claude Code 单独接手。原材料、历史原型、用户课程配置、历史任务和不可变候选均应保留。

## 2. 目前完成与用户最新决定

批次 1–4 / Task 1–8 的本地功能已实现：材料/证据、课程分析与确认、组卷蓝图与结构确认、题答、数学/盲解/语义核验和一轮定向修复。**尚无通过全部门槛的完整真实题卷。** 第五批 Paper/双 PDF/结果保存及第六批六次真实验收尚未实施，暂不进入第二轮。

最近功能提交 84ac319 实现 generation-v3 / source-policy-v1：
- evidence_ids 是学术/教学依据，支撑题目主要知识点；不再因超出本题原白名单直接中断。
- background_references 是独立背景参考，可来自其他课程资料、通用情境或外部参考，不限课程白名单；不能自动成为官方事实或课程范围依据。
- 小幅相邻知识扩展可以接受，由 source_alignment 判断实际知识和方法是否仍服务于主要目标；不设未经确认的“允许超纲百分比”。
- 额外、背景或未解析的引用保留为非阻断提示；核心依据缺失、实质偏离等才进入必需检查和单题修复，最多一轮。
- 数学、盲解、原创性等必需门槛不变；失败、未检查、无法判断不能冒充通过。
- 页面来源分组，未知 ID 不生成坏链接。背景详细说明随 Show answers 打开；已知来源仍定位固定版本和物理页。
- 策略/schema/提示词绑定 context hash。旧结果不改写，修改上下文不能冒充同一个验证版本。

用户将速度/用量优化、专项真实语义/原创性校准及修复效果验证后置到第一轮完整流程跑完后。见优化清单；不要误读为允许省略每次生成的必需检查。

## 3. 最新真实任务：已到语义核验输入准入，但超出限额

这是用户在网页自行新提交的运行，不能继续沿用此前“generation-v3 尚未真实运行”的旧描述。

| 项目 | 当前实测 |
|---|---|
| Task | 32bb6d9c-2121-4f4a-9a6a-b89c585b7b32 |
| 页面 | http://127.0.0.1:5173/tasks/32bb6d9c-2121-4f4a-9a6a-b89c585b7b32 |
| 课程 | 68caa35d-6e08-42d7-84bd-70a23e369b1f；已确认 version 2 |
| 冻结快照 | 68a09ab1-6059-4b59-a4af-6d3b880f1b2d；4 大题、15 小问、60 分 |
| pipeline / 模型 | generation-v3；gpt-6.1-sol；官方 Responses API，store:false |
| context hash | 79117bb6541823bb75df986888e89fceb54968f6dc5aaf481d55be0428c1f954 |
| 时间 | 2026-10-28 23:12:33–23:17:13；提交至结束 280.398 秒 |
| 终态 | failed / TOKEN_BUDGET_EXCEEDED |
| 直接原因 | count:r0:semantic 官方计数 67,531 tokens，超过项目冻结上限 60,000 |
| 已发生调用 | 8 次模型调用 + 9 次计数，全部 completed；8 个模型结果 parsed / complete |
| 用量 | 输入 94,099；输出 41,424；合计 135,523 tokens；未查询账单 |

已保留：
- 四道题的 r0:pair 与 validated:r0:pair 成果。
- 完整 CandidateVersion revision 1：b255c962-b0fa-43c8-bace-fe53c6ecf6e6；payload hash 校验通过。
- 四次 blind:* 盲解成果。
- Q3 有 1 条独立 background_reference；这次没有复现 PAIR_SOURCE_INVALID。
- task.result 为 {}；候选仍能由 generation-content 接口读取。

未完成或不能声称通过：
- **语义模型请求没有发送**；只有它的输入计数请求执行了。页面错误中“No analysis request was sent”仅指该阶段，不表示前面 8 次模型调用未发生。
- CheckReport 尚不存在，来源范围/原创性/盲解一致性等最终判定未形成；未进入修复、发布或 PDF。
- 程序/数学阶段已执行，但当前实现直到语义返回后才 save_report，本任务没有持久化它们的完整检查列表；不能把阶段经过当作检查全部通过。
- 本次不是 API 额度不足、网络超时、输出截断或服务端模型上下文限制的证据；是应用自身 60k 输入准入上限被触发。

交接证据（本机忽略目录，不进 Git）：var/handoff-2026-10-28-latest-task.json。只读核对任务/调用/候选哈希，没有更改任务或新建授权、调用。

## 4. 下一步建议与代码入口

下一项应先评估语义核验聚合输入为什么达到 67,531 tokens，选择满足现有输入限额并保留必需检查的组织方式。这是阻断完整流程的问题；本次没有实施，也没有静默提高限额。

优先入口：
- backend/app/generation/reviewer.py：review_semantics 拼接 candidate/course/local_checks/blind_solutions/duplicate_comparison/source_review；save_report 在语义调用之后。
- backend/app/generation/source_policy.py：背景/学术分类、来源提示和有界证据摘录（每源1200字符，明确截断）。
- backend/app/generation/runtime.py 与 backend/app/ai/invocations.py：阶段持久化、官方计数、调用预算/未知结果处理。
- backend/app/generation/generator.py：成对成果复用，仅当前任务或直接父任务、相同 input_hash；完整候选保存。
- backend/app/generation/repair.py：保留原候选、只修复阻断目标、最多一轮。
- backend/app/generation/execution_context.py：预检、冻结策略、授权和版本绑定。

可先独立做本地输入构成分析、单元/模拟测试；确定改动范围后再按用户后续指令实施。若拆分语义检查，需要保留整卷重复/结构等跨题判断，重新评估调用总数和600秒任务上限。不要盲目重跑全部生成，也不要跳过检查以推进发布。新上下文不能强行复用旧 hash 或付费授权；当前历史候选/盲解可作为分析证据，能否跨版本复用必须显式校验。

在用户安排下再进入批次5 Task 9（阅读/历史）、Task 10（两个PDF/唯一发布/恢复）及批次6 Task 11–12。交接本身没有授权自动启动新一轮真实模型任务。

## 5. 验证基线与服务

最近实际代码验证（2026-10-28，84ac319）：
- 后端207 passed（218.08秒），前端16 passed。
- 类型检查、生产构建、Django check、迁移一致性、OpenAPI及生成类型通过。
- Playwright 7组通过：来源分组、固定物理页/刷新、答案/背景主动打开、390px、旧结果兼容；0 JS错误。
- 这些测试在上次开发阶段运行。本次交接只核查状态与文档，不重复声称跑过全量测试。

2026-10-28 23:25:59 检查：
- Web/API/worker/dispatcher 均为本仓库活动进程。
- 前端5173、API8000及前端代理 session GET 均200。
- PostgreSQL54330可读；0 queued/processing业务任务。
- 没有重启、停止服务，保留运行供接手。必要时复用：

    & .\.venv\Scripts\python.exe .\scripts\local.py start

实际数据目录 var/postgres-20261023/；var/postgres/ 是旧保留副本。材料与解析 var/data/，离线模型 var/models/，日志 var/logs/。环境文件、var/与原材料未提交；同机接手可直接使用，不能认为 git clone 自带这些数据。不要输出 .env.local 或 var/local.json 的密钥/口令。

## 6. 历史证据与工具注意事项

| Task | 结果 |
|---|---|
| 344da144-1127-46b2-b137-4707f98a6a04 | 首次真实完整候选保留，原检查未放行、修复 needs_info；历史不改 |
| bda61a74-c5e9-4639-adc3-08b4d35655b5 | Q1输出截断；仅Q2完整保留；无完整候选 |
| 9033ae45-be67-4136-a67c-4ac3589181c1 | 用户取消；两次模型请求仍为started，远端结果与用量未知，不按零费用处理 |
| 8f2e167c-6d30-4dcf-9bcb-70caacd7c59e | Q3额外背景引用触发旧规则；四题新策略离线结构通过，原失败保留 |
| 00dd1359-f7ae-4907-b48f-cf6de8a224ff | 独立 B4-SOURCE-FIXTURE 合成演示，0模型调用，不是实测题卷 |

脚本：
- scripts/audit_source_policy.py <terminal-task-id>：读取原始题答，按当前代码在内存中检查结构/来源，写var报告；不调用模型，不改原任务，不做数学或语义核验。
- scripts/audit_generation_task.py：目前要求 candidate.check_report 存在，**不能直接用于最新无报告任务**；不要把该脚本异常误判为数据库损坏。
- scripts/test_retained_generation.py：针对首个历史任务的固定断言，不是最新任务通用测试。
- scripts/prepare_source_policy_fixture.py：会新建独立合成课程/任务；scripts/test_source_policy_view.py 读取已保存fixture检查UI。
- 原API授权是按用途/范围/版本及明确运行提交处理；密钥存在、历史Grant或本次交接不代表无限付费重试。

已知未解决：最新语义输入准入阻塞、阶段检查结果在语义前失败时的持久化不足、历史输出截断具体原因未保存、部分符号检查覆盖、两分钟完整出卷目标、真实专项质量校准、两个PDF和六次验收。不要将合成通过或部分真实调用成功写成完整验收成功。
