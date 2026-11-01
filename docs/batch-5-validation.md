# 第五批实施与验证记录

日期：2026-11-01。范围：第一轮第五批 Task 9–10。用户已授权实施及本地服务操作；本批使用先前真实成功的题答，**没有新增真实模型或官方输入计数请求**。第六批尚未执行。

## 实际完成与用户入口

- 成功生成在同一事务内通过必要检查 gate、candidate/report/snapshot hash 校验，唯一保存 Paper 与不可变 ContentVersion。模型候选、检查报告、课程与蓝图来源保持旧版本；两个迁移已应用，数据库 trigger 拒绝修改已冻结内容。
- 原任务页保留题目和主动开答案；答案区域下方增加 Generate PDFs，不要求先展开答案。点击一次提交独立 export 任务并跳转对应 Papers detail。Run details 默认折叠，包含总耗时、时间线及调用明细；当前状态、失败、取消和恢复入口保持可见。
- Papers 列表、详情、带签名 cursor 分页；显示实际题数、分数、课程版本与真实/fixture 标记。只看题目接口不含答案和答案资产；Show answers 才加载答案及详细报告。
- Generate another practice 先显示旧配置和当前课程版本，显式采用后仍需保存、重新规划及确认；不直接生成。新预检冻结最近 20 份已保存卷，按题向生成器提供至多 3 段、每段 1200 字符的相关题干参照。历史不是教学证据；本地查重仅比较规范化题干和结论，不能声称完整语义原创性判定。新一次生成不复用已经成功的整卷大题成果。
- 离线 Chromium + 本地 KaTeX/字体生成 A4 题卷和 mark scheme；不允许页面外连。长公式在安全分隔处重新排版，过宽且不能保持可读大小时明确失败；表格重复表头。内容版本、页码、难度未校准说明入 PDF。
- 文件独立保存并验证 hash/大小/页数；两份有效才完成导出。单份至多一次自动重试，进程恢复保留尝试预算，整导出限额 120 秒。失败重试复用成功文件，零模型调用；幂等、course/paper/task 锁、执行 epoch、取消和唯一发布继续适用。

实际文件：backend/app/papers/ 的 models、publication、reader、api、schemas、history、storage、render、export、templates/print.css、两份 migration 和 backfill/export 命令；复用 core 任务队列与 generation reader。前端 features/papers、TaskPage、CandidatePreview、GeneratePage、GenerationLaunch；契约同步到 contracts/openapi.yaml 与 frontend/src/api/generated.ts。启动脚本就绪检测已接受 batch 5。

## 真实既有内容与最终输出

| 项目 | 本次核对 |
|---|---|
| 原生成任务 | d5a7434f-4d05-4f93-81a7-c4a002b1d358 |
| 候选 | d07e1809-4ae3-4638-8394-8729d7cd3025 |
| 原生成结果 | 75 个必要检查通过；4 大题、15 小问、60 分；课程 v2 |
| Paper | 45f3f96e-3478-475c-b839-d85ca7e1c2dd |
| ContentVersion | 4005290e-c457-4bda-beb7-e6181fa9c481 |
| 最终 PDF 任务 | 7e9b7fd7-7d22-4e12-bda4-c6de0c87e164，succeeded |
| 最终导出耗时 | 9.831 秒（受理至完成，含排队）；chromium-katex-v5 |
| 题卷 | 5 页，109,427 bytes，SHA-256 d3265ac6ce84317aeb66bff03847d43a6285c5a9f2b8ae0149b1e2da86743b30 |
| Mark scheme | 16 页，208,030 bytes，SHA-256 c99c7e32941396afc30cc8e15b402d48ca8856f9ae1114615bd9e8f5145e32ec |
| 模型调用表 | 本批开始/结束均 173 条，新增 0（包含原有计数请求记录） |

原生成自身约 335.9 秒处理、337 秒受理至完成；10 次模型与 10 次计数请求，168,865 input + 47,915 output = 216,780 tokens。它是此前用户在网站运行的真实结果，本批读取并导出，不将它写成本批重新运行。两分钟目标仍未达标。

执行 backfill_papers 将 10 个原有成功任务保存为 Paper，其中包含明确标记的合成 fixture；不是 10 次真实验收，也未改原任务、候选或报告。排版调试中的导出任务和失败记录保留；严格版宽检查曾拒绝过宽答案公式，修正排版后对同一 ContentVersion 完成最终导出。没有用重出题掩盖导出失败。

