# 第六批 A+B 真实起步验证（2026-11-02）

## 结论与授权边界

用户明确回复“允许 A+B，并确认验收口径”。本次执行 R1 的一次规划、E1 精确 12 页转写及同 22 页派生输入的一次课程分析。rubric 与 Codex 独立逐作答单元开发审阅的口径已确认；原 manifest/rubric 文件及哈希保留，确认另存私有 approval 记录，没有改写冻结输入。

R1 规划返回通过 JSON schema，但业务结构检查失败；E1 转写 11 页有效、1 页来源字段失败；E1 分析成功并保存新的 Topic 1 草稿。尚无本批题答生成、内容审阅或新 PDF，不计六次验收通过，也不计 E1 完整闭环通过。没有自动重试或重放任何模型调用。

## 真实调用与时间

| 阶段 | 任务 | 结果 | 模型请求耗时 | 系统墙钟（含队列） | 输入 tokens | 输出 tokens |
|---|---|---|---:|---:|---:|---:|
| R1 规划 | d08de7d8-643d-4d07-9319-862ccb7314ce | failed / QUESTION_COVERAGE_MISMATCH | 37.610 秒 | 44.373 秒 | 16,397 | 3,110 |
| E1 页图转写 | 84b790d4-05d7-45aa-b2ee-cab7af8b1884 | 11 有效 / 1 失败；任务 succeeded | 12 个调用分别记录，不相加当作墙钟 | 116.837 秒 | 39,038 | 20,643 |
| E1 课程分析 | 1affd130-d954-4f58-92f8-3f4557b2d940 | succeeded；草稿 revision 1 | 83.484 秒 | 93.950 秒 | 10,077 | 6,324 |

合计 14 次模型调用、1 次官方输入计数；实际 usage：输入 65,512，输出 30,077，合计 95,589 tokens。E1 分析官方输入计数 10,077，计数请求耗时 1.969 秒；它不是另一次生成用量。全部 15 条调用记录有终态，14 次模型响应均 parsed；parsed 只证明响应可解析，不能代替来源及业务校验。无未知结果、输出截断或超时。实际费用/价格未核实，保持 unknown。

转写冻结并发 2，按调用起止区间计算的峰值也为 2；恰好 12 次调用，失败页没有重发。使用官方 Responses / gpt-6.1-sol / store:false / SDK 重试 0，沿用获准限额。三个阶段顺序运行。尚未测量本批 generation+export 完整系统时间，不能用准备阶段时间声称两分钟出卷目标达标。

## A：R1 的实际失败及本地提案

获准输入 hash：e11eec77fdef8a8a5f25c99f09b1fc8634b64c579240c828fcfb3d8cdb22e15d；执行前与当前输入重算一致。

模型 Q2 题目级 knowledge_ids 只列 K5，但 Q2(b) 的 part knowledge_ids 为 K5/K2；Q3 也把 K2 加入了大题目标。程序严格验证题目与小问目标集合，R1 在发布 Blueprint 前失败。这不是 token 超限、API 凭据或模型响应截断。

模型原提案为 3 大题、11 小问、48 分、80 分钟，未锁定小问数。规划请求只约束三大题和知识/题型；验收矩阵的 3/2/3、12/8/10、40 分钟原本就计划在返回后编辑，不能把矩阵差异冒称模型违反了未收到的配置。

原任务、调用响应和失败均保留。另在本地依照已确认矩阵整理了提案：
- Q1：K1/K2；3 小问，12 分。
- Q2：K5；2 小问，8 分；明确提供导数，重点为 Rolle/MVT 条件与论证。
- Q3：K3/K4；3 小问，10 分；简单单变量应用、候选分类与端点比较。
- 全必答，三类题型，锁定 8 小问、30 分、40 分钟；仍是建议练习设置。

