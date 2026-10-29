# Codex 与 Claude Code 开发交接

更新：2026-10-29，Asia/Shanghai。**最新实现为 generation-v4 核验改进；用户要求的三项修改已实现并通过最终完整回归。** 本次开始前基线为4d8e906，最新提交以git log -1为准；历史细节保留在 [第四批验证记录](batch-4-validation.md)。

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
- 后端测试阻断真实OpenAI传输；本次0新增真实模型/官方计数调用。

合成演示（课程a1d95d44，B4-REVIEW-FIXTURE，不代表模型质量）：
- 成功且可选跳过：http://127.0.0.1:5173/tasks/ba5ca16b-99e9-4b79-b8fa-4e5329dc11fc
- 必要核验中断、q1成果保留：http://127.0.0.1:5173/tasks/bec205be-1814-4606-a403-0cad78f8a5ef

本机证据：var/review-budget-fixture.json、var/review-budget-browser-check.json、var/screenshots/review-budget-*.png。
内置浏览器打开请求返回queued；实际页面可用性已由Playwright验证。

## 真实数据状态与离线回放

真实QM课程68caa35d-6e08-42d7-84bd-70a23e369b1f，已确认version2；当前四大题/15小问/60分快照68a09ab1-6059-4b59-a4af-6d3b880f1b2d。

最新真实生成仍为32bb6d9c-2121-4f4a-9a6a-b89c585b7b32，2026-10-28 23:12:33–23:17:13：
- 原generation-v3，gpt-6.1-sol，store:false；4题答+4盲解完成，9次计数。
- 语义输入67,531 > 应用60,000；没有语义模型请求、完整CheckReport、修复或发布。
- 原候选b255c962-b0fa-43c8-bace-fe53c6ecf6e6保留，原失败/调用记录不改。
- 原用量135,523 tokens、耗时280.398秒；不是本次新增调用。

本次scripts/audit_review_projection.py在只读事务中重建旧输入，hash一致；本地检查8项结构/引用、26项数学均通过，但未做新的盲解或语义判定。新输入从201,697字符降至174,982字符（13.25%）；单题74,293–82,804字符，整卷复核56,594字符。这些是字符，不是官方token计数，不能宣称新真实请求必定达标。

结果：var/review-projection-32bb6d9c-2121-4f4a-9a6a-b89c585b7b32.json。
复查命令：
    & .\.venv\Scripts\python.exe -X utf8 scripts/audit_review_projection.py 32bb6d9c-2121-4f4a-9a6a-b89c585b7b32

## 下一步与未验证事项

本次实现不等于generation-v4真实质量验收。下一次真实运行需从QM Generate的新精确预检明确提交：
http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/generate

密钥已配置、既有Grant或用户认可实现方案，不代表新增无限付费重试。没有获得本次新策略的独立真实运行提交，不自动发送。维持官方目的地、store:false和未知结果不自动重放。

后续应核查新版本实际token/分组/耗时、语义质量和一轮修复结果；不能把fixture通过当真实通过。不新增用户拒绝的专用核验恢复能力。

批次5（阅读/历史、两个PDF、唯一发布/恢复）及批次6（六次真实验收）尚未开发，本次没有进入。两分钟目标、专项质量校准、数学覆盖及早期输出截断诊断仍有后续工作。

历史记录：
- 344da144：第一次真实候选及未放行检查保留，修复needs_info。
- bda61a74：Q1输出截断；仅Q2完整保存。
- 9033ae45：用户取消，两次模型请求结果/用量未知，不按零费用处理或重放。
- 8f2e167c：旧引用白名单失败；原记录保留，之后已实现来源分层。
- 00dd1359：来源分层合成演示，0模型调用。

scripts/audit_generation_task.py仍要求完整check_report，不能用于原32bb无报告任务；使用本次audit_review_projection.py。测试/演示helper会新增独立fixture，不改真实课程。


## 最终运行状态

2026-10-29 18:10:46：web/api/worker/dispatcher均为本项目活动进程；5173前端、8000/API session、前端代理session均200。0活动业务任务，旧真实失败状态/候选hash保持，从旧任务结束后没有新ModelInvocation。服务保留运行，证据var/review-budget-final-status.json。需要操作时直接访问上述链接；本次没有关闭服务。
