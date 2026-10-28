# 第四批实施与验证记录

日期：2026-10-25（Asia/Shanghai）。范围：首轮 Task 7–8，AI③ 成对题答与素材、AI④ 分层核验和一轮定向修复，以及 Task detail 的候选预览。依据：[批次四计划](superpowers/plans/2026-10-24-batch-4-question-generation.md)。

## 结论与边界

本地实现已完成，核心回归和浏览器完整流程通过。真实 QM 的出题与核验尚未调用，GenerationGrant 与真实 generation 任务均为 0。前批分析、规划的授权不能跨用途用于本次出题。真实运行一次仍是本批剩余验收条件，必须先取得精确 scope / context hash 授权。

服务与开发使用 `C:\Users\Yijia\dev\past_paper_generator`。原 OneDrive 副本未编辑；原材料、历史原型与前批真实结果保留。只读核对真实课程 11 个 MaterialVersion 的存储 blob，SHA-256 全部匹配；这项检查不等同于重算全目录所有原始路径。未新增依赖。Papers 发布和两个 PDF 属于批次五，六次真实验收属于批次六，本批未执行。

## 实际完成

| 领域 | 文件、行为与边界 |
|---|---|
| 冻结与授权 | `generation/execution_context.py`；合并 Generate practice 入口，冻结/复用已确认快照；独立 GenerationGrant 绑定输入、提示词和 schema hash，重查配置/结构绑定、课程忙碌与密钥存在性。预检不调用模型 |
| 不可变记录 | `generation/models.py`、迁移 0003/0004；GenerationGrant、GenerationArtifact、CandidateVersion、CheckReport；模型及数据库拒绝 UPDATE，task+revision/key 唯一；原候选保留 |
| AI③ | `content_schemas.py`、`content_validation.py`、`generator.py`、`ai/prompts/question_pairs.md`；按大题生成成对题答、最多两个并行，校验题号、知识、题型、分值、答案完整性、替代评分组、来源和素材 |
| 素材 | `expressions.py`、`assets.py`；受限算式树、固定变量和运算，限制深度、规模、数值及组合幂；不执行模型代码；服务端绘制 SVG，标签转义；网页数学用 KaTeX，关闭信任 HTML |
| 持久执行 | `runtime.py`、`core/queue.py`、`core/management/commands/generate_practice_one.py`；沿用 outbox、epoch、heartbeat、取消、任务截止；保存原始及已验证大题组；同输入恢复/新尝试可复用完整验证组；未知请求不自动重放 |
| AI④ | `checks.py`、`math_checks.py`、`math_worker.py`、`reviewer.py`、`duplicates.py`；结构检查、SymPy、独立盲解、九类必需语义判断、限定材料检索及重复检查；门槛和 requiredness 由代码确定 |
| 盲解隔离 | 只给题干、小问、题目可见素材及课程方法/范围/偏好；不传生成答案、数学检查规格或仅答案使用的图形；逐小问比较结果后交语义核验判断 |
| 修复 | `repair.py`、`ai/prompts/repair.md`；根据阻塞项选受影响大题，最多一轮；生成 revision 2，保留父候选；未变盲解可复用，全部程序/数学和整卷语义/重复复核；预算不足或无合理修复时保留失败 |
| 页面与 API | `generation/content_api.py`、`CandidatePreview.tsx`、`ContentBlocks.tsx`、`TaskPage.tsx`；默认题卷投影不含答案/原始模型输出；显式 Show answers 才请求答案和详细报告；历史候选、固定来源、恢复及错误可见 |
| 状态准确性 | 任务结束会再次读取最终候选报告，避免终态仍显示“检查中”；没有完整报告的终止任务如实显示未完成。任务侧栏按实际 course_id 显示课程 |
| 构建 | 数学阅读器按需加载；主 JS 443.98 kB，候选阅读器约 268.59 kB（压缩前），本次构建无大于 500 kB 的主块警告；不据此宣称用户侧加载性能达标 |

