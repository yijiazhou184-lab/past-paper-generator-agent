# AI Past Paper Generator

## 当前验收：E1 获准分析已完成，仍需课程草稿处理（2026-11-03）

用户已明确确认“使用标准数学定义，并注明资料差异”，并允许按 6dc34c33… 精确快照运行一次 E1 后续分析。该次调用已执行：task fd64ee51-0e51-44ce-9ff8-0f1ae39d9c31 返回 needs_info；API/解析正常，4 个知识节点为部分支持，没有 token 超限。官方计数 10,771；实际输入/输出 10,771 / 6,906，合计 17,677 tokens；模型 78.750 秒，系统墙钟 84.611 秒。新增 1 模型+1 计数，调用记录 207→209；没有自动重试。

获准输入仍包含旧的“Codex 临时、用户尚未确认”说明，模型据此重复提出惯例选择。这是确认信息与冻结输入未同步的问题，不应再次要求用户选择。未改写获准快照或历史响应；已通过正常澄清回答保存实际人类确认，明确取代临时说明，当前草稿 revision 4。该确认是练习偏好，不是官方事实。新精确预检 826fce3f… 仅本地准备、execution_authorized=false，未再次外发；本次一次分析的授权已使用。

E1 暂无 CourseVersion、规划、题答或 PDF。章节总节点、连续性、最值存在性、介值/不动点四项仍 partial；当前整章确认会阻塞全部 partial 节点，新澄清也触发重新分析。下一步应先处理确认信息同步，以及“章节总节点/个别不可读例题”与实际练习所需知识的区别，保留真实缺口，避免盲目重复付费调用；未实施范围放宽或绕过 gate。Lecture 1 物理 p38（印刷 39）已做本地页图核对，明确写在定义域上连续；未创建正式视觉转写记录、未发新页图。

R1 一次补测仍 failed（必要数学检查不支持根式点字符串）；R2 保持用户指定 skipped；R3–R6 未执行。本次仅运行真实分析及本地核对，没有新增产品代码/依赖/迁移，也未重跑全库或浏览器端到端。Django check 0 issues；web 和实际 API /api/v1/session 均 HTTP 200，0 活动任务。完整记录及前次代码测试见 [R1/E1 实测记录](docs/batch-6-r1-retest-e1-2026-11-03.md)。原材料、原结果和用户未跟踪文件保持。

## 当前局部更新：小问知识驱动覆盖汇总（2026-11-03）

模型只为每个小问填写实际考核的 knowledge_ids 和 focus；程序计算大题知识并集与整卷 coverage，不区分主考/辅助，不固定每大题的知识分配。新模型契约 planning-v3-part-coverage / 提示词 r1-planning-3-part-coverage；持久化蓝图仍为 blueprint-v2，旧 v1/v2 冻结记录不改。结构编辑保存时也重算汇总；知识范围、教学证据及所有合法选答的覆盖检查继续保留。

本次定向回归 61 passed / 20.87 秒，Django check 和 git diff --check 通过。原 R1 响应离线转换后覆盖校验通过；原任务仍 failed，11 小问/48 分/80 分钟也未擅自采用。0 真实调用，调用记录保持 188；未提交业务任务或重启服务。实际网站/worker 下次正常重载后使用新契约，须生成新预检，不套旧授权。当前验收 manifest 已移除固定逐题知识分配，旧运行快照保持。详见 [局部实施及验证](docs/superpowers/plans/2026-11-03-planning-part-coverage.md)。

## 当前实现：第六批 A+B 真实起步已执行，完整验收尚未完成（2026-11-02）

工作目录为 C:/Users/Yijia/dev/past_paper_generator；OneDrive 旧副本已停用。

- Materials 支持同课程 Topic 目录、公共/未归属筛选、多章节材料链接、物理页范围、重复上传显式追加链接与冲突比较；来源面板保留筛选。
- Course profile 提供课程概览和按 Topic 分析/审阅。分析输入由材料版本及明确物理页组成；切章前保存，失败可保留本地草稿；局部确认不会夹带其他 Topic 未审阅编辑。新共同信息会要求受影响章节复核。
- Generate 提供整课知识树和配置 v2（selected_topic_ids / knowledge_ids）。本批只允许单 Topic；旧 v1 topic_ids 的知识语义和冻结结果保持可读。Task/Papers 使用冻结章节摘要，Papers 可按 Topic 筛选。
- 本地集成已运行至合成题答和双 PDF。用户已确认 A+B 范围与 rubric：R1 一次规划因题目/小问目标不一致失败；E1 的 12 页转写 11 有效/1 来源字段失败，随后同 22 页课程分析成功保存 Topic 1 新草稿。R1–R6/E1 的本批题答生成、逐题审阅及新双 PDF 尚未执行。
- 完整后端 318 passed；之后诊断/章节接口/验收记录补测 11 passed，人工声明冻结与证据校验补测 13 passed。前端 31 passed、build/typecheck、Django/迁移检查通过。详细范围、首次失败及修复、实际浏览器命令见 [第六批记录](docs/batch-6-validation.md)。
- 本次实际 14 次模型调用+1 次计数，95,589 tokens；调用记录 173→188，全部有终态，没有自动重试。验收收集器补齐逐页失败和阶段错误，专项 9 passed；真实页面 6 组只读检查通过。详见 [A+B 实测与剩余事项](docs/batch-6-live-start-2026-11-02.md)。E1 草稿保留 1 项练习惯例选择、p44 转写缺口和 p40 公式待核对，不代表新 Topic 闭环通过。