validate_blueprint 和 check_matrix 均本地通过。proposal hash：d6fe767110c983e5f1f9d9d0eee3ff5ce2f579251247d3d6968cea0cfa1310e7。本地提案不是成功模型输出，尚未发布到产品 Blueprint 或 StructureConfirmation，没有改成“规划成功”。文件为 var/evals/round1/R1/reviewed-matrix-proposal.{json,md}。

下一步建议：题目目标并集和整卷 coverage 由程序从 parts 派生，仍严格检查知识范围、证据支持及全部题型；把“主考目标”和仅作前提的知识关系说清，避免为了摘要冗余不一致浪费整次规划。该建议本次尚未实施；后续改动需新契约/精确预检，不能套用原失败任务授权重发。

## B：E1 转写与新课程分析

页图 scope_hash：132187abfb75df81d1deb1ffe0a37e180ed67be5ef7542f4d88cc0606c63d5e1。执行前逐页重算 evidence/parse/image 哈希、版本和路由均匹配。只发送原 12 页，没有扫描/外发其他待转写页。

唯一失败为 MSIN0180 Lecture 1, lecture slides, 11_01_2026.pdf 物理 p44。模型返回的 parse_content_hash 多复制了一段字符；其余来源字段一致。check_transcription 拒绝保存该页为 VisualTranscription。原响应仍可审计，p44 保留 visual_pending，没有改写原材料、覆盖失败、伪造有效转写或自动多调用。

转写后重算并保存分析输入：
- context hash：be89bce08f32129f049c1987d78b1f51d63f7f59d265d3c947ba09ca25586e69。
- 精确 22 个物理页，11 份来自本次获准页图的有效转写；p44 明确 pending。
- 只有既有 All lecture content 用户声明；其 provenance=user_statement、authority_status=unverified 保持。
- 没有 Topic 2 知识目标或新图片；来源集合与授权选择完全一致。
- 父 scope/用户确认来源记录在 AnalysisGrant 和私有预检中；before-transcription 快照未直接执行。

新草稿 fd02fd70-69b9-45b3-bdf1-bcfec7589e08 / revision 1：一个章节根节点、6 个子知识组、9 条方法规则、8 项问题/提示、1 项 needs_confirmation 的练习惯例选择。独立核查所有引用属于 22 页，知识 ID 与主课程 Topic 2 无交集。未自动确认 CourseVersion。

6 个子知识组为：limit notation and one-sided limits；limit laws and algebraic simplification；standard trigonometric and exponential limits；continuity at a point and on a domain；boundedness and extrema existence；IVT, roots and fixed points。

须如实保留：
1. p44 缺失转写不阻断其他可读来源所支持的连续性知识。
2. 模型新提出 Lecture 1 物理 p40 的 revenue 公式版式待核对；它在 22 页文字范围内，但其页图未在原 12 页外发授权中。本次未补发。E1 可以不选用该例题公式，不把补齐所有材料作为其他知识的统一门槛。
3. 练习惯例选择已在产品内展示，涉及切线/连续性定义域、IVT 端点方向及两条不一致印刷答案。用户选择是练习偏好，不能认证来源真伪。建议采用标准定义并注明差异；本次没有替用户提交答案。
4. 模型建议的模板为 3 题/30 分/45 分钟，只是新草稿建议；E1 最终仍按后续选择的知识规划和确认 2 大题，不自动套用 Topic 2 或模型模板。
5. 所有转写仍为 model candidate / needs_review；本次浏览器已实际查看 additional questions p16，确认能看到原页与转写，未宣称 12 页均人工复核。

页图失败的工程改进建议：将完整来源 hash 保留为服务器冻结请求、调用记录和缓存键，让模型只返回页面内容/定位及不确定项，再由程序附上来源。不要依赖模型逐字回抄 64 位 hash；也不能直接忽略现有 SOURCE_MISMATCH。此契约调整本次未实施，旧记录不改。

## 本次本地修复与实际检查

evals/round1/collect.py 现在为每阶段收集 state/result/error/checkpoint，并保存转写任务内部的逐页失败 notes。规划阶段失败在没有 generation 时也直接保留错误。收集器仅读取业务数据，新增 append-only 验收文件，不改写业务任务或把转写部分失败记成完整闭环通过。

