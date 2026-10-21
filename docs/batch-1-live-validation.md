# 第一批真实 API 接入补充记录

日期：2026-10-22（Asia/Shanghai）。本记录区分已实现代码、本地模拟协议测试、真实 API 失败及尚未执行的课程页验证。

## 当前结论

官方 Responses 适配器、调用预算及持久化、来源绑定、任务结果查看已实现。**第一批补充接入和五页样本验证完成。** 两次不含课程材料的合成请求最初因额度问题失败；用户明确授权五页并告知充值后，新任务成功完成 1 次合成检查与 5 次真实页图识别。保留全部失败历史，不将其从统计中删除。

原批次 1 / T1–2 是本地任务与 PDF 证据管理，完整课程理解属于批次 2 / T3。用户这次明确要求完成第一批需要真实模型的部分，因此增加小范围接入与公式页识别检查，不提前实现课程草稿、组卷或出卷。页面数量不是当前考试范围的判断，也不是课程材料完整性的门槛。

## 实际请求与保留的失败

| 任务 | 实际发送内容 | 请求结果 | 调用耗时 | 用量 / 费用 |
|---|---|---|---|---|
| `872d4595-8020-47f9-8f3d-2538132d7ba4` | 合成 `x^2` 求导与 x=3 求值题、JSON schema；无课程文字或页图 | HTTP 429，最初归类 `PROVIDER_RATE_LIMIT`；未获得模型输出 | 2.922 s | 服务未返回，未知；不记 0 |
| `54e5f6b4-2c61-4e62-b6a6-7738a4270b3a` | 同一合成题；人工诊断重试，parent 指向上次失败 | HTTP 429，provider code `credit_balance_exhausted`、type `insufficient_quota`；归类 `PROVIDER_QUOTA_EXHAUSTED` | 1.984 s | 服务未返回，未知；不记 0 |

第二次请求的 request ID 为 `req_468e78d4843b4781b63e7767bd2cc14d`，可用于向服务方排查。HTTP 429 不自动等于临时速率限制；新增分类器识别额度耗尽。第二次任务的初始通用分类保存在调用 metadata 的 `original_error_code`、旧 ErrorRecord 和诊断事件中，随后追加了明确的额度诊断。没有抹掉首次分类或把失败改成成功。

SDK `max_retries=0`。前两次失败属于两个单次请求的不同任务，不是 SDK 隐式重试。用户随后告知充值，第三个任务 `32726231-997a-4c00-825d-60fbafc282d0` 关联第二次失败，成功执行以下 6 次调用。共发出 **8 次请求：2 次失败、6 次成功**；没有切换服务商、模型或 endpoint，没有访问或修改账户账单。

| 成功任务内调用 | 输入 tokens | 输出 tokens | 调用耗时 | 结果 |
|---|---:|---:|---:|---|
| smoke | 89 | 41 | 3.453 s | 导数 2x，在 x=3 处为 6 |
| M34 p14 | 2,432 | 1,140 | 17.125 s | 左右导数公式及图示恢复，来源绑定通过 |
| M34 p41 | 2,473 | 1,503 | 22.344 s | 临界点根号和二阶导数恢复，来源绑定通过 |
| M14 p5 | 2,340 | 1,204 | 19.110 s | 平方根求导推导恢复，保留原条件并单列域解释 |
| M33 p22 | 2,360 | 931 | 15.641 s | 忠实保留两条右端为 1 的原式，纠正建议独立保存 |
| M48 p20 | 2,394 | 1,308 | 20.297 s | 识别故意错误证明，保留错误原式与正确解释的区别 |
| 合计 | **12,088** | **6,127** | **97.970 s** | **18,215 total tokens** |

任务从提交到完成 **102.157688 s**（约 1 分 42 秒），包含排队和本地检查。服务均返回 `model=gpt-6.1-sol`、`service_tier=default`；cached input 0、reasoning tokens 176（已包含在输出计数中，不能再次相加）。按查询日官方 Standard 输入 $2 / 百万、输出 $10 / 百万的基础 token 单价估算，本成功任务约 **$0.085446**；这是估算，非账单，未核实可能的其他收费，之前两个失败请求用量/费用仍未知。本次少量页图任务不是完整出卷，不能据此宣布完整产品两分钟目标达标。

## 五页范围及数据处理授权

2026-10-22 用户对下述具体数据、目的地、模型及用途回答“允许按上述范围发送”。该授权已成立；恢复相同范围的验证无需重复询问。

