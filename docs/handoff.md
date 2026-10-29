# Codex 与 Claude Code 开发交接

更新：2026-10-29，Claude Code。**最新实现为 generation-v5**（提交 `e8632c0`、`5fbb3b2` 及之后的文档提交，以 `git log -1` 为准）。新的出卷预检已生成，**尚未授权、尚未运行**。详见[第四批记录](batch-4-validation.md)末节“generation-v5”。

## generation-v5 要点（用户决定，2026-10-29）

- 卷内题间重复：只有“题目相同且结论相同”才算重复。审阅只报告两项事实，由 `generation/originality_policy.py` 判定，检查项为必要项 `paper:intra_duplicates`。与课程原题、历年卷的比较保持原规则。
- 数学：`math_bounds.py` 用区间证明定义域；绝对值尖点分段；`MathCheckSpec.role` 区分 core 和 auxiliary（auxiliary 未判定时不阻塞但记录，判 fail 仍阻塞；旧规格按 core）。
- 拆分设计不改。下次真实运行若触发拆分，专门记录分组、调用次数、耗时和整卷检查结果。
- AGENTS.md 第 3 节：产品代码和提示词不写死课程或科目内容；既有内容按 OPT-03 移出。
- 评测样例 `backend/tests/fixtures/intra_paper_overlap_eval.json` 和 `scripts/eval_overlap_facts.py` 只做预检和评分，不发送请求；真实抽测需另行授权。

## 下一步

1. 已授权运行一次 generation-v5（任务 `e94322bf`）：Q4 生成输出达到 12,000 上限被截断。随后按用户决定实现了生成专用的 20k 输出 / 300 秒单次 / 900 秒总时限，以及跨任务复用已验证大题（`27a8d5a`）。新的出卷预检 `774d6c4a…` 已生成，**尚未授权**；授权前不发起付费调用。
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
