# 第六批 R1 补测、R2 跳过与 E1 后续状态（2026-11-03）

## 用户本次指令及范围

用户要求“直接把R1在生成验证一次，直接跳过R2，然后把继续E1的验收”。仅推进 R1 一次补测和 E1；未执行 R3–R6。R1 原失败保留，新增 R1-retest-01；R2 明确登记 skipped，不算成功或失败。原始计划仍保留 6 个位置，当前 active_planned_total=5；E1 是额外项目。

## R1 实际结果：规划成功，生成验收未通过

- 新规划 task：40e3ed42-d950-4ec9-8b67-5f15d37c4476。模型实际耗时 33.734 秒，系统墙钟 37.272 秒。新 planning-v3-part-coverage 真实返回成功，模型只填写小问知识，程序汇总覆盖。
- 模型原提案 11 小问/48 分/75 分钟；通过正常 edit_blueprint / confirm_structure 编辑为 3 大题、8 小问（3/2/3）、30 分（12/8/10）、40 建议作答分钟，保留全部已选知识，不固定逐大题知识分配。
- 旧 CourseVersion 2 没有改写。结构确认曾暴露 TOPIC_OUTSIDE_VERSION：该入口误用旧 frozen_payload 而未做 course_projection，现已接入原有只读映射。隔离测试先复现失败，修复后通过。
- 编辑来源后，旧预检幂等键正确拒绝不同输入，未调用模型；改用绑定新 confirmation 的精确预检键，旧快照保留。正常产品 submit_generation 接受新授权，不复用变化前的预检。
- 生成 task：828c1c21-a550-4c55-b299-a7052020785a。
- 精确 context hash：318886ad9462465b318bc172f8a3adc1fa75901a1af062b83f9c287a86cc8614。
- 实际来源为上次成功运行范围内的 26 个物理页；1 份已有题卷历史；无新页图。完整预检 var/evals/round1/R1-retest-01/generation-preflight-v2.{json,md}。
- 官方 Responses / gpt-6.1-sol / store:false；16 次模型调用上限、900 秒任务、一次修复、未知结果不自动重放。

三题八小问完整生成并保存。初轮检查发现 q2-b 的核心 stationary_points 检查无法解析根式字符串；系统只对 Q2 做一次修复。题面、答案与盲解不变，仅检查点字符串从 -2/sqrt(3) 等改成带括号形式，仍不符合数字字面量规则。最终仍 failed / REQUIRED_CHECKS_BLOCKED，未保存 Paper、未发布、没有新 PDF。

最终候选 v2：1a1a5dbe-416f-4686-b11c-189483cc3eb3；
candidate hash：f97c96b04a777f555c4468a491e7a57a1f27bcfc65d2aef7d0c846bf77966038；
CheckReport：73e9695b-2b60-45bc-88f7-40f1c8e8dcf5。

最终 58 项必要检查：56 pass、1 not_checked、1 inconclusive。阻塞为 math:q2-b-check-interior-points 及 semantic:q2:math_relevance。12 项可选检查因必要项未过未执行，不能当作可选预算失败。

## R1 原因、质量与实际用量

Q2(b) 的函数为 g(x)=x³−3x，区间 [−2,2]。端点割线斜率为 1；解 3c²−3=1 得 c=±2/√3，均在区间内部。独立数学审阅认为该结论及推导成立。但检查器的 points 只接受有界数字字面量（小数或整数分数），不接受 sqrt 表达式字符串，必要计算验证没有完成。

本次没有放宽必要 gate，也没有把独立审阅改写为程序检查通过。8 小问的条件、推导和分值逐项复核记录绑定最终候选 hash，但整体放行仍 false。候选、两轮完整报告、原模型响应均保留。

建议后续在独立范围内增加受限、类型化的常量 AST 表示来表达根式点，维持不执行任意字符串及精确解集比较；或者让生成/修复在保持知识目标的前提下选用当前检查器支持的题目。本次未实施该能力扩展，也没有额外再生成一次或把失败改为成功。

