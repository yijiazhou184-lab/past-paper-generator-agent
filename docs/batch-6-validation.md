# 第六批实施与验证记录

更新：2026-11-02。依据最新第六批及 Topic 工作区计划，范围为 U1–U3、Task 11/12、R1–R6 与额外 E1。U4 跨 Topic 混合生成不属于本批。

## 状态

- U1 目录、材料归属及旧记录投影已实现；隔离后端测试 8 项通过。
- U2 Materials 页面已接入目录/筛选/多重归属/上传前归属/来源 URL 保持；前端定向测试 4 项通过，真实页面只读浏览器检查通过。隔离多 Topic 写入及失败状态检查继续补充。
- U3、Task 11/12 与真实验收尚未完成。
- 本批当前没有真实模型调用；R1–R6/E1 均未执行，不以旧成功样本或 fixture 补数。

## 已执行检查

1. 随机 PostgreSQL 测试库：scripts/test_batch5_backend.py tests/test_topic_catalog.py tests/test_material_topic_assignments.py tests/test_topic_legacy.py -q，8 passed（12.31 s）。覆盖身份/幂等、owner 隔离、CAS、物理页范围、同文件多归属、shared/unassigned、跨课程引用拒绝及旧 payload/hash 不变。
2. 前端 MaterialsPage.test.tsx / TopicPicker.test.tsx，4 passed。先确认缺组件时失败，再实现并复跑。搜索不清空所选 Topic；来源翻页/关闭保留筛选；追加链接保留旧页段。
3. OpenAPI 生成及验证、生成 TypeScript 契约、pnpm --dir frontend typecheck 通过。
4. scripts/test_topic_materials_view.py：真实主课程 11 文件 / Topic 2 直接关联 5 文件；显式包含公共材料后 11 文件；搜索、源版本/物理页、刷新关闭恢复；1440/1024/768/320px 无页面溢出；无业务写入和 JS 错误。私有截图、结果在 var/screenshots/batch6-materials-* 与 var/batch6/materials-browser.json。
5. 本地新增迁移已应用；未修改已有迁移。迁移前数据库备份 var/batch6/before-u1.dump。迁移及映射登记后：原 2,438 条业务记录 hash 和 25 个材料/PDF 文件 bytes 不变，ModelInvocation 仍 173。

## 真实旧数据登记

主课程 68caa35d-6e08-42d7-84bd-70a23e369b1f 的 Topic 2 名称依据 Lecture summary 物理 p1 正文；已确认 v1/v2 的 8 个知识身份均核对。新增独立 LegacyTopicMapping，不回写旧冻结 payload/config/hash。

5 个直接归属材料为 Lecture 2、Lecture summary、seminar、additional questions and answers、Math Background。其余已导入的复习、旧 mock、Lecture 1 范围页及 coursework 归入 Course-wide；页段只取旧确认清单已有证据。登记不表示新的 API 授权或官方考试事实。精确本地 ID/映射在 var/batch6/legacy-topic-mapping.json，一次性脚本在 var/seed_batch6_legacy_topic.py；不作为通用产品默认。

## 页面与服务

Materials：<http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/materials>。API/worker/dispatcher/web 均由 scripts/local.py 管理，复用项目现有服务。U3 完成前，旧 Profile/Generate 仍使用原有路径，不能宣称新增 Topic 分析已完成。

## 未执行与后续

- U2 写入/错误状态 fixture，U3 按 Topic 分析、确认、配置与冻结摘要。
- Task 11 集成/诊断与 Task 12 记录工具、rubric、精确预检。
- 新真实分析/规划/生成需在预检准备好后集中确认数据范围；没有使用历史授权扩大外发。


## 2026-11-02 稳定实施结果（覆盖上方早期进度）

U1–U3 的本地能力已实现，Task 11 的核心集成与恢复检查完成。Task 12.1 的记录/预检/收集/审阅绑定/汇总工具已实现；manifest/rubric 的用户冻结确认仍待回复。R1–R6 和 E1 的真实分析、组卷及内容验收尚未执行，不能宣布第六批或第一轮验收完成。