目的地：`https://api.openai.com/v1/responses`；模型：`gpt-6.1-sol`；用途：第一批公式识别及原始页与抽取文本的差异检查；`store:false`。仅发送五个物理页的 PNG、该页抽取文本和必要的版本/页码/hash 引用，不发送整份 PDF、原始本地路径、其他课程页或账户凭据到模型输入中。

| ID | 原文件名 | PDF 物理页 | 选页原因 | 真实模型检查 |
|---|---|---|---|---|
| M34 | MSIN0180 Topic 2 - Lecture 2 11_01_2026, lecture slides (1).pdf | 14 | 左右导数、绝对值函数，读序及公式丢失 | 已返回，关键点对照通过 |
| M34 | 同上 | 41 | 收益/成本最优化，根号和关键式子丢失 | 已返回，关键点对照通过 |
| M14 | MSIN0180 - Calculus - Revision 19_03_2026.pdf | 5 | 平方根导数定义推导；抽取仅余标题，需区分源条件与纠正建议 | 已返回，关键点对照通过 |
| M33 | MSIN0180 Math Background for topic 2 11_01_2026.pdf | 22 | 对数/指数互逆公式；需忠实保留原页可能错误并单列解释 | 已返回，关键点对照通过 |
| M48 | MSIN0180 - Topic 2 - seminar 11_01_2026.pdf | 20 | 标明 WRONG proof 的教学反例；不能误当正确课程方法 | 已返回，关键点对照通过 |

最初包含课程页的命令被自动审批审查拒绝，理由为当时尚无用户对五页及具体外部目的地的明确授权；该命令未执行。随后仅运行不含课程材料的两次合成请求。用户补充明确授权并完成充值后，完整任务获准执行并成功；这两项阻塞现已解除。`store:false` 不等于零数据保留；用户授权问题中已明确告知此区别，不据此声称账户具有 ZDR。

## 已实现的契约和运行边界

- `backend/app/ai/responses.py`：固定官方 endpoint，忽略环境中的替代 base URL；结构化 `text.format` / strict schema；单页 PNG 高细节输入；无工具、无文件上传 API、无后台响应和隐式重试。区分 parsed、refusal、truncated、invalid_output、provider_error、not_executed；保留服务返回的 usage、request/response ID、耗时及安全错误代码，不记录密钥或原始错误消息。
- `page_review.py`：独立的 SmokeResult 与 PageReview schema。每页输出固定 source reference、忠实转写、公式位置/可辨认程度、parser_loss/source_issue/intentional_wrong_example/uncertain、教学用途及未决项。原文和页图中的指令作为资料；原页错式保留在转写内，修正只能出现在独立解释中。
- `invocations.py` + `core.ModelInvocation`：调用前锁任务并占预算，持久化输入 hash、提示词/schema 版本、来源及调用位置；相同任务/位置唯一。已完成结果可以恢复复用；started 但无结果的调用以 `MODEL_OUTCOME_UNKNOWN` 失败，不盲目重发。返回用量可留存，但取消/旧 epoch 不可发布任务结果。
- `validation.py`：固定五页清单，冻结 material version、parse version、原 PDF hash、解析文件 hash、页图 hash 和文本输入 hash；每页调用前重新检查。输出 source 必须与输入一致。成功的页面识别也只标记 `model_candidate_not_human_verified`，不改变原始 Evidence 的 `needs_review`。
- `ai_validate` / `validate_ai_one` + worker：显式命令提交，outbox 和独立子进程执行；全局 worker 并发 1，同课程 AI 任务互斥。完整任务最多 6 次请求、15 分钟；合成检查上限输出 1,000 token，单页上限输出 5,000，单次最长 150 秒且受任务剩余时间约束。首次错误停止本任务。
- 输入 admission 使用 UTF-8 字节数加单张受尺寸限制图片的保守预算（8,192）；这是本地保护估计，不是假称精确 tokenizer 或账单 usage。总输入上限 60,000；图片限制 PNG、最大边 1,600、8 MiB。服务端未返回的 usage 为 null。
- Task 页新增调用记录、结构化输出折叠区和同版本来源链接；Materials 可找回验证任务。网页没有发起付费重试的按钮，保留取消与刷新恢复。同一 CLI key 不创建重复任务；人工新尝试可以绑定 parent。

不永久开启网页 AI；`.env.local` 的常规开关仍为 disabled/false。显式 CLI 验收授权是受固定清单限制的一次业务任务，不能扩大为任意课程内容外发。既有 `call_model` 普通调用边界仍默认 disabled；正式 AI①接入和编辑确认流程留到批次 2。

## 验证与可查看位置

本地测试与真实请求分开统计：新增模型协议测试使用 `httpx.MockTransport`，不代表真实模型能力；上表 6 次成功是实际 API 返回。