| 阶段 | 模型请求 / 计数请求 | 输入 tokens | 输出 tokens | 合计 | 系统墙钟 |
|---|---:|---:|---:|---:|---:|
| 规划 | 1 / 0 | 16,404 | 2,608 | 19,012 | 37.272 秒 |
| 题答与核验，含一次 Q2 修复 | 9 / 9 | 169,843 | 34,053 | 203,896 | 343.599 秒 |
| 合计 | 10 / 9 | 186,247 | 36,661 | 222,908 | 两阶段分列 |

两次整卷语义输入计数为 38,918 / 38,921，都未超过 60,000，未触发真实拆分。所有 19 条新调用记录有终态，模型响应均 parsed；无截断、未知或超时。费用未核实，保持 unknown。生成任务本身已超过 120 秒，未形成 generation+export 完整交付耗时；不能声称两分钟达标。

## R2 与验收统计

- 用户要求跳过 R2，本地追加 skipped 记录，没有模型/业务任务。
- 汇总新增 skipped_slots 与 active_planned_total；R2 从 not_executed_slots 中单列，保留原计划总数 6、原失败和补测。
- R1 原位置仍是原规划失败；本次补测也 failed，独立记录。R3–R6 未执行；没有宣称六次全部通过。

## E1 最新：人类已确认，获准分析已执行，课程草稿仍 needs_info

本节更新覆盖下方“外发被拒绝”的历史检查点。用户已回答两项问题：练习采用标准数学定义并注明资料差异；允许按原 6dc34c33… 快照进行一次后续分析。自动审批此前拒绝所缺的授权已经获得，不再作为当前阻塞。

- 分析 task：fd64ee51-0e51-44ce-9ff8-0f1ae39d9c31。
- AnalysisGrant：b5eded16-a595-4e2b-9524-345559410931；另存明确人类确认，不修改原获准输入。
- context hash：6dc34c33b2918ca9d1ccf73b8bf75c1ef72065bf0fec1e93ab13c5d6c3cf6805。
- 沿用 22 页文字及 11 份已保存转写；无新页图。官方 Responses / gpt-6.1-sol / store:false，单次 300 秒、任务 900 秒、一次分析及对应计数；没有未知结果重放或追加分析。
- 计数请求 1.047 秒、10,771 输入 tokens；模型请求 78.750 秒，实际 input=10,771、output=6,906、total=17,677，reasoning=351、cached=0；系统提交至终态 84.611301 秒。没有超限、截断或 API 错误，费用未核实。
- 结果 needs_info，草稿发布到 revision 3，4 个部分支持节点导致阻塞。不能将该状态说成成功完成课程确认，也不能把它说成传输或 token 失败。

### 剩余阻塞与已落实的人类选择

本次获准快照原文仍包含“临时约定由 Codex 选择、用户尚未单独确认”。用户同时批准了使用该精确输入并回答了选择题，但真正发送的旧快照没有纳入新的人类回答。这项输入状态同步问题使模型再次询问同一惯例；不应归因于用户未选择。没有改写旧快照、模型响应或机器草稿来伪造它当时已看到新回答。

之后通过正常 answer_clarification 保存了实际回答：新 UserStatement 36c5c186-8b35-4a04-9eaf-e14202a14a48，明确取代旧临时说明 43912317-9d4d-4ed4-ae80-3fd4e67135dc；来源为本次用户明确回复。原材料与差异说明保留；练习偏好不能提升为官方教学纠错或官方考试公告。草稿现 revision 4，产品现有逻辑将新回答标为需要分析。

4 个 partial 节点分别为章节总节点、连续性、闭区间有界性/最值存在性、介值定理/不动点；极限记号、极限法则、标准三角/指数极限三组已 supported。partial 原因混合了惯例确认、个别不可读例题及根节点汇总。当前 confirm_topics 会检查整个 Topic 的所有节点，且新澄清未进入分析 base 时拒绝确认，所以无法直接确认。并非缺少全部教学材料，也不是需要用户再回答相同偏好。