已有环境启动（本机已应用本批迁移；升级其他已有环境前先备份并确认没有活动任务）：

~~~powershell
Set-Location C:/Users/Yijia/dev/past_paper_generator
& .\.venv\Scripts\python.exe scripts/local.py start
~~~

访问 <http://127.0.0.1:5173>。服务脚本复用当前进程；API 代码更新用 restart-api，后台更新用 restart-workers，后者拒绝在业务任务运行时重启。新真实外发仍受精确预检和授权约束。

[QM Materials](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/materials) · [Course profile](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/profile) · [E1 真实课程草稿](http://127.0.0.1:5173/courses/1aeae0e0-c154-4dae-b3e6-fa9b214840d7/profile?topic=2948d0da-c723-4cea-bb6b-386d0be37caa)。

以下为第五批及之前的实现、验证与操作记录，保留其历史状态。


## 当前实现：第五批已完成（2026-11-01）

第一轮 Task 1–10 已实现。成功任务保持题目阅读和主动开答案，答案区下方的 **Generate PDFs** 启动独立导出并跳转 Papers detail；**Run details** 默认折叠。题答成功即冻结保存，PDF 失败不撤销题答；重试使用同内容且不调用模型。Papers 可找回固定版本和两个文件；Generate another practice 先复核当前课程版本与配置，仍需保存、规划和确认。

实测：后端全库 **287 passed / 246.54 秒**，最终渲染/分页/并发补充 **17 passed / 45.73 秒**；前端 **23 passed**，类型、构建、Django 与迁移一致性检查通过。重启后浏览器 8 组检查通过、0 JS 错误；实际题卷 **5 页**、答案 **16 页**，最终导出 **9.831 秒**，全部 21 页转图核对。本批模型调用记录前后均 **173**，新增 **0**。

[直接打开真实题卷及两个 PDF](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/papers/45f3f96e-3478-475c-b839-d85ca7e1c2dd)。原真实生成约 **5m37s**，两分钟目标仍未达标；**第六批六次真实验收尚未执行**。新增历史输入的真实 token 和多样性尚未检验。完整检查、失败修正、文件和边界见 [第五批记录](docs/batch-5-validation.md)。

API、worker/dispatcher 已重启加载本批代码，web/数据库运行；使用 scripts/local.py start 复用服务。本机两份 papers 迁移已应用，backfill_papers 已保存 10 个旧成功任务（含明确标记的 fixture，不代表 10 次真实验收）。其他既有数据库迁移后可运行 backend/manage.py backfill_papers；该命令可重复执行，零模型调用、不自动导出。PDF 保存在被忽略的 var/data/papers/，与数据库共同保留。缺失文件可同内容重导出。

下一步是第一轮第六批，需按新预检确认真实调用；本批没有进入第二轮。独立已有未跟踪文档 docs/multi-course-compatibility-design-v0.1.md 保留原位，未纳入本次修改/提交。接手基线 18a18ab，已知 generation-v6 侧聊成果先保存为 71ae8de，pull --ff-only 已是最新；第五批提交以 git log 为准。

下文保留历史记录，当前状态以上述本节为准。

当前实现：第一轮 **批次 1–4（Task 1–8）的本地功能**，核验已更新为 **generation-v6**（2026-11-01）。课程材料与历年卷的比较使用精简 `source_overlaps`：模型只报告小问/来源 ID、是否同题、是否同结论及可空的短说明；代码仅在两项均为 true 时判重复，相同解题方法本身不构成重复。缺失或无法判断的必要事实不冒充通过。沿用有限来源检索、按题拆分、阶段保存和一次定向修复，没有新增模型阶段或页面操作。版本为 `review-policy-v3` / `originality-policy-v2`，新预检自动绑定新契约；现有确认结构可继续使用。

2026-11-01 实测：生成相关离线回归 **116 passed，168.61 秒**；Django check **0 issues**；Generate 页面显示已确认四大题，生成入口可用，历史题答可读且答案默认关闭，浏览器 **0 JavaScript 错误**。API 与 worker/dispatcher 已加载新代码，前端继续运行。模型调用记录前后均为 **153**，本次未发起真实生成、模型请求或官方输入计数，实际 token、耗时和新规则的真实质量待用户手动运行验证。入口：[QM Generate 工作台](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/generate)。实现和验证范围见[方案记录](docs/superpowers/plans/2026-10-30-source-originality-rule.md)。

此前基线与历史结果（不代表新版本真实验收）：**generation-v5**（2026-10-29）：卷内题间重复由代码按用户规则判定（审阅只报告“题目是否相同、结论是否相同”两项事实）；数学检查增加了区间定义域证明、绝对值尖点分段和核心/辅助划分（辅助项未判定时如实记录、不阻塞，判错时仍阻塞）。7496b3cb 离线回放的数学阻塞项从 5 项降到 1 项（下包络，旧规格按 core 处理）。2026-10-30 起，生成和修复调用使用独立上限（输出 20k、单次 300 秒，生成任务总时限 900 秒），其他阶段仍为 12k / 240 秒；同一冻结快照上的重试可复用之前已验证的第 0 轮大题（生成依据和输入都相同才复用，复用前重新校验，并记录来源）。后端 **252 passed**、前端 19 passed。真实运行 b02101f9 复用 Q1–Q3、新生成 Q4，最终只剩 `semantic:q3:originality` 一项阻塞，未发布；拆分未触发。详见[第四批记录](docs/batch-4-validation.md)末节。2026-10-31 按用户最新决定撤回来源意图的专门分类与约束，统一按生成内容的实际正确性检查和修复；历史来源记录保留。2026-11-01 定向离线回归 67 passed（93.05 秒）。该次回归只验证撤回专门约束；后续来源判重实现和验证见上方 generation-v6 记录。该历史记录当时尚未进入第五、六批；现状以上方第五批结果为准。产品代码和提示词不写死课程或科目内容（AGENTS.md 第 3 节，OPT-03）。

真实 QM 课程基线（2026-10-24；2026-10-28 网页另建四大题配置，见下）：用户已确认课程 **version 2**（45 页分析，32 页用页图转写，0 阻塞，8 个知识组全部 supported，含用户的两条练习偏好）；在其上完成真实 AI② 规划（blueprint-v2：3 道大题、13 个小问、60 分、95 分钟）、结构确认和输入冻结（快照 `7e2a758e-7e7e-4a03-b618-e7c12d56b708`），批次三真实验证完成。页图转写共 27 页（新格式，均经用户逐次授权），另有 5 页沿用第一批的页面核对结果；状态汇总中其余 138 页显示待授权（含那 5 页），未发送。

2026-10-22 完成第一批 5 页真实模型核对；2026-10-23 在用户新授权的 36 页抽取文字和 5 页已有核对结果上运行课程分析，得到真实的 `needs_info` 草稿，未冒充课程已确认。第三批于 2026-10-23–24 完成本地功能验证；2026-10-24 在真实课程 version 2 上完成真实规划、结构确认和输入冻结（快照 `7e2a758e…`），批次三真实验证完成。需求入口见 [AGENTS.md](AGENTS.md)，记录见 [批次一](docs/batch-1-live-validation.md)、[批次二](docs/batch-2-validation.md)、[批次三](docs/batch-3-validation.md)、[视觉证据路径](docs/visual-evidence-validation.md)。历史原型和原材料保持原位。

## 当前电脑启动（已实际运行）

在项目根目录打开 PowerShell：

```powershell
& .\.venv\Scripts\python.exe .\scripts\local.py start
```

访问 **http://127.0.0.1:5173**，点击 **Open local workspace**。程序检查 API 就绪后才打印地址。重复执行会复用已确认身份的本项目进程，补起已停止的服务。

- `5173`：Vite 前端；`8000`：Django API；本机当前 `54330`：项目 PostgreSQL（新环境默认 `54329`，实际以 `var/local.json` 为准）。
- worker、outbox dispatcher、API 和前端均在后台运行；日志在 `var/logs/`。
- 本机活动数据库在 `var/postgres-20261023/`；原 `var/postgres/` 是本次恢复前的保留副本，不是活动库。文件/解析/页图在 `var/data/`；离线解析权重在 `var/models/`。恢复原因和核对见批次二记录；不要把旧副本当作新数据备份。
- 项目进程信息在 `var/services.json`；本地随机密钥和数据库密码在被忽略的 `var/local.json`。不要分享这些文件。
- 当前是绑定回环地址的单人开发工作区，通过显式按钮建立受控本地 Session；所有材料端点有归属校验及 CSRF。它不提供正式邀请/密码登录功能，不应对外暴露。

停止全部项目服务及数据库：

```powershell
& .\.venv\Scripts\python.exe .\scripts\local.py stop
```

修改数据库结构时先停止 worker/dispatcher，避免新源码在旧结构上执行：

```powershell
& .\.venv\Scripts\python.exe .\scripts\local.py stop
& .\.venv\Scripts\python.exe .\scripts\local.py setup
& .\.venv\Scripts\python.exe .\backend\manage.py migrate
& .\.venv\Scripts\python.exe .\scripts\local.py start
```

`setup` 会复用已有私有配置和数据库，不清空数据。仅更新 API 代码时可用 `scripts/local.py restart-api`；更新队列映射后可用 `scripts/local.py restart-workers`，它仅重启本项目 worker/dispatcher，并在有排队或执行中任务时拒绝重启。本批迁移已应用，无需重复停库。机器休眠/意外停止后重新执行 `start`；任务租约过期 90 秒后重排队，旧执行不能写回。

## 可以操作什么

1. Materials 已导入首轮 11 个唯一真实 PDF、237 页；相同字节的原始路径独立保留。
2. 点击文件名或 **View source**：查看固定版本、SHA-256、物理页、原始 PDF、文本抽取和答案关联。来源参数保存在 URL，刷新可恢复。
3. 点击类型按钮修改分类；保存有反馈，旧 revision 返回冲突。分类建议不是官方考试范围判断。
4. **Answer associations** 可登记这份答案对应的题卷和页/题范围，可解除关联。
5. 未完成/失败材料可点 **View task**；已完成材料的来源面板有 **Processing task**。任务详情保留真实阶段、时间、诊断和此前尝试。
6. **Course profile** 查看真实 Topic 2 草稿：Knowledge、Scope & methods、Exam reference。来源按钮在同页打开原材料版本和物理页，刷新可恢复。
7. 修改字段后 800ms 串行自动保存，也可点 **Save changes**。失败保留输入；冲突必须比较后选择服务器版本或保留本地修改。浏览器当前标签的未提交编辑用 sessionStorage 恢复；服务器已保存草稿可跨会话找回。
8. 澄清问题有建议答案时显示为选项，另可 **Write my own answer**；**Save answer** 会记录 UserStatement，并保存当时所问的问题原文。需解释的新回答由新分析任务处理，不自动付费调用；分析已标为 answered 的问题不再重复询问。读取缺口显示现有页图入口；不是要求再次上传已存在的材料。
9. **Review & confirm** 只确认服务器已保存且无目标阻塞问题的 revision。确认后进入读取该冻结版本的 Generate 工作区。真实 QM 已有确认版本 1、2（当前使用 version 2）；fixture 课程标记为 `B2-TEST` / `B3-FIXTURE` / `B4-VISUAL-FIXTURE` / `B4-FIXTURE`。
10. **Generate** 可选择知识、三档难度、2–4 大题及三类题型；先 **Save configuration**，再 **Review structure** 查看精确输入并提交规划。修改本次配置不改课程默认；改回原值也需要重新规划和确认。
11. 结构中可编辑小问、分值、时长、选答和小问数量锁定。**Save structure** 后由服务端重新汇总并检查；经 **Confirm structure** 后，**Generate practice** 自动冻结或复用输入并打开精确预检。合成课程显示 **Generate with local fixture**；真实课程必须对本次用途及 context hash 授权，才可 **Start generation and checks**。不再有单独的 Prepare generation 按钮。
12. Task detail 显示生成、数学检查、盲解、语义检查和修复的实际阶段。完整候选保存后可读题；点击 **Show answers** 才请求答案、评分说明及可能透露答案的详细报告。刷新默认回到只看题目。**Source references** 打开固定材料版本和物理页；修复前后候选均可找回。
13. 必需检查为 fail / not_checked / inconclusive 时不会放行；候选和错误记录保留。模型拒答、截断、超时、未知结果如实记录，不自动重放未知付费请求。返回 Generate 可复核输入后发起新尝试，相同输入可复用完整且已通过结构校验的大题组。必要检查通过的候选已自动保存为 Paper；未通过者保留候选但不发布。

2026-10-29 核验规则更新：**Check progress** 显示已保存阶段及核验题号；必要检查未完成时，候选仍可查看但任务不会成功。**Check summary** 区分 required 与 optional，跳过项显示 not checked；可选项不影响必要检查通过后的成功状态。详细判断仍要主动点击 **Show answers**，阶段版本变化会刷新已打开的报告。旧无阶段记录的任务不补造结果。

可直接查看两个独立合成演示（0真实模型调用）：
- [必要检查通过、可选超限跳过](http://127.0.0.1:5173/tasks/ba5ca16b-99e9-4b79-b8fa-4e5329dc11fc)。
- [必要核验中断、部分成果保留](http://127.0.0.1:5173/tasks/bec205be-1814-4606-a403-0cad78f8a5ef)。

当前运行上限（2026-10-30 起）：模型保持原配置，输入上限60k；出题和修复输出20k、单次300秒，盲解和必要语义核验输出12k、单次240秒；整任务最多16次模型调用、900秒、一次修复。可选建议最多一次，20k/4k、计数10秒/模型45秒，剩余不足60秒跳过；不存在自动后台补跑。真实生成仍从 [QM Generate](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/generate) 的新预检发起。新策略、提示词和schema改变context hash，旧一次授权不被自动延用。

2026-10-28 来源规则更新：题目预览的 **Source references** 分为 **Academic / teaching evidence** 和 **Background references**。学术依据显示计划内、额外课程来源、仅背景记录或未解析引用；少量扩展不按引用列表硬拒绝。背景可用其他资料或一般情境，不能自动变成官方课程事实。背景说明可能透露答案，因此与 **Show answers** 一起加载；外部链接未自动核实或抓取。当前真实网页配置为 4 大题、15 小问、60 分（快照 68a09ab1-6059-4b59-a4af-6d3b880f1b2d），先前的三大题配置及失败记录保留。

[来源分层合成演示](http://127.0.0.1:5173/tasks/00dd1359-f7ae-4907-b48f-cf6de8a224ff) 为独立 B4-SOURCE-FIXTURE 课程，不代表真实质量验收。查看已有结果不会调用模型。新策略、schema 和提示词均进入新 context hash，下一次真实生成需通过更新后的预检；旧授权和旧失败结果不会被静默升级。

`Parsed` 只表示本地解析结束。Docling 当前关闭 OCR 和公式增强；数学页可能漏抽公式、丢失根号或读序错误，所有页面保持 `needs_review`。应查看原页图。后续 AI 分析必须选择相关页图或经验证的公式解析路径，不能把当前文本作为完整数学内容。

上传范围暂为每文件 20 MiB、每课程 20 个唯一 PDF / 300 个唯一页 / 30 个路径 / 100 MiB。超限和损坏文件单独报错，不撤销其他成功上传。解析进程有 15 分钟保护限额；排队时间与解析时间在记录中可区分。这些不是正式产品永久上限。

## 安装与重建环境

本机已完成安装，无需重复安装。当前实测：Windows、Python 3.12.14、Node 24.19.0、pnpm 11.25.0、PostgreSQL 17.11、Django 5.2.18、Docling 2.140.0、Procrastinate 3.10.0。Python 完整锁定在 `backend/requirements.lock`，前端锁定在 `frontend/pnpm-lock.yaml`。

以下为在具备 Python 3.12、pip、Node 24、pnpm 的 Windows 电脑上重建的步骤；各组件在当前电脑验证过，**尚未在第二台干净电脑完整复现**：

```powershell
python -m venv .venv
python -m pip --python .venv/Scripts/python.exe install -r backend/requirements.lock
pnpm --dir frontend install --frozen-lockfile
& .\.venv\Scripts\python.exe scripts/fetch_postgres.py
& .\.venv\Scripts\python.exe scripts/local.py setup
& .\.venv\Scripts\python.exe backend/manage.py migrate
& .\.venv\Scripts\python.exe backend/manage.py seed_local_course
& .\.venv\Scripts\python.exe scripts/setup_models.py
& .\.venv\Scripts\python.exe -m playwright install chromium
& .\.venv\Scripts\python.exe backend/manage.py import_qm
& .\.venv\Scripts\python.exe scripts/local.py start
```

`fetch_postgres.py` 从官方 EDB 页面取得 PostgreSQL 17 Windows 发行版，保存下载地址与 SHA-256；将来下载的补丁版本可能变化。`setup_models.py` 下载 Docling 本地权重，不读取或上传课程材料。启动脚本设置 Hugging Face 离线模式；缺少权重时解析会报可诊断错误。

本机没有 Docker/WSL，采用项目内 PostgreSQL 二进制与 Python/Node 进程实现已确认架构；没有安装系统数据库服务，没有声称 Linux 容器方案已验证。本批未创建未验证的 Compose 启动入口。

`.env.local` 是可选覆盖项，可从 `.env.example` 复制。留空 `APP_DATABASE_URL` 会使用本地私有配置。原有 LiteLLM `.env` 和虚拟环境不参与本应用。`OPENAI_API_KEY` 只保存在本地，不应发送到聊天或提交 Git。填入 key 不自动调用；网页分析必须显式提交，并对展示的输入范围授权。

## 第一批 API 接入验证

Materials 顶部的 **View saved call records** 可找回真实调用任务。任务页显示模型、阶段、耗时、用量或未知状态、错误、结构化输出（仅成功时）及精确来源链接。最新成功任务为 `32726231-997a-4c00-825d-60fbafc282d0`，总耗时 102.16 秒、18,215 tokens；成功的是小范围接入及页图检查，不能替代六次真实出卷验收。

2026-10-22 用户明确授权五个指定页面及官方目的地，并在额度不足后充值；随后验证成功。范围见接入记录；不重复请求同范围许可。以下提交命令会产生真实 API 请求，只有需要新的验收时才执行。日常查看已有结果和启动网页无需再次调用模型：

```powershell
# 只发送合成的 x^2 求导题，最多一次请求，不含课程材料
& .\.venv\Scripts\python.exe backend/manage.py ai_validate --submit --smoke-only --key <new-run-key>
# 一次合成检查成功后，逐页检查已授权的五页；该任务最多六次请求
& .\.venv\Scripts\python.exe backend/manage.py ai_validate --submit --allow-course-data-upload --key <new-run-key>
# 本地导出指定任务的记录；不调用 API
& .\.venv\Scripts\python.exe backend/manage.py ai_validate --report <task-id>
# 对已有成功结果执行固定样本数学断言及页面检查；两者均不调用模型
& .\.venv\Scripts\python.exe scripts/check_batch1_live_result.py 32726231-997a-4c00-825d-60fbafc282d0
& .\.venv\Scripts\python.exe scripts/test_ai_validation_view.py 32726231-997a-4c00-825d-60fbafc282d0
```

相同 key 和输入返回同一任务，不重复调用。需要人工审阅后的新尝试可传 `--parent <failed-task-id>` 保留尝试链。没有自动付费重试；远端结果不明的调用不能在恢复时自动重发。取消不能承诺撤销服务端已收到的请求或费用，但旧执行不能发布结果。

命令行授权仅覆盖固定清单，`APP_MODEL_MODE=disabled` / `ALLOW_COURSE_DATA_UPLOAD=false` 可继续保留。批次二使用单独的、绑定 course 和 context hash 的 AnalysisGrant；它只允许显式提交这份分析输入，不授权整门课长期外发。请求固定使用官方 Responses API、`store:false`、SDK 重试次数 0；`store:false` 不代表零保留。

## 第二批课程分析

入口：`/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/profile`。最新真实任务：`5a60ab41-a2a4-4b92-991c-1e420b637796`（succeeded，用于确认 version 2）。准入改为官方 token 计数（上限 60k），课程分析单次调用时限 300 秒，其他阶段 150 秒。第二批原始任务 `cd0d0c32…` 的 `needs_info` 结果与后续演进见[视觉证据路径记录](docs/visual-evidence-validation.md)。

查看已有结果不会调用模型。**Analyse again** 会先展示精确发送范围；提交会产生新的真实 API 调用。材料/声明/模型/提示词变化导致 hash 改变，需要明确授权新输入。同一提交 key 复用原任务，旧任务快照不变。原任务 `needs_info` 后的新分析有 parent 关联；取消或 lease 失效的执行不能发布草稿。

以下命令只读本地数据，不调用模型：

```powershell
& .\.venv\Scripts\python.exe backend/manage.py course_analysis
& .\.venv\Scripts\python.exe backend/manage.py course_analysis --report cd0d0c32-50c2-4f42-a2b6-3e9d148dd702
```

第二批原始授权只含 36 页文字和 5 页已有识别结果；之后的页图转写与重新分析均另行逐次授权，详见视觉证据路径记录。

## 第三批组卷规划

可操作的独立模拟课程：<http://127.0.0.1:5173/courses/5557e765-063f-4170-a75d-970799a675f1/generate>。该页面有已确认的四大题结构及两份历史输入快照。`Fixture data · no model call` 表示确定性测试数据；其分值、时间和教学安排不代表模型或真实课程质量结论。修改该模拟课程可走本地队列，不发送课程材料。

真实课程入口：<http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/generate>。用户已确认课程 version 2，并在其上确认了 blueprint-v2 结构（3 道大题、13 个小问、60 分、95 分钟），冻结了生成输入快照 `7e2a758e-7e7e-4a03-b618-e7c12d56b708`。

真实规划复用官方 Responses 适配器，但需要单独的 `PlanningGrant`，不会沿用第二批 `AnalysisGrant`。预检展示冻结课程描述、方法/范围、声明、配置及来源索引；不发送原页文字或新页图。授权绑定精确输入、模型、提示词与 schema。限额为每任务最多 2 次调用、180 秒截止、每次 150 秒、输入/输出 60k/12k，SDK 自动重试 0。当前实现正常规划只调用一次；未知结果不会自动重放。真实 AI② 共运行 3 次：51–59 秒、约 1.5–2 万 tokens；其中 1 次在同样输入下返回 needs_info（要求先回答未答的偏好问题）。实际扣费未查询，3 次样本不足以说明稳定性。详见[批次三记录](docs/batch-3-validation.md)。

规划 Task detail 支持真实阶段、取消、错误和原始蓝图找回。迟到结果不能覆盖新配置；取消后的旧执行不能发布。后续题答生成将读取 `GenerationSnapshot`；目前历史截止已冻结，历史试卷集合明确为空（Papers 尚未实现）。六次真实验收仍未执行。

## 视觉证据路径（页图转写）

计划见 [2026-10-24 计划](docs/superpowers/plans/2026-10-24-visual-evidence-path.md)，验证记录见 [visual-evidence-validation.md](docs/visual-evidence-validation.md)。

- **分流**：每页按 Docling 版面标签和文字量判断走 `text` 还是 `visual`（规则 `pdf-route-1`），判断原因记录在 signals 中。规则不看科目或文件名；拿不准的页走 `visual`。
- **转写**：`visual_transcription` 任务每页调用一次（官方 Responses、`store:false`、不自动重试），并发上限由 `APP_TRANSCRIPTION_CONCURRENCY` 控制，默认 6。结果按“页 + 解析 hash + 页图 hash + 模型 + 提示词/schema 版本”缓存，写入后不可修改，始终是模型候选，页面状态仍为 `needs_review`。
- **触发与授权**：解析完成后、授权创建后会自动排队。开发阶段只发送已按页清单授权的页，其余页显示“awaiting consent”，不会发送。
- **分析**：课程分析读取转写文字，不发送页图；没有转写的视觉页标为 `visual_pending`，模型不得猜测其内容。提示词或 schema 变化会改变 context hash，需要重新授权分析。

以下命令只读本地数据，不调用模型：

```powershell
# 每页状态汇总
& .\.venv\Scripts\python.exe backend/manage.py visual_transcription
# 预览指定页的精确授权范围（版本 ID:页码）
& .\.venv\Scripts\python.exe backend/manage.py visual_transcription --select <material-version-id>:2-6,8
# 查看某个转写任务的记录
& .\.venv\Scripts\python.exe backend/manage.py visual_transcription --report <task-id>
```

**会产生真实 API 请求**：在预览命令后加 `--authorize --scope-hash <预览得到的 hash>`。它会写入授权记录，并立即为这些页排队转写，只应在用户明确授权该页清单后执行。

浏览器检查用的 fixture：`scripts/prepare_visual_browser_fixture.py`。它会新建 `B4-VISUAL-FIXTURE` 课程，数据是合成解析结果和一条 fixture 转写，不调用模型。

## 检查命令

项目根目录 PowerShell：

```powershell
& .\.venv\Scripts\python.exe backend/manage.py check
& .\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests -q
& .\.venv\Scripts\python.exe backend/manage.py spectacular --file contracts/openapi.yaml --validate
pnpm --dir frontend api:types
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend test --run
& .\.venv\Scripts\python.exe scripts/test_workspace.py
& .\.venv\Scripts\python.exe backend/manage.py audit_batch1
```

后端测试使用独立 PostgreSQL 测试库与临时文件目录。浏览器检查使用正在运行的真实本地应用，会重复上传一个已导入 PDF、提交一个无效 PDF，并将截图保存到 `var/screenshots/`；不会调用模型。审计核对 65 个原始路径的 hash，报告保存在 `var/batch1-audit.json`，不改写原件。

`scripts/test_live_recovery.py` 是本批特定失败样本的故障注入检查：取消重试任务、终止本项目 worker 并重启，保留尝试链。它需要特定失败前置状态，不是日常启动命令；结果记录在 `var/recovery-check.json`。

课程页面浏览器测试使用独立的 fixture 课程（会新建 `B2-TEST`，不改真实 QM 草稿），其中一个本地保存请求被故意中断以模拟网络故障：

```powershell
& .\.venv\Scripts\python.exe scripts/prepare_profile_browser_fixture.py
& .\.venv\Scripts\python.exe scripts/test_course_profile.py
```

第三批浏览器测试同样使用独立模拟课程与合成教学 PDF，通过实际本地 API/队列验证，不调用模型：

```powershell
& .\.venv\Scripts\python.exe scripts/prepare_generation_browser_fixture.py
& .\.venv\Scripts\python.exe scripts/test_generation_workspace.py
```

每次重跑应先创建新的测试课程；脚本会保存配置、规划、确认和快照，覆盖其 `var/batch3-browser-fixture.json` 指针，不删除旧测试课程。当前完整后端回归 152 项、前端 12 项通过（2026-10-24）；浏览器覆盖范围与未验证项详见各批记录。2026-10-24 的 Claude Code 会话中，本机当前用户没有 Playwright Chromium（`ms-playwright` 目录不存在），Python Playwright 脚本未能运行，改用内置浏览器检查；安装前需用户同意。

Vitest 覆盖串行保存、迟到响应、未知保存结果的同 key 重试、冲突和标签刷新恢复。Python Playwright 覆盖实际浏览器；仍未建立 Node Playwright 测试集，不把 `test:e2e` 脚本视为已验收入口。


## 第四批本地验证与查看

工作目录为 `C:\Users\Yijia\dev\past_paper_generator`；原 OneDrive 副本停用。第四批未新增依赖，迁移 `generation.0003` / `generation.0004` 已应用。检查结果、浏览器记录、限制和真实预检入口见 [batch-4-validation.md](docs/batch-4-validation.md)；真实失败及下一次验证边界见 [handoff.md](docs/handoff.md)。

本地合成验收使用专用 `B4-FIXTURE` 课程，实际运行 API、数据库、任务队列、数学检查和网页；题答与语义判断来自合成适配器，模型调用为零。以下命令创建新的独立夹具并验证页面，不改真实课程：

```powershell
& .\.venv\Scripts\python.exe scripts/prepare_generation_content_fixture.py
& .\.venv\Scripts\python.exe scripts/test_generation_content.py
```

测试需服务正在运行，并有 Playwright Chromium；本机已确认可用。记录在被忽略的 `var/batch4-browser-check.json` 和 `var/screenshots/batch4-*.png`。浏览器验收与密集符号回归宜串行运行；符号检查超时会如实保留 not_checked 并阻止放行。


2026-10-26 更新：真实任务 [344da144-1127-46b2-b137-4707f98a6a04](http://127.0.0.1:5173/tasks/344da144-1127-46b2-b137-4707f98a6a04) 保留失败、3 大题题答、原报告及 18 条调用/计数记录。Show answers 主动打开答案。原模型响应全部有返回；没有需要自动重放的未知调用。旧任务保持原状态，离线修复结果另存，不提升原门槛。

只读核查已有真实结果（已实际运行，不调用模型）：

```powershell
& .\.venv\Scripts\python.exe scripts/audit_generation_task.py 344da144-1127-46b2-b137-4707f98a6a04
& .\.venv\Scripts\python.exe scripts/test_retained_generation.py 344da144-1127-46b2-b137-4707f98a6a04
```

本次程序/数学回放 23 个必需项中 21 通过，另外 2 项仍无法完整判定；原创性语义复核未重做。查重现在返回真实片段，空内容会阻断。修复后的本地合成闭环为 [f252278c-ac9c-417e-bcce-3f0a6baa9811](http://127.0.0.1:5173/tasks/f252278c-ac9c-417e-bcce-3f0a6baa9811)，零模型调用，不能替代真实验证。

`generation-v2` 把检查器契约纳入冻结输入，修复/语义提示词已有变化。新预检在 `var/batch4-generation-preflight-v2.md` / `.json`；同样 30 页、无新页图，hash 为 `2c01982cb2c17aab36141f4dee249e4a8a6a1f06fb4a872849c796fdcdd52114`。旧“一次运行”授权已经执行完毕，不自动授权第二次。旧任务仍可读取；下一次运行必须基于新预检，不把旧上下文当成新检查器下已通过的输入。


2026-10-28 新实测：[第二次真实任务](http://127.0.0.1:5173/tasks/bda61a74-c5e9-4639-adc3-08b4d35655b5) 已按修复版预检运行一次，failed / MODEL_INCOMPLETE。第一题输出达到 12,000-token 上限；第二题的完整成对输出保存在 GenerationArtifact。第三题和数学/盲解/语义核验未执行，没有完整候选。调用记录均有终态，本次没有自动重试。当前授权状态以本段和最新 handoff 为准，前文“第二次尚未授权/执行”属于此前记录。

第二题已导出到 `var/batch4-v2-partial/q2-questions.md` 与 `q2-answers.md`，明确为未核验的部分成果；网页任务显示错误和四条模型/计数记录。只读页面 5 组检查通过，不代表题目质量通过。调用概要为 `var/batch4-live-v2-outcome.json`，后续容量和诊断问题记入 [优化清单](docs/round-1-optimization-backlog.md)。服务保持运行。