- 最终全后端回归：**40 passed，47.75 s**。覆盖实际 SDK 请求格式、固定 endpoint、store:false、拒绝/截断/错误及额度分类、图片尺寸边界、无隐式重试、未知用量、持久结果复用、取消与六次预算、调用记录跨用户隔离、网页禁止重复付费验收、合成范围不读取课程材料。
- Django check：无问题；数据库迁移执行成功，`makemigrations --check --dry-run` 无缺失迁移。
- OpenAPI validate / 类型生成及生产构建通过；现有真实本地浏览器 **8 项**检查通过，新增成功结果页面 **7 项**通过：六条记录、刷新保持、可展开真实输出、准确源页及刷新、Materials 找回、390px 无溢出、无浏览器错误。
- 原件审计：65 个路径、hash 不一致 0；11 个真实 PDF 的本地解析仍为 succeeded。
- `scripts/check_batch1_live_result.py <task-id>` 已通过：6 次 live/parsed 与真实 request/response ID、5 个精确 source 引用、主要公式锚点、固定来源表达式的 SymPy 数学检查。输入/输出计数一致，逐页绑定和 store:false/零重试元数据通过。
- 成功后使用完全相同的 CLI 幂等 key 再提交：仍返回 `32726231-997a-4c00-825d-60fbafc282d0`、state=succeeded；调用记录仍为 6 条，没有新增请求。
- 逐页原图与模型完整输出已由本开发代理目视对照。M34 p14 的左右导数 -1 / 1；M34 p41 的临界点和极大值判别；M14 p5 的求导和实域条件；M33 p22 的原式与更正区分；M48 p20 的原极限为 3、第二次 L’Hôpital 不合法，均通过选定样本核查。**这是开发代理抽查和固定数学断言，不是用户/教师人工确认，也不是一般语义核验器。** Evidence 仍保持 needs_review。
- 发现的解释尺度问题：M34 p41 的近似等号、未显式写出的生产域，以及 M48 p20 的排版空格会被模型列为 source_issue。它们应作为分级备注，不应自动否定整份材料或阻断课程分析；后续 AI①需按重要性整理。
- 尚未执行：真实模型运行中的取消/中断故障注入、完整课程理解、出卷与两个输出 PDF。取消和恢复保护目前由本地隔离测试覆盖。六次真实出卷验收仍为 **0/6**。

本机地址：

- [Materials](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/materials)
- [成功验收任务及五页输出](http://127.0.0.1:5173/tasks/32726231-997a-4c00-825d-60fbafc282d0)
- [此前真实失败和额度诊断](http://127.0.0.1:5173/tasks/54e5f6b4-2c61-4e62-b6a6-7738a4270b3a)
- `var/batch1-live-872d4595-8020-47f9-8f3d-2538132d7ba4.json`
- `var/batch1-live-54e5f6b4-2c61-4e62-b6a6-7738a4270b3a.json`
- `var/batch1-live-32726231-997a-4c00-825d-60fbafc282d0.json`
- `var/batch1-review-32726231-997a-4c00-825d-60fbafc282d0.json`
- `var/ai-validation-browser-32726231-997a-4c00-825d-60fbafc282d0.json`
- `var/screenshots/ai-validation-desktop.png` / `ai-validation-mobile.png`

本地 JSON 及运行数据保持 Git 忽略；源码、迁移、测试和脱敏说明提交。原课程 PDF、历史原型及正式 PRD/技术设计没有改写。

## 官方依据（查询日期 2026-10-22）

- [GPT-6.1 Sol 模型](https://developers.openai.com/api/docs/models/gpt-6.1-sol)：图像输入及结构化输出能力已在上述小样本中实际验证。
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)：schema 约束、拒绝和不完整输出仍需单独处理。
- [Images and vision](https://developers.openai.com/api/docs/guides/images-vision)：Responses 图像输入支持本次的内联图片路径。
- [Data controls](https://developers.openai.com/api/docs/guides/your-data)：`store:false` 与零保留是不同概念，本次没有验证账户区域或 ZDR 状态。
- [Pricing](https://developers.openai.com/api/docs/pricing)：本次基础 token 成本估算使用 Standard 输入 $2 / 百万、输出 $10 / 百万；费用以实际账户账单为准。

本次请求范围已完成，无需继续重跑这五页。下一批可复用官方 API adapter、错误分类、持久调用记录、固定版本来源和本次视觉识别结果；完整课程理解仍需其专门提示词/契约、课程草稿/确认与缺口交互。当前五页授权不扩大为全部材料的任意外发授权。本次未进入第二批或第二轮。