入口：
- [Papers](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/papers)
- [真实题卷与 PDF](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/papers/45f3f96e-3478-475c-b839-d85ca7e1c2dd)
- [原成功任务](http://127.0.0.1:5173/tasks/d5a7434f-4d05-4f93-81a7-c4a002b1d358)

## 实际检查

| 检查 | 结果及边界 |
|---|---|
| 后端全库 | 287 passed / 246.54 秒；随机隔离 PostgreSQL 测试库，阻断真实 API |
| 回归发现与修复 | 初次 282 passed / 5 failed，均因旧来源查重输入没有 answers；只在存在历史卷时读取答案结论，修正后全库通过 |
| 最终 PDF/分页/竞争补充 | 17 passed / 45.73 秒；包括全库之后新增的两项分页和并发唯一发布测试 |
| 最终历史 ID 与旧来源兼容回归 | 26 passed / 62.37 秒；compared_paper_ids 对应实际 Paper ID，ContentVersion ID 单独保留 |
| 前端 | 23 passed / 5.59 秒；typecheck 与生产 build 成功 |
| Django | check 0 issues；makemigrations --check --dry-run：No changes detected |
| 契约 | spectacular --validate 与 OpenAPI TypeScript 生成已成功 |
| 真实浏览器 | 8 组检查通过；0 JS 错误，登录后 0 写请求；答案默认不请求，主动打开 15 个答案；两份文件实际下载；刷新恢复同卷；1024/768/320px 无整页横向溢出；再次练习不自动提交；运行明细折叠 |
| PDF 视觉 | 最终全部 21 页转图检查，另放大检查最宽公式；未发现公式裁切、表格丢失或题卷混入答案。长 80 行表/图/SVG/选答布局属于合成渲染测试，不能当作真实跨学科质量验收 |
| 服务恢复 | 无 active task 时重启 API、worker/dispatcher，再运行浏览器检查，同一 Paper/PDF 可找回；前端持续运行 |

本次实际执行命令（根目录 PowerShell；测试脚本内部进入 backend，所以参数使用 tests/）：

~~~powershell
& .\.venv\Scripts\python.exe scripts/test_batch5_backend.py -q
& .\.venv\Scripts\python.exe scripts/test_batch5_backend.py tests/test_papers.py tests/test_paper_render.py -q
& .\.venv\Scripts\python.exe scripts/test_batch5_backend.py tests/test_papers.py tests/test_generation_sources.py -q
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
& .\.venv\Scripts\python.exe backend/manage.py check
& .\.venv\Scripts\python.exe backend/manage.py makemigrations --check --dry-run
& .\.venv\Scripts\python.exe scripts/local.py restart-api
& .\.venv\Scripts\python.exe scripts/local.py restart-workers
& .\.venv\Scripts\python.exe scripts/test_batch5_browser.py
~~~

脚本 test_batch5_browser.py 当前为本机保存真实结果的验收脚本，读取 Git 忽略的 var/batch5-browser-start.json（url 字段），不是新环境通用种子数据。重建环境与正常启动看 README。

## AC 覆盖与边界

- P0-10 / AC-10-01..03：实际双 PDF、同版本/主动答案、部分失败同内容重试；按用户已确认的独立 PDF 状态执行。
- P0-11 / AC-11-01..03 首轮子集：持久历史、读取归属、冻结旧内容、当前版本复核、有限历史查重；完整删除联动仍不在本批。
- P0-12 / AC-12-01..04：重复提交、取消前后竞争、旧 epoch、超时、丢文件和 worker 恢复，以隔离库合成故障验证；真实结果重启后可读。
- 未在本批再次调用真实模型，新增历史输入的 token/真实多次练习多样性须下一批检验；难度与作答时长仍未官方校准；六次真实验收与两分钟性能目标尚未完成。
- PDF 已通过渲染、文件打开/下载和页面检查，未做实体打印；不把此项冒称物理打印机验收。新环境完整安装尚未在第二台机器复现。
- 原材料、历史原型、旧失败任务保留。独立已有文档 docs/multi-course-compatibility-design-v0.1.md 不纳入本次实现。

私有证据（Git 忽略）：var/batch5-final-export.json、var/batch5-browser-validation.json、var/pdf-review-v5/ 全部页图、var/screenshots/batch5-*.png，以及 var/data/papers/4005290e-c457-4bda-beb7-e6181fa9c481/ 的 hash 命名文件。

排版接口依据：[Playwright page.pdf 官方文档](https://playwright.dev/python/docs/api/class-page#page-pdf)，查阅日期 2026-11-01；实际安装版本和渲染能力以本机测试为准。