本地只读查看了 Lecture 1 物理 p35（印刷 36，直观连续性）和 p38（印刷 39，基本函数连续性定理）的页图；模型此次 visual review 的证据 227e49e4-6143-40d9-ade5-4cbc3514b8ce 实际指向物理 p38。其版面可区分基本函数类别，定理明确限于定义域。此观察记录在 local-review-followup-01.json；没有新外发、没有创建正式视觉转写缓存、没有强制修改 readiness。p40 不可读例题、p44 旧转写失败及印刷答案差异继续保留，不以局部页图核查冒充已解决。

建议先在独立实施范围内处理：人类已确认澄清的有效状态如何进入后续输入；章节容器节点和非必需例题缺口如何区别于所选考核知识证据。不得将未核实内容直接 supported，也不应通过反复分析弥补确认状态的产品问题。这些修正尚未实施。

### 本地预检、验收记录与本次验证

新本地预检 analysis-human-confirmed-preflight.json / analysis-human-confirmed-scope.json / selection-human-confirmed.json 绑定 revision 4 和新真实回答，context hash 826fce3f30dd7e14dc35a540156a0edcd939334559aa1dad62eb13dfb557a0c8；仍为同 22 页/11 份转写，无新页图。execution_authorized=false；未提交第二次分析。旧一次授权已经执行，不能复用为不限次数。不要把仅本地准备的预检说成已外发或已获准。

本地 E1 收集器追加 var/evals/round1/E1/42e12a50-f94f-4e8e-8950-53da870058ab/record.json，包含原分析、原转写及本次分析，保留独立 analysis-followup-<task-id> 绑定，不覆盖原分析。收集器当前将 needs_info 汇总为 failed；这是“未通过验收”的记录口径，真实 Task 仍 needs_info，不是 API 失败。本条累计 usage 93,759 包含之前 E1 起步调用，不能全部算成本次（本次仅 17,677）。

人类确认：analysis-followup-01-human-approval.json；提交：analysis-followup-01-task.json；实际用量/时间：analysis-followup-01-observation.json；本地视觉与服务核对：local-review-followup-01.json。以上均在被忽略的 var/evals/round1/E1/，不推送私人材料。

本次无产品代码变化，未重跑原 36 项或全库，不将此前测试冒充本次执行。实际 Django check 0 issues；web / 与 API /api/v1/session 均 200。最初误探 /api/session 的失败保留记录，正确路由随后确认正常。数据库核对调用数 209，0 活动任务，E1 CourseVersion 数量 0。没有 E1 规划/生成/Paper/双 PDF，端到端验收仍未完成。R1/R2 不重复执行，R3–R6 不启动。

本次服务保留运行，未重启或安装依赖。git diff --check 在提交前执行。接手应以本节为 E1 最新状态，不再等待已经收到的人类偏好确认；后续真实调用仍需绑定实际更新的精确范围及次数。

## E1 历史检查点：本地准备后外发曾被自动审批拒绝

E1 原始真实分析成功状态和 22 页范围保留。此前草稿有一项练习惯例选择。助手发出选择问题后尚未收到回复，先按已说明的可修改临时默认保存为：
“使用标准数学定义并注明资料差异；保留原文及疑点；不复用不可读公式或不一致答案行。”

该声明明确注明由 Codex 为本次开发验收选择、尚未获用户单独确认；source 也标为 Codex provisional development-acceptance convention。它不是官方事实、老师纠错或已确认的用户永久偏好。E1 当前本地草稿 revision 2，新增声明尚待分析，不存在新的课程确认版本。

仅准备了同 22 页文字、11 份已有有效转写及既有范围声明/临时设置的后续分析预检：
- context hash：6dc34c33b2918ca9d1ccf73b8bf75c1ef72065bf0fec1e93ab13c5d6c3cf6805。
- 文件：var/evals/round1/E1/analysis-followup-01-preflight.{json,md}；selection-followup-01.json；analysis-followup-01-scope.json。
- 无新页图；p40、p44 的视觉缺口保留。
- 拟官方 Responses / gpt-6.1-sol / store:false，正常一次分析及计数；单次 300 秒、任务 900 秒，未知结果不重放。