接口以 `/api/v1` 为前缀：

- `POST /courses/{course_id}/generation-preflight`：当前绑定、冻结输入、精确范围。
- `POST /courses/{course_id}/generations`：稳定幂等 key、范围 hash、独立授权；返回持久任务。
- `GET /tasks/{task_id}/generation-content`：所有候选的题目、可见素材、来源和不透露答案的检查摘要。
- `GET /tasks/{task_id}/generation-content/{candidate_id}/answers`：显式打开答案、详细报告、已保存模型输出。
- 通用 Task GET 对 generation 隐去答案-bearing model payload；归属校验、CSRF 和任务取消沿用原机制。

## 真实调用契约

以下为本批调用契约；2026-10-25 已执行一次，实际失败结果与后续修复见文末：

- 官方 OpenAI Responses API，模型读取现有 `OPENAI_MODEL`（当前预检为 `gpt-6.1-sol`），`store:false`，SDK 自动重试为 0。
- 最多 16 次生成/盲解/语义/修复调用，单次 240 秒、整个任务 600 秒、最多两个并发、修复一轮。每次新调用前有官方 input-token count 请求；输入 60k、输出 12k token 上限。
- 发出前核验固定原始 blob、解析内容和转写内容 hash。新页图为 0；只使用所列页的文字/已保存转写及派生上下文。
- 返回 needs_info、无法判断、拒答、截断或调用失败均保留真实状态；未知结果须人工复核后新尝试，不自动重放。
- 首轮没有可引用的官方细分 rubric，`marking_basis=suggested`。
- 任一必需项非 pass 均不放行；检查通过也只表示当前候选满足已执行门槛，不是数学正确性的认证。

精确预检保存在本地忽略目录：

- `var/batch4-generation-preflight.md`：名称、物理页、材料版本及每题来源。
- `var/batch4-generation-preflight.json`：完整固定输入和内容 hash。
- context hash：`9992277e6ca50e4556da7587f075afadd2ca869c97348af46e19957374b9e294`。
- 真实快照 `7e2a758e-7e7e-4a03-b618-e7c12d56b708`，3 大题、13 小问、60 分，建议时长 95 分钟。
- 30 页来源：M05 mock p1,3,5；M06 additional questions and answers p2,6；M34 Lecture 2 p14,28–33,41,46–49；M35 Lecture summary p4–6,8–10,13,14,17；M48 seminar p19–22。
- 其中 9 页进入材料重复比较；历史生成卷集合为空。检索只覆盖固定集合，不能证明对全世界所有题目均不重复。
- 还包含确认课程、蓝图、配置、方法、问题项、用户声明/偏好，以及候选题答、盲解、检查报告与检索片段。完整输入以 JSON 为准。

## 实际检查

以下命令已执行，不是拟实施命令。后端全量检查之后进行了针对修复范围的回归，没有把重叠用例数量相加为独立覆盖数。

