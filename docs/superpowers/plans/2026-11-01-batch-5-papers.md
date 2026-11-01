# 第五批 Task 9–10：保存练习、主动导出与恢复

> 执行方式：本会话原生实施；用户已于本会话批准第五批及下述交互变更。

## 已确认变更
生成和必要核验成功即冻结题答并保存到 Papers。现有任务页仍可看题并主动开答案；答案区域下方的 Generate PDFs 一次提交并跳转 Papers 详情。未点击导出属于正常的 not_generated 状态。两份 PDF 都可用才标 pdf_ready，但 PDF 失败不撤销题答成功。旧 PRD/技术方案中的自动首次导出及全任务成功口径以本次决定为准。没有独立继续核验入口。
运行明细默认折叠；当前阶段、失败/连接提示、取消始终可见。

## 实施
1. 保存第四批 generation-v6 独立基线；既有成功任务 d5a7434f 作为真实样本，不重新调用模型。
2. 新增 backend/app/papers/{models,schemas,reader,publication,api}.py 和迁移。
   ContentVersion 一对一绑定 CandidateVersion，保存不可变内容、题目/答案投影、课程/结构摘要和 hash。
   Paper 一对一绑定原生成 Task 和内容；PDFArtifact 唯一 (content,kind)，含 bytes hash、页数、私有相对路径。
   finish_candidate 在同一事务冻结与成功；历史成功结果通过显式 backfill 命令导入，GET 不写库。
3. Task 9：题卷/答案独立 API，列表 cursor 分页、权限，关联原任务与来源；frontend/src/features/papers/{PapersPage,PaperPage,ExportPanel}.tsx。
   当前 CandidatePreview 复用阅读层，PaperPage 只读固定 candidate；显式答案行为保持。
   Generate another 携带冻结配置，Generate 页显示当前版本差异并由用户保存/重规划/确认，不能自动生成。
4. Task 10：papers/{export,render}.py、打印模板及 CSS、export_paper_one 命令。
   submit_export 锁 course→paper，幂等记录与队列同事务；一次只运行该 paper 的一个导出任务。
   每份文件至多一次自动重试；保留完成文件，重试使用原内容。120 秒导出限额，未知模型不会重试（导出不调用模型）。
   worker checkpoint、执行代次、取消、发布在同一锁序；PDF 写不可变路径，验证后数据库登记；全部完整才发布 exports_ready。
   Chromium 本地离线字体/KaTeX，不请求外网；公式/素材错误明确失败。
5. 修改 TaskPage：运行明细折叠，错误/取消在外；成功候选下面 ExportPanel；启用 Papers 导航。完善 API 契约、README/交接及实际验证记录。

## 关键验证（拟执行）
- backend/tests/test_papers.py：必要检查 gate/哈希、默认答案与资产隔离、课程变化旧卷不漂移、他人404、分页、一次冻结。
- backend/tests/test_paper_exports.py：第二份失败/重试零模型同版本/已成功 hash 不变、取消/过期代次、并发提交/唯一发布、丢失文件、重启恢复。
- backend/tests/test_paper_render.py：真实 Chromium 渲染两个 PDF，长公式/表格/图/答案隔离、页数与版本。
- frontend tests：主动答案、导出按钮独立于答案展开、明细折叠、失败提示可见、轮询及刷新不 POST。
- 真实成功题答网页及两个 PDF，逐页 PNG 视觉核对；实际浏览器检查桌面/窄屏、下载、历史和刷新。
- 使用随机隔离 PostgreSQL 测试库；项目 venv pytest；pnpm frontend test/typecheck/build。测试禁真实 API。
- 数据证据与截图存 var/，源材料保持不动。更新本计划实际进度，不把合成故障当真实内容验收。

## Review Focus
1. 默认阅读数据/图注不能泄漏答案：隔离投影及网络请求测试。
2. PDF 失败不使题答失败，两个文件有独立状态：第二文件失败测试。
3. 取消与旧 worker 晚到不能发布：事务竞争与 epoch 测试。
4. 导出恢复不重复历史、不改冻结内容：hash 与调用次数断言。
5. 来源失效/课程更新/配置复用不使用当前数据覆盖历史：快照和差异测试。

## 完成条件
P0-10/11/12 的本批约定通过；真实既有题答可读且可导出两个实际文件；服务可操作；明确未实测与第六批边界。本批不执行六次真实模型验收。


## 实施结果（2026-11-01）

Task 9–10 已完成。实际测试集中于 backend/tests/test_papers.py（包含原拟 test_paper_exports.py 的导出测试）、test_paper_render.py、前端 ExportPanel/TaskPage/CandidatePreview 测试及 scripts/test_batch5_browser.py。复用 CandidateReading，未新增重复的数学阅读组件。迁移为 0001_initial.py、0002_immutable_content.py；命令为 backfill_papers 与 export_paper_one。

后端全库 287 passed、后续分页/并发与最终渲染 17 passed、前端 23 passed；真实既有题答生成两个 PDF，5/16 页、9.831 秒，模型新增 0。完整证据和未验证边界见 [验证记录](../../batch-5-validation.md)。未进入 Task 11–12；原拟命令以验证记录中的实测为准。