### 实际验证

- 完整隔离后端：318 passed / 454.37 秒。使用随机 PostgreSQL 测试库，删除真实密钥并阻断未 mock 的官方 API 传输。
- 全库首次运行是 306 passed / 1 error，错误为 Windows 数学子进程在 poll/kill 之间退出导致 PermissionError。已修复：只在 wait 证实退出时接受该竞争；仍运行且不可终止时保留错误。上面的 318 是修复后的完整重跑。
- 随后补充实际保存题卷的验收收集测试和数据库临时故障处理：diagnostics_redaction、topic_api、eval_accounting 合计 11 passed / 22.41 秒；其中 eval accounting 最新 7 项均通过。未将这个子集相加冒称完整全库数量。
- 前端 9 文件 / 31 tests passed；生产 build 与 typecheck 通过。
- Django check 0 issues；makemigrations --check --dry-run 无变更；git diff --check 无空白错误。
- scripts/test_round1_flow.py --fixture：独立 owner/course；Topic B 筛选与显式共享；未分析章节为空；A 保存失败后保留编辑并切 B，返回恢复保存；B 独立确认；配置 v2；参数改回也不恢复确认；真实产品任务/刷新/主动答案/主动导出到 Papers；同内容两个合成 PDF 可下载。
- scripts/test_round1_views.py --fixture：Materials/Profile/Generate/Task/Paper 五视图，各 1440/1024/768/320px 无页面横向溢出，键盘焦点可达；合成网络失败可重试，合成超时错误在折叠详情外；全程未请求答案或模型。
- scripts/test_topic_material_links.py：另一个独立 fixture；重复上传后显式追加 Topic B，保留 A 和原文件/版本；两标签归属 revision 冲突时保留输入、比较服务器、明确采用新 revision 后保存。重跑通过。
- 浏览器写入测试中曾遇到 PostgreSQL/Windows 错误 10024（新连接 socket/process 资源暂不可用），不是归属判断冲突本身。接口现返回脱敏、可重试 DATABASE_UNAVAILABLE / HTTP 503；纯单测验证不泄漏驱动消息/密钥/全文，不依赖故障中的数据库写日志。单独浏览器重跑正常。未修改系统资源限额。
- 旧 2,438 条记录的原字段及原 25 个材料/PDF 文件哈希再次保持一致；新加的 topic_state / topic_ids / confirmation_fingerprint 元数据列不作为旧内容字段比较。模型调用总数仍 173，新增真实调用 0。

### 能力与测试证据映射

| 能力 | 主要证据 | 首轮相关要求 |
|---|---|---|
| 章节身份、多重材料归属、固定版本/页段 | topic_catalog / material_topic_assignments / topic_legacy；真实 Materials 浏览 | AC-01-03、AC-03-02、AC-06-03 |
| 动态分析、来源权限、其他章节人工编辑隔离 | topic_analysis / topic_api / 原 course_execution 回归 | AC-04-02/03、AC-05-03 |
| 局部审阅/确认、共同事实影响、切换前保存 | topic_confirmation / TopicProfile / useDraftSave / flow fixture | AC-06-01/03、AC-11-02 |
| 配置 v1/v2、知识树、结构失效、旧版新规划 | topic_generation_config / generation_snapshot / planning_execution / TopicKnowledgeSelector | AC-07-02、AC-10 的首轮部分 |
| 取消/epoch/唯一保存、未知结果、PDF 失败恢复 | round1_recovery、task_lifecycle、generation_review_budget、papers 全库；flow | P0-12、AC-14-03 |
| 诊断脱敏、未知 usage、记录与统计 | diagnostics_redaction / eval_accounting；收集实际 fixture 题卷 | AC-14-04、NFR 计时口径 |

视觉检查覆盖实际渲染截图及四屏宽自动断言。新增真实题卷尚不存在，因此 R1–R6/E1 的逐题质量及全部 PDF 页图检查仍未执行。之前第五批同字节 PDF 的视觉记录保留，不能算本批新样本。