| 检查 | 结果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests -q` | 179 passed，523.44 秒；当时完整代码集 |
| 预检 / execution / question_pairs 定向回归 | 21 passed，155.28 秒；覆盖新增独立授权、未知调用、不可变 UPDATE、嵌套幂限制 |
| 符号启动修复后 checks / execution / repair 回归 | 23 passed，138.57 秒；包含真正的子进程超时终止与复用断言、答案图形隔离 |
| `node node_modules/vitest/vitest.mjs run`（frontend 目录） | 15 passed，包含显式答案请求、答案网络错误保留题目、任务终态轮询竞争 |
| `node node_modules/typescript/bin/tsc -p tsconfig.json --noEmit --incremental false` | 通过 |
| `node node_modules/vite/bin/vite.js build` | 通过；最后构建日志 `var/batch4-frontend-build.log` |
| `backend/manage.py check` | 无问题 |
| `backend/manage.py makemigrations --check --dry-run` | No changes detected |
| OpenAPI 与前端类型 | 已生成，且通过类型检查 |
| `git diff --check` | 通过；只有仓库行尾转换提示 |
| Git 忽略核对 | `.env.local`、`var/`、原始 `Quantitaive methods/` 被忽略 |

有意义的断言还覆盖缺答案、重复小问/评分、分值不匹配、非法素材、取消后拒绝写回、缺语义项不能放行、洛必达错误步骤、根号定义域、有界优化端点、只改数字的重复题、一轮修复上限和跨用户拒绝。测试删除真实 API key，并阻止未 mock 的官方 HTTPTransport 请求；真实课程材料没有用于测试外发。

## 调试中发现与修复

- 浏览器丢失提交响应后，刷新须恢复同一幂等请求与 task_id；已纳入验收脚本。
- 任务与内容分别轮询导致最终报告可能漏读；已用终态查询身份重新取最终报告，单元测试覆盖。
- 原 8 秒子进程限额包含 Python/SymPy 冷启动：繁忙时曾造成 fixture 任务的 9 项数学检查均为 not_checked，正确阻止放行；另一次定向测试出现 1 failed / 6 passed。未删除失败任务或放宽通过标准。
- 现将启动上限单列 20 秒；启动后每个计算仍限 8 秒，同一轮检查复用进程。计算超时会杀死进程，记 not_checked；下一项用新进程；整任务 600 秒上限保持。最终 23 项相关回归通过。
- 早期浏览器脚本有登录导航时序和来源面板名称不匹配，已改为实际页面断言。开发期间一次同时开启两个 pytest 导致测试库建库冲突，已改为串行，开发库未受影响。

## 尚未证明

截至本地初验时尚未做真实 AI③/④；其后首次真实失败结果见文末。实际费用、教师级审阅、难度校准或两分钟完整出卷仍未验证。受限检查器主要支持单变量求导、等式、值、极限、驻点、有界优化及明确可判定的洛必达检查；超出范围保留 not_checked / inconclusive。复杂证明依赖语义判断，不能冒充符号证明。固定历史比较集合为空、有限材料检索和合成判断均是明确限制。


## 最终浏览器验收与查看

- 课程：`fc14a93b-f943-437b-9549-a83cfe51e94f`（B4-FIXTURE，合成数据）。
- 结果：[82ff0ea5-7399-42e0-8af2-d5b279d4d393](http://127.0.0.1:5173/tasks/82ff0ea5-7399-42e0-8af2-d5b279d4d393)。
- 任务实际状态：succeeded；提交至完成 41.52 秒，其中执行 39.88 秒；模型调用 0 次。**这些是合成流程耗时，不是真实模型性能证据。**
- 报告：必需项 43，通过 43，门槛 allowed=True。语义与盲解判断来自合成适配器。
- `scripts/test_generation_content.py` 8组断言通过：入口、丢失响应后恢复同一任务、实际worker成功/刷新、主动获取答案/KaTeX、隐藏和重载不预取答案、固定版本来源、390px无整页横溢、无未捕获JS错误。
- 记录：`var/batch4-browser-check.json`、`var/batch4-fixture-outcome.json`；桌面题卷/答案和手机截图已保存并检查。
- 服务启动复核：`scripts/local.py start` 返回 http://127.0.0.1:5173，复用本项目进程。内置浏览器与预检文件的 open_in_codex 返回 queued，未把该返回值声称为用户已经看到页面。

## 2026-10-25 首次真实运行及 2026-10-26 排错

用户明确允许原 hash `9992277e…` 范围运行一次。前一个提交命令被中断；恢复核查发现没有 generation 任务、GenerationGrant 或调用记录，因此按同一幂等 key `batch4-live-once-approved-20261025-9992277e` 提交。只创建了一个真实任务：`344da144-1127-46b2-b137-4707f98a6a04`。本节取代前文“尚未真实运行”的时间点状态，不改写原报告。

| 实测项目 | 结果 |
|---|---|
| 任务终态 | failed，GENERATION_NEEDS_INFO；模型在修复时表示缺少检查诊断/比较证据，未生成修复版本 |
| 已保存成果 | 3 大题、13 小问、60 分的成对题答；候选 `9b0a79ba-6fca-45aa-81e6-ceb7fbbb1a4d` revision 1；报告 `1e635cb0-5182-4a2e-8699-0fc78db3c518` |
| 实际调用 | 3 次生成 + 3 次盲解 + 1 次语义审阅 + 2 次修复 = 9 次；另 9 次官方输入 token 计数。全部 completed，模型响应全部 parsed；没有超时/未知远端结果 |
| 用量 | 输入 164,364；输出 38,472；总计 202,836 tokens。缓存输入 5,666、reasoning 3,666 属于对应总量中的子项，不再次相加。未查询实际账单 |
| 耗时 | 提交到终态 385.842 秒，执行 385.064 秒；超过 120 秒目标，未含 PDF |
| 原报告 | 必需 54、pass 15、not_checked 39，门槛 allowed=false；没有发布 Paper |
| 原调用与状态 | 保留原 Task、ModelInvocation、CandidateVersion、CheckReport；离线回放不更新这些历史记录 |

问题来源与修复：

1. JSON schema 允许的数字字符串、无穷区间及多项 AST 与解码器不一致：分数、inf/-inf、3–4 项加乘导致 12 项数学检查未执行。现支持有界分数和 2–4 项加乘，无穷只在区间/极限位置使用。保留深度、节点、组合幂、数值大小、子进程时限；不用 eval 或自由文本表达式求值。
2. 全道长题与页面字符串的相似度阈值把 9 页比较池全部筛掉，原报告 local_duplicates 仍错误显示 pass。现按题干和小问的词项/数学符号有界排序，每题返回最多 6 个真实片段，不因低分变成空集合；有比较页却无可用正文时明确 not_checked 并阻断。检索不是原创性证明。
3. 修复请求缺少实际检查诊断、检查器契约、已检索比较片段，并把要求应用重新执行检查的指令交给模型。现传入诊断与片段，修复目标按大题缩小，说明应用负责重新执行；有实质重复时在原结构和知识目标内重写问题/完整答案，不能只换数字。
4. 修复环节的 needs_info 异常原被当作普通 failed，result 没有候选/报告入口。未来任务现在保存 needs_info 及原候选、报告 ID，仍 allowed=false；本次历史 failed 未改写。
5. 用量汇总误把 input-token count 的未知 usage 算进模型总量。现排除计数记录，同时保留真实模型未知用量为 unknown，不填零；旧任务的正确总量由逐条原记录离线汇总得到。
6. 真实调用 key 含长 hash，使手机任务页溢出。现使任务正文可断行、时间线子项可收缩；不隐藏诊断。
7. 检查器契约加入冻结 context，pipeline generation-v2；变化后的上下文不能使用旧授权。语义提示词明确“完整判断报告”不代表“题目通过”，所有必需非 pass 仍被代码门槛阻断。

测试先复现失败：初次新增 5 项回归全部失败；修复后一次相关检查为 30 passed / 3 failed，后者发现旧合成材料缺正文、以及过度依赖检查排序的断言。补齐明确的合成正文，并独立测试空来源必须阻断，未绕过门槛。最终验证：

| 实际命令或检查 | 结果 |
|---|---|
| live_regressions / model_persistence / checks / repair / execution / question_pairs / preflight 定向 pytest | 47 passed，95.48 秒 |
| `.venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests -q` | 195 passed，139.79 秒；与定向结果重叠 |
| 前端 Vitest / TypeScript / Vite build | 15 passed / 通过 / 通过；本次样式修复后运行 |
| Django check / makemigrations --check --dry-run | 无问题 / No changes detected |
| `scripts/audit_generation_task.py 344da144-1127-46b2-b137-4707f98a6a04` | 本地回放，无模型调用、不改历史；结果见下 |
| `scripts/test_retained_generation.py 344da144-1127-46b2-b137-4707f98a6a04` | 5 组只读浏览器断言通过：真实题卷、主动答案/原报告、刷新、来源、手机与无 JS 错误；读取期间调用记录未增加 |
| 新建合成课程后 `scripts/test_generation_content.py` | generation-v2 完整 API/worker/页面 8 组断言通过；新任务 f252278c-ac9c-417e-bcce-3f0a6baa9811；0 模型调用 |

离线回放仅覆盖程序/数学与检索：必需 23，21 pass、1 not_checked、1 inconclusive。原先 12 项格式不匹配中 10 项现通过；q1-d 全域绝对值可微性和 q1-e 隐式关系定义域仍不能由当前检查器完整判定，不得豁免。9 页比较池实际返回来自 8 页的 9 个去重片段，各大题关联 6 个片段；没有精确数字替换命中，但**尚未重新进行语义原创性判断**。原修复模型指出 q2 找错题可能重复 seminar 的解题路径，这是待核验的模型判断，不是程序已证明重复或已排除重复。

执行工具抽查（Codex）：本地阅读三道题的推导、极限适用条件、优化端点及评分配对；对照 M35 物理页 13、14、17 和 M34 物理页 41 的原页图核对相关方法/限定。抽查不替代语义复核、教师审阅、难度校准或完整正确性认证；页图未发送到新外部服务。详细问题文本保留在本地候选中。

可查看真实失败结果：[任务页面](http://127.0.0.1:5173/tasks/344da144-1127-46b2-b137-4707f98a6a04)，点击 Show answers 后才获取答案及详细报告。服务已运行，API 已加载修复。桌面答案截图及手机截图已查看，长标识溢出已消除。合成成功任务为 [generation-v2 fixture](http://127.0.0.1:5173/tasks/f252278c-ac9c-417e-bcce-3f0a6baa9811)，不能当成真实题答质量证明。

## 后续真实验证预检

修复后的真实模型路径尚未运行。原授权明确为“一次”，已消耗于上述完整失败尝试。新预检保存为 `var/batch4-generation-preflight-v2.md` / `.json`，旧文件保持：

- hash：`2c01982cb2c17aab36141f4dee249e4a8a6a1f06fb4a872849c796fdcdd52114`。
- 冻结 input 与首任务结构完全相等：同一 course version 2、结构快照、30 页和已有转写；0 新页图。变化是检查器契约、pipeline 及修复/语义提示词。
- 同样官方 API、模型、store:false、16 次模型调用及相应计数上限、240 秒/次、600 秒/任务、一轮修复。没有新授权记录或真实任务。
- 再运行须取得对这一次新尝试的明确授权；不能把用户“常规开发继续”解释为无限付费运行。所有不受影响的代码、测试、页面和记录已完成。
- 此次未进入第五批，未生成两个 PDF，未做六次真实出卷验收；这些不应标记完成。

审计、预检全文、截图及原材料均位于被忽略的本地路径。账单、真实原创性与难度、修复后模型表现和完整出卷耗时仍未验证。


## 2026-10-28 修复版第二次真实运行：输出截断

用户明确允许按 `var/batch4-generation-preflight-v2.md` 再运行一次。接手时快进同步已是最新；当前代码与预检 JSON 完全匹配，hash 为 `2c01982cb2c17aab36141f4dee249e4a8a6a1f06fb4a872849c796fdcdd52114`。保留工作区已有的后续优化排期文档。没有修改提示词、程序、模型、材料范围或输出限额。

- 唯一任务：`bda61a74-c5e9-4639-adc3-08b4d35655b5`；幂等 key `batch4-live-v2-approved-20261028-2c01982c`。
- 上海时间 2026-10-28 02:22:50 提交，02:25:29 结束；提交至结束 **158.914 秒**，执行 **158.487 秒**。
- 终态 **failed / MODEL_INCOMPLETE**。第一题响应截断；第二题完整返回并通过题答配对/结构校验。没有完整 CandidateVersion 或 CheckReport。
- 总共 **2 次模型调用 + 2 次官方输入计数**，四条记录全部 completed，无结果未知的调用；没有自动重试。
- 真实用量：输入 **36,411**、输出 **20,870**、总计 **57,281 tokens**；reasoning 3,923、cached input 1,974 为其中子项。TaskAttempt 汇总与逐条调用相等，验证了此前计数请求污染用量汇总的修复。未查询账单。

| 调用 | 返回与耗时 | 输入 / 输出 / 总 tokens |
|---|---|---|
| r0:pair:q1 | truncated / MODEL_INCOMPLETE；145.781 秒 | 20,164 / 12,000 / 32,164 |
| r0:pair:q2 | parsed；106.578 秒；结构已校验 | 16,247 / 8,870 / 25,117 |

第一题输出恰好达到配置的 max_output_tokens=12000，且服务端返回 incomplete；这是输出预算耗尽的强证据。当前适配器没有保留 `incomplete_details.reason`，因此“由输出预算耗尽导致”记录为推断，不伪称已取得明确的服务端原因。没有网络超时、额度不足或限流的记录。不能把这次失败归因于数学或原创性判断，它们尚未运行。

第三题生成、整卷组装、数学检查、独立盲解、语义/原创性判断、一轮修复、发布和 PDF **均未执行**。两分钟目标仍未达到；此次提前失败，与前次完成更多阶段的 385.842 秒不可直接作优化前后比较。前次两项检查能力缺口没有得到新证据，也没有被豁免。

第二题作为不可变 GenerationArtifact 保留：`r0:pair:q2` 与 `validated:r0:pair:q2`。已核对已验证成果的 payload hash，并导出本地题目/答案分离的 Markdown：

- `var/batch4-v2-partial/q2-questions.md`：只含第二题题干与四个小问，标为 partial / unverified。
- `var/batch4-v2-partial/q2-answers.md`：已保存的推导和建议评分；没有标为通过数学/语义检查或正式题卷。
- `var/batch4-live-v2-outcome.json`：状态、时间、用量、调用摘要、事实/推断及未执行阶段。
- `var/batch4-live-run-v2.json`：本次授权与提交回执。旧预检和旧任务保持。

只读 Playwright 实际完成 5 组断言：任务失败和四条调用显示准确；无完整候选、无答案预取；刷新与父任务关联；390px 最终页面无整页横溢；返回 Generate 不新建任务。检查过程中无 JS 错误、写请求或新增调用。记录为 `var/batch4-v2-browser-check.json`，截图为 `var/screenshots/batch4-v2-incomplete-*.png`。手机截图先等待候选区完成加载，未把加载中画面当作完成状态。

本次没有修改应用代码、安装依赖或迁移，因此未重跑全量后端/前端测试；2026-10-26 的 195/15 项结果仍是之前验证的日期，不计作本次新执行。核对了授权 hash、原调用已结束、当前无活动课程任务、已完成成果 hash、TaskAttempt 用量、真实失败页面和 Git 差异。

页面：[第二次真实任务](http://127.0.0.1:5173/tasks/bda61a74-c5e9-4639-adc3-08b4d35655b5)。网站保持运行；内置浏览器和题目文件打开请求返回 queued，实际页面已由 Playwright 验证。

此授权的一次运行已结束。下一步需处理单道大题负载与输出预算的匹配、补足截断诊断，再决定后续有界恢复；本次未增加 token 上限或追加付费尝试。后续专项速度/用量及质量优化继续按 [排期清单](round-1-optimization-backlog.md) 管理。未进入第五批或第六批。


## 2026-10-28 网页新失败与来源分层修复

用户最新自行提交的真实任务为 8f2e167c-6d30-4dcf-9bcb-70caacd7c59e，02:46:50–02:50:34（Asia/Shanghai），4 大题、15 小问、60 分。4 次模型调用与 4 次输入计数完成，4 个响应均 parsed。耗时 224.506 秒；输入 69,752、输出 33,582、合计 103,334 tokens。Q1/Q2/Q4 保存结构校验成果，Q3 原始响应保留；没有完整候选、数学/盲解/语义报告或修复。

直接错误 PAIR_SOURCE_INVALID：Q3 多引用了 M33《MSIN0180 Math Background for topic 2 11_01_2026.pdf》物理页 22 的 ID。它来自发送给模型的课程问题及用户偏好背景，确为真实记录，但未列入 Q3 的 6 个教学来源、也没有提供该页内容。根因是背景引用和每题学术依据的输入/校验契约不一致，而非本次额度或截断。此前任务 9033ae45 已取消，两次模型请求停在 started、用量未知；本次用量不包含它。

用户本次确认：背景参考不需要课程白名单限制；学术引用用于支撑考点，但允许少量边际扩展，不能一超出就中断。

实施：

- generation-v3 + source-policy-v1 冻结在 context；PairOutput 保留 evidence_ids 表示知识依据，新增 background_references（label、evidence_id/URL、note）。背景支持其他课程资料、一般情境或外部参考，未经核实不作为官方事实，不自动联网。
- question_input 明列 academic_source_ids，课程 issues/scope 移入 background_context；只增加冻结背景来源元数据目录，没有偷偷外发新页面正文/页图。
- 删除来源白名单的提前结构异常，保留重复、额外、背景、未解析 ID 原样作诊断。来源提示非必需放行项；必需 source_basis 检查至少存在已提供内容的依据，source_alignment 语义判断实际知识、主要目标和扩展是否合理。未提供数值化“允许超纲比例”。
- 相邻扩展可以有理由地通过；核心教学依据缺失或实质方法/主题偏离则保存候选和报告，进入既有最多一轮单题修复。数学/盲解/原创性等必需门槛不变。
- 单条语义引用提示不再使整卷所有判断无效；重复/缺失判断只影响对应题及类别。source_alignment 若声称 pass 却无任何已提供内容的引用，记 inconclusive。
- 来源与背景在页面分组；未知 ID 不生成失效链接，已知记录打开固定版本/物理页。背景全文在主动打开答案后加载，外部 URL 不自动抓取，只有 http/https 可作为链接。
- 旧 payload 只在读取/本地验证时补空背景列表，不改写不可变历史；新契约不可直接恢复旧 task/hash，不能沿用旧真实调用授权自动重跑。

实际验证：

- 首轮新用例复现 7 项失败后实施；中间暴露的测试素材遗漏图形资源与前端括号问题已修正。
- 来源/接口专项：13 passed（36.45 秒）。
- 完整后端：207 passed（218.08 秒）；前端：16 passed；tsc 与生产构建通过。
- Django check 0 issues；makemigrations --check --dry-run：No changes detected；OpenAPI 验证与前端生成类型同步成功。无依赖/数据库迁移。
- scripts/audit_source_policy.py 在内存中读取上述真实任务四组原始返回，使用新上下文验证：4/4 结构通过，Q3 多余 ID 分类 background_only，产生非阻断提示。前后 fingerprint 相同，历史任务/调用/成果未改变。报告 var/source-policy-audit-8f2e167c-6d30-4dcf-9bcb-70caacd7c59e.json。
- 该离线回放没有进行数学、盲解、语义、修复或发布，不能当作真实全卷通过。
- 新建独立 B4-SOURCE-FIXTURE，任务 00dd1359-f7ae-4907-b48f-cf6de8a224ff，模拟模型输出、实际本地生成/检查执行，0 模型调用。额外引用提示与两条背景参考保留，合成核验通过。
- Playwright 7 组断言通过：默认不请求答案、来源分组/无坏链接、固定物理页及刷新、背景主动打开/隐藏、390px 无横溢、旧候选兼容、原失败不改状态。0 JS 错误，登录后 0 写请求。记录 var/source-policy-browser-check.json，截图 var/screenshots/source-policy-*.png，已视觉核对。

运行：服务在 http://127.0.0.1:5173；API/worker 在无活动任务时重启以加载修复。内置浏览器打开演示请求返回 queued，实际 UI 由 Playwright 验证。

限制：新提示词与相邻扩展判定尚未跑真实模型；新语义输入使用已授权正文的有界摘要（每源 1200 字符，明确标记截断），若不足需如实 inconclusive。原输出截断问题、部分符号计算覆盖、两分钟目标、专项语义/原创性校准仍未解决。本次不增加 token/调用限额，不进入第五/六批，不执行额外付费尝试。


## 2026-10-28 23:26 交接核查：用户网页运行 generation-v3

本段是用户完成源码修复后自行在网页提交的真实运行。交接时仅只读核查，无新模型调用、代码修改、服务重启或全量测试；覆盖前文“v3尚未真实运行”的时间点描述。

- Task：32bb6d9c-2121-4f4a-9a6a-b89c585b7b32；父任务8f2e167c。课程68caa35d，课程确认version2，四大题/15小问/60分，快照68a09ab1。
- context hash：79117bb6541823bb75df986888e89fceb54968f6dc5aaf481d55be0428c1f954；generation-v3，gpt-6.1-sol，store:false。
- 时间：2026-10-28 23:12:33.503–23:17:13.901（Asia/Shanghai）；提交至结束280.397882秒，执行279.754596秒。
- 终态 failed / TOKEN_BUDGET_EXCEEDED；count:r0:semantic 保存的官方计数为67,531，超过应用冻结的60,000输入token上限。
- 8次模型调用（4题答+4盲解）均completed/parsed，payload.status均complete；另9次计数均完成。输入94,099、输出41,424、总计135,523 tokens，与TaskAttempt汇总一致，未查询账单。
- 四组题答原始及validated成果、四组blind成果保存。完整候选revision1：b255c962-b0fa-43c8-bace-fe53c6ecf6e6，payload hash已核对；Q3有1条独立背景引用，未再触发旧PAIR_SOURCE_INVALID。
- **没有发送语义模型请求**，仅发送该阶段的输入计数。错误文案“No analysis request was sent”不能解读为整个任务零调用。
- 程序/数学阶段已执行，但尚未save_report；无持久化完整CheckReport，不能断言数学检查通过。语义/原创性/来源范围最终判断未完成，未进入修复、发布或PDF；task.result为空但候选可读取。
- 此次是应用自身输入限额拒绝，不是API额度不足、网络失败、输出截断或模型服务端上下文窗口错误的证据。

本地证据 var/handoff-2026-10-28-latest-task.json，包含安全调用概要、用量、候选哈希核对、服务与活动任务数量，不含密钥，未提交Git。核查时Web/API/worker/dispatcher身份均符合本项目；前端5173、API8000及代理session均HTTP200；数据库可读，0活动业务任务；保留服务运行。

下一步建议在本地检查review_semantics聚合的candidate/course/local_checks/blind_solutions/duplicate_comparison/source_review体积，评估在已有预算内保留全部必需检查的调用组织方式。当前代码在语义完成后才保存检查报告，异常前的局部检查结果缺少持久化也需评估。本次仅交接，不执行修复或增加限额。速度/用量与专项质量优化的原后置排期保留；不能因此跳过必要检查。完整最新上下文见 docs/handoff.md。