新增两项回归：完成转写内的失败页保留；没有题答任务时的规划错误保留。实际命令：

~~~powershell
& .\.venv\Scripts\python.exe scripts/test_batch5_backend.py -c pytest.ini tests/test_eval_accounting.py -q
~~~

结果：9 passed / 20.67 秒，独立随机 PostgreSQL 测试库，测试移除真实密钥并阻断未 mock 的官方 API。启动器会切入 backend；第一次多写一层 backend/ 路径导致配置文件不存在，尚未进入测试；修正相对路径后上面的正式测试通过。Django check 0 issues，git diff --check 通过。未重新跑整个后端、前端构建或全量回归。

Playwright 对真实成果的 6 组只读检查通过：R1 错误与刷新恢复；E1 成功任务/默认折叠；新草稿刷新找回；待选择惯例仍留在产品；同版本/物理 p16 来源图；用户声明单独归因。0 JS 错误、0 业务写请求、模型调用数不变。第一次图片定位误匹配装饰 SVG，改为确切原图 accessible name 后重跑通过；不是原页加载失败。

旧基线 2,438 条业务记录中，只有授权 R1 save_config 正常更新的 generation.GenerationDraft 7744d536-6584-4534-810f-56c1deba9d36 变化，其他 2,437 条原字段哈希保持；原 25 个材料/PDF 文件字节哈希保持。模型调用记录从 173 增至 188，恰好本次 14 模型+1 计数。没有新依赖、迁移、运行限额或模型更换。

## 可查看成果及证据

- [R1 原真实失败任务](http://127.0.0.1:5173/tasks/d08de7d8-643d-4d07-9319-862ccb7314ce)。
- [E1 转写任务](http://127.0.0.1:5173/tasks/84b790d4-05d7-45aa-b2ee-cab7af8b1884)。
- [E1 分析任务](http://127.0.0.1:5173/tasks/1affd130-d954-4f58-92f8-3f4557b2d940)。
- [E1 新草稿](http://127.0.0.1:5173/courses/1aeae0e0-c154-4dae-b3e6-fa9b214840d7/profile?topic=2948d0da-c723-4cea-bb6b-386d0be37caa)。

服务使用 scripts/local.py start 复用并保留运行。已请求在内置浏览器打开，工具返回 queued；页面实际可访问性由上述 Playwright 验证。收尾 web/API session/前端代理 session 均 HTTP 200，0 活动任务、调用记录仍 188；本地状态保存于 var/evals/round1/A-B-final-status.json。

私有证据均保持 Git 忽略：var/evals/round1/approval-2026-11-02-A-B.json、approved-A-B-observation.json、approved-A-B-findings.json、A-B-browser-recon.json、browser-*.png、E1/analysis-preflight-after-transcription.json、analysis-scope-after-transcription.json、draft-review.json。收集器已追加 R1/e92404f7-1a75-47d5-ac8d-b62e19a90d36 与 E1/fc8cc4a8-f875-46f6-872e-14b8b725ea6b 记录；旧记录不覆盖。

## 下一步与未执行

R1 原位置保留“规划失败”，本地提案尚需正常保存/确认；后续补测独立编号，不能替换失败。E1 尚待产品内惯例选择、局部确认及 2 题结构。R2–R6 未执行；R1–R6/E1 全部尚无本批真实题答或双 PDF，逐题质量审阅尚未开始。下一次真实生成须绑定当时的确认版本、蓝图、历史及新精确范围；A+B 不自动授权七次题答生成。

第六批、第一轮完整验收均未完成，没有进入第二轮。

接口资料于 2026-11-02 核对：[OpenAI 官方数据控制说明](https://developers.openai.com/api/docs/guides/your-data)。store:false 不等同账户已获零保留；本次沿用用户接受的处理条件，没有额外推定账户资格。没有引用未核实价格或费用。