### E1 本地准备与范围

E1 为独立课程 1aeae0e0-c154-4dae-b3e6-fa9b214840d7；Topic 1（2948d0da-c723-4cea-bb6b-386d0be37caa）：Functions of a single variable: Limits and continuity。本地导入 Lecture 1、Topic 1 seminar、Topic 1 additional questions and answers，解析均 succeeded。Lecture 1 已有同哈希解析缓存可复用，其他两份本地解析约 83/73 秒；不复用 Topic 2 草稿/知识/蓝图/答案。

选定 22 个物理页，聚焦有限点极限、连续性及介值定理；现有 value / limit / equivalence 数学检查与 explanation/proof 适配。Lecture 物理 p41 对应印刷页 42，已渲染核对。12 页公式需要页图转写。精确清单在 evals/round1/e1-materials.json 和私有 var/evals/round1/E1/；未发送。

E1 页面已实际操作至 Prepare sending scope：22 页、12 页转写缺口显示正确；Start analysis 在未授权时禁用；只有一次本地预检 POST，未启动模型任务。用户的 All lecture content 继续作为 user_statement / unverified，不提升成官方公告。

### 验收工具与可运行命令

以下命令已经实现；只有列为实际执行的预检、fixture 收集和报告运行过，真实 execute 未运行。

~~~powershell
# 默认纯本地规划预检，不保存/修改产品配置，不发模型请求
& .\.venv\Scripts\python.exe evals/round1/run.py --run R1 --preflight

# 经审阅授权后才可执行；grant-ref 必须是当前 context 的已有授权 ID
& .\.venv\Scripts\python.exe evals/round1/run.py --run R1 --stage planning --execute --grant-ref "<reviewed-grant-id>"

# 后续生成必须绑定正常产品中已确认的蓝图和当前精确生成预检
& .\.venv\Scripts\python.exe evals/round1/run.py --run R1 --stage generation --execute --grant-ref "<generation-grant-id>"

# 从已经运行的任务只读收集；新增 JSON 记录，不改写业务结果
& .\.venv\Scripts\python.exe -m evals.round1.collect --run R1 --task-id "<task-id>"
& .\.venv\Scripts\python.exe -m evals.round1.report
~~~

R1–R3 复用同一蓝图并记录新的 history；R4–R6 按矩阵分别确认。没有授权不能 execute；未知结果不自动重放；原位置绑定其他任务会拒绝，补跑另起 retest ID。收集器保存各阶段提交/起止/事件、调用和实际 usage 或 null；生成与导出系统耗时用墙钟区间，导出前等待单列。分析中的用户等待缺少明确事件时保留 null，不能据间隔武断归为系统耗时或零等待。

质量审阅必须绑定实际 content_hash 并覆盖全部作答单元。fixture-browser-flow 已用真实保存的合成题卷和两个合成 PDF 运行收集命令，状态 completed / mode fixture，不占 R1–R6，也不自动内容通过。实际价格及费用没有核实，保留 unknown。

### 仍需推进

1. 回复 var/batch6-real-preflight.md 的 A/B 范围及 rubric/审阅者确认。它目前只申请 R1 规划、E1 12 页转写及同 22 页派生分析，不授权七次题答生成。
2. R1 规划后按矩阵审阅/编辑/确认真实蓝图；E1 转写后重建并核对分析预检，再执行一次新课程分析及必要澄清。
3. 准备 R1–R6/E1 各次实际生成预检，按已批准的数据范围执行；逐题审阅、导出及全页视觉检查、真实 token/耗时/费用统计。
4. 完成 12.4 总结前不宣布本批退出。U4 混合章节、完整模拟卷及更广科目仍属后续轮次。


### 收尾补充