自动审批在进程执行前拒绝该提交，明确原因是：用户只要求继续 E1，尚未授权将助手自行新增且未确认的临时约定具体外发。因此没有新增 AnalysisGrant、E1 模型任务或调用。没有通过其他命令/输入变体绕过拒绝，已发送上述精确范围的确认请求。E1 后续分析、确认、规划、题答和双 PDF 均等待用户回复；不得宣称完成。

## 本次代码与验证

- snapshots.py：current_blueprint 的验证使用 course_projection，支持已显式迁移的旧课程及 v2 配置确认/冻结，不改旧版本内容。
- records.py：明确统计 skipped，与失败和未执行分开。
- collect.py：澄清后分析使用独立 analysis-followup-<task-id> 绑定，保留首轮分析绑定不覆盖。
- 测试：扩展旧版本确认/冻结覆盖，新增显式跳过和多次分析保留测试。

实际命令：

~~~powershell
& .\.venv\Scripts\python.exe scripts/test_batch5_backend.py -c pytest.ini tests/test_topic_generation_config.py tests/test_generation_snapshot.py tests/test_planning_coverage.py tests/test_eval_accounting.py -q
& .\.venv\Scripts\python.exe scripts/audit_generation_task.py 828c1c21-a550-4c55-b299-a7052020785a
& .\.venv\Scripts\python.exe backend/manage.py check
~~~

最终定向 36 passed / 14.17 秒；旧版本回归首次先复现 TOPIC_OUTSIDE_VERSION，单行修复后 25 项子集通过。跳过统计单独 10 passed / 9.13 秒，最终合并 36 项包含其覆盖，不相加冒称全库。Django check 0 issues、git diff --check 通过。未重跑后端全库、前端构建或其他未相关测试。

离线 audit 复现唯一未检查的核心数学项，候选/报告 hash 正确，无新模型调用。Playwright 对实际失败任务检查：3 题/8 小问与修复版可读；答案主动打开后 8 个答案渲染，0 KaTeX 错误；刷新保留任务且答案关闭；无发布/PDF入口。0 JS 错误、0 业务写入；调用数保持 207。已查看题面截图。没有 PDF 可做新页图验收。

## 页面、证据和接手边界

- [R1 真实补测及已保存题答](http://127.0.0.1:5173/tasks/828c1c21-a550-4c55-b299-a7052020785a)。
- [E1 课程草稿](http://127.0.0.1:5173/courses/1aeae0e0-c154-4dae-b3e6-fa9b214840d7/profile?topic=2948d0da-c723-4cea-bb6b-386d0be37caa)。

私有证据在 var/evals/round1/R1-retest-01/：model-blueprint.json、confirmed-blueprint-final.json（保留初始 confirmed-blueprint.json 供对照）、generation-preflight-v2.{json,md}、generation-submission.json、live-observation.json、final-candidate.json、independent-candidate-review.json、browser-check.{py,json}、task-*.png。补测记录 c792acc7-bd12-4f63-a79a-001306359289；原 R1 与 R2 skipped 记录保留。额外离线审计 var/generation-audit-828c1c21-a550-4c55-b299-a7052020785a.json。

本次运行前调用记录 188，结束后 207；0 活动业务任务；web/API session 收尾均 HTTP 200。API/worker 已在空闲时加载修复，web/本地 PostgreSQL 保留。无新依赖或迁移；原材料和历史成果未移动、删除或覆盖。用户其他文档/课件不处理、不提交。

历史检查点下一步曾为等待 E1 精确外发确认；该确认及一次分析现已执行，见上方最新 E1 状态。没有新的明确指令，不再运行 R1 第二次补测。第一轮完整验收未完成，没有进入第二轮。