- 原始来源的浏览器 Back/Forward 补验通过：重新打开同一物理 p2，再前进恢复 Topic/search。
- scripts/test_topic_material_response.py 实际扣住 Topic A 的旧响应，切换 B 后才放行；B 列表不被覆盖，全程 0 业务写入。
- 局部确认增加对人工编辑 UserStatement 的完整冻结，并使用本次审阅上下文重新校验证据引用。保留原分析 statements 以区分 AI 当时看到的内容与用户后来编辑的内容；不存在的证据不能确认。topic_confirmation / course_drafts / topic_api 最新定向 13 passed / 24.89 秒。此补充发生在 318 项全库之后，没有声称已经重新跑过增加测试后的整个库。


## 2026-11-02 A+B 真实起步结果（当前状态）

用户已确认 A+B 与验收口径。本次 R1 规划失败保留；E1 精确 12 页转写 11 有效/1 来源 hash 失败，同 22 页一次分析成功保存 revision 1 新草稿。未执行 R1–R6/E1 题答生成、新 PDF 或逐题质量验收。上文“待授权/新增调用 0”是此前检查点。

实际 14 模型+1 计数，95,589 tokens，记录总数 188；无未知或自动重放。补齐验收收集器逐页失败与阶段结果，test_eval_accounting.py 实际 9 passed / 20.67 秒；真实页面 6 组只读检查通过。原材料和 PDF 25 文件哈希保持，旧冻结记录保持；R1 正常保存配置有一条已授权可变 GenerationDraft 更新。没有重跑全库测试。

完整任务、输入 hash、逐阶段用量和耗时、错误原因、本地矩阵提案、课程草稿与真实/未执行边界见 [A+B 实测记录](batch-6-live-start-2026-11-02.md)。R1 原位置标为规划失败，R2–R6 未执行，E1 awaiting_generation；第一轮完整验收未完成。


## 2026-11-03 局部契约更新：知识覆盖由小问汇总

用户已确认取消主考/辅助及固定逐大题知识分配，模型只填写小问考核知识，程序派生大题/整卷覆盖。存储仍为 blueprint-v2；新 provider 契约及 prompt/hash 独立版本，编辑保存重算，冻结历史严格读取。当前验收 manifest 的逐题分配已取消，整卷知识及数值矩阵保留。原失败/授权/历史快照不改。

定向回归 61 passed / 20.87 秒，Django check、git diff --check 通过；原 R1 响应离线通过新覆盖校验，原文件和失败状态保持。调用记录仍 188，新增真实调用 0。没有重启服务、提交业务任务或执行 R1–R6/E1。测试路径、一次夹具时序故障修正和未执行边界见 [局部实施记录](superpowers/plans/2026-11-03-planning-part-coverage.md)。


## 当前验收：R1 补测未通过，R2 已跳过，E1 等待精确外发确认（2026-11-03）

用户要求 R1 再生成验证一次、跳过 R2、继续 E1。本次 R1 新规划成功，按正常入口确认 3 题/8 小问/30 分结构；真实生成任务 828c1c21-a550-4c55-b299-a7052020785a 经一次 Q2 修复后仍 failed。最终 58 必要项 56 pass、1 not_checked、1 inconclusive：Q2 根式驻点字符串不符合检查器数字字面量约定。题答已保存但未发布，无新 PDF；不是 token 超限。生成 343.599 秒、203,896 tokens；连同规划共 222,908 tokens，新增 10 模型+9 计数，记录总数 207。

R2 已按用户要求 skipped，汇总与失败/未执行分列。E1 已本地保存明确标注为 Codex 临时默认的练习约定，草稿 revision 2；自动审批拒绝把该新增未确认约定随 22 页材料外发，后续分析未启动。精确预检 6dc34c33… 的确认问题已发出，等待用户回复；不得绕过或视为已同意。完整预检见 var/evals/round1/E1/analysis-followup-01-preflight.{json,md}。

补齐旧确认版本映射入口、skip 统计及分析 followup 独立绑定；最终定向回归 36 passed / 14.17 秒。R1 离线审计和实际浏览器查看/主动答案/刷新检查通过，0 新调用/JS 错误/业务写请求；Django check 0 issues。未做新 PDF 检查。

下一步：等待 E1 精确确认后继续原 22 页分析/确认/规划/生成；本次 R1 不自动再跑。根式点的受限类型化常量表示仅为后续改进建议，未实施，未放宽必要 gate。R3–R6 未执行。服务保留运行、0 活动任务，无依赖或迁移变化。详见 [本次真实验收记录](batch-6-r1-retest-e1-2026-11-03.md)。


## 当前验收：E1 获准分析已完成，仍需课程草稿处理（2026-11-03）

用户已明确确认“使用标准数学定义，并注明资料差异”，并允许按 6dc34c33… 精确快照运行一次 E1 后续分析。该次调用已执行：task fd64ee51-0e51-44ce-9ff8-0f1ae39d9c31 返回 needs_info；API/解析正常，4 个知识节点为部分支持，没有 token 超限。官方计数 10,771；实际输入/输出 10,771 / 6,906，合计 17,677 tokens；模型 78.750 秒，系统墙钟 84.611 秒。新增 1 模型+1 计数，调用记录 207→209；没有自动重试。

获准输入仍包含旧的“Codex 临时、用户尚未确认”说明，模型据此重复提出惯例选择。这是确认信息与冻结输入未同步的问题，不应再次要求用户选择。未改写获准快照或历史响应；已通过正常澄清回答保存实际人类确认，明确取代临时说明，当前草稿 revision 4。该确认是练习偏好，不是官方事实。新精确预检 826fce3f… 仅本地准备、execution_authorized=false，未再次外发；本次一次分析的授权已使用。

E1 暂无 CourseVersion、规划、题答或 PDF。章节总节点、连续性、最值存在性、介值/不动点四项仍 partial；当前整章确认会阻塞全部 partial 节点，新澄清也触发重新分析。下一步应先处理确认信息同步，以及“章节总节点/个别不可读例题”与实际练习所需知识的区别，保留真实缺口，避免盲目重复付费调用；未实施范围放宽或绕过 gate。Lecture 1 物理 p38（印刷 39）已做本地页图核对，明确写在定义域上连续；未创建正式视觉转写记录、未发新页图。

R1 一次补测仍 failed（必要数学检查不支持根式点字符串）；R2 保持用户指定 skipped；R3–R6 未执行。本次仅运行真实分析及本地核对，没有新增产品代码/依赖/迁移，也未重跑全库或浏览器端到端。Django check 0 issues；web 和实际 API /api/v1/session 均 HTTP 200，0 活动任务。完整记录及前次代码测试见 [R1/E1 实测记录](batch-6-r1-retest-e1-2026-11-03.md)。原材料、原结果和用户未跟踪文件保持。


## 2026-11-06 新版真实 R1/E1 运行（最新）

R1-retest-02 和 E1-retest-02 均完成真实题答、必要检查、独立八小问审阅及双 PDF。R1 58/58 必要 pass，题卷/答案 4/10 页，一轮真实 Q2 修复；E1 34/34 必要 pass，题卷/答案 3/7 页，无修复，已确认新 CourseVersion 1。总 15 模型+15 计数（含一次已知 Schema 400），277,407 tokens；调用记录 239。R1 复用三题旧初稿后重新核验/修复，E1 首次全新生成；两者不可当作同等新题生成基准。

运行中修复严格分析输出 schema，48 项离线回归通过；验收记录的已确认分析关联修正，13 项通过；Django check 0 issues，真实浏览器 9 组通过，24 页 PDF 查看完成。保留可选未确定项、分页小问题、超过 120 秒的性能缺口和原失败。原 R1 名额仍 failed，R2 skipped，R3–R6 未执行，未进入第二轮。

精确任务/输入/用量、初次 E1 计数失败及继续经过、独立内容审阅、文件 hash、实际测试及后续边界见 [本次实测](round-1-live-r1-e1-2026-11-06.md)。上文“真实新增 0”“E1 无确认版本/PDF”均属之前检查点。
