# 第一轮实施与验证记录

日期：2026-10-21。范围：**批次 1 / Task 1–2 本地功能**。用户已确认设计 §9.2 三项决定并授权实施，随后要求先完成第一批本地功能、稍后提供 API key。本记录不代表第一轮全部完成，也不代表完整 MVP 验收完成。

## 实际完成

| 项目 | 实现与证据 |
|---|---|
| 工程 | Django 5.2.18 / DRF 3.18.3、React 19.3.1 / Vite 7.3.7、PostgreSQL 17.11、Procrastinate 3.10.0；项目内 Windows 后台服务。Python / pnpm 锁文件已保存 |
| 持久任务 | Task、TaskAttempt、TaskEvent、Outbox、ErrorRecord、幂等记录；数据库行锁、课程活跃任务约束、epoch 防迟到写回、取消、失败诊断、关联重试、心跳和租约恢复 |
| AI 接口边界 | `ModelCallSpec` / `ModelCallResult`、输入输出 token 与调用预算；测试适配器必须标记 fixture；未接入真实网络适配器，默认 `not_executed`，未知 usage 为 null |
| 材料 | PDF magic/加密/大小/页数/课程总量校验；SHA-256 去重；多路径映射；显式替换新版本；原子私有存储；原件下载鉴权 |
| 解析与来源 | 真实 Docling 本地转换；固定材料/解析版本与物理页、块位置、解析内容 hash；原始页图；`EvidencePack` 固定分类 revision、关联与来源；任务输入匹配校验 |
| 页面 | Materials、来源面板、材料类型保存、答案关联保存/解除、逐文件上传结果、Task detail、取消/重试、原任务与来源 URL 刷新恢复 |
| 契约 | DRF 输出 schema → `contracts/openapi.yaml` → `frontend/src/api/generated.ts`；页面类型引用生成结果 |

入口：http://127.0.0.1:5173。运行方式见 [README](../README.md)。产品界面为英语，后续页面显示尚未可用状态。

## 真实材料结果

65 个原始路径重新计算 SHA-256，**0 处变化**。首轮选定 11 个唯一 PDF 的逐页证据共 **237 页**，全部完成本地解析；15 个原目录路径归到 11 份内容。浏览器重复上传测试额外登记了 mock answers 的文件名别名，因此应用中路径别名数为 16。

| 材料 ID | 页数 | 当前结果 | 本次成功处理记录 |
|---|---:|---|---:|
| M04 mock answers | 8 | succeeded | 41.86 s |
| M05 mock questions | 7 | succeeded | 44.22 s |
| M06 Topic 2 additional questions and answers | 8 | succeeded | 47.24 s |
| M14 Calculus revision | 15 | succeeded | 78.48 s |
| M15 Calculus revision questions | 9 | succeeded | 42.26 s |
| M32 Lecture 1 | 58 | succeeded | 122.50 s |
| M33 Math Background for topic 2 | 26 | succeeded | 69.89 s |
| M34 Topic 2 Lecture 2 | 57 | succeeded | 117.55 s |
| M35 Topic 2 Lecture summary | 19 | succeeded | 99.14 s |
| M46 Coursework 1 Brief | 7 | succeeded after retry | 35.55 s |
| M48 Topic 2 seminar | 23 | succeeded after recovery | 165.22 s，包括中断等待 |

耗时是 Task 的 `finished_at - started_at`，不含首次排队；M48 包含故障注入恢复等待。冷启动、权重加载和本机负载均影响数值。它们是材料解析实测，**不是生成两分钟目标的验收结果**。

本地详情在 `var/batch1-audit.json`：材料/任务 ID、hash、别名、页数、状态和风险页抽取。原始清单固定于 `backend/tests/fixtures/qm_inventory.json`；首轮子集在 `qm_manifest.json`，只含元数据，没有课程全文。

## 数学页核对及限制

本次查看了以下原始页图，并对照实际 Docling 输出。页图可读不等于抽取正确；未将任何页标为数学语义已通过。

| 物理页 | 观察 | 结论 |
|---|---|---|
| M34 p14 | 原页左右导数 -1 / +1 清楚；抽取语句读序紊乱，公式缺失 | 抽取问题；AI 必须同时使用原页或验证后的公式结构 |
| M34 p41 | 原页临界点 `2 ± √2`；文本变为 `2 + 2`，求导推导部分遗漏 | 根号及公式丢失，不能按纯文本继续推理 |
| M14 p5 | 原页是根号函数按定义求导的完整推导；本次仅抽出 “Lecture 2” | 实质内容未被文本覆盖；原页须进入后续局部视觉路径 |
| M33 p22 | 原页把两条指数/对数复合恒等式右端写成 1；抽取只留下标题 | 同时存在抽取缺失与源文疑点；不能自动纠正后宣称原文正确 |
| M48 p20 | 原页明确写着 “A WRONG proof / Find what has gone wrong”；抽取保留此标题但漏掉大部分推导 | 教学中的故意错误例，不能作为正确解答照搬 |

当前关闭 OCR / formula enrichment，不声称 Docling 已满足公式质量要求。全部证据保留 `needs_review`，解析报告显示 `MATH_REVIEW_REQUIRED`。本轮后续 AI①须在选定相关证据时加入原页；如果要采用公式增强，需单独测试其准确性及资源开销。该限制不妨碍材料/任务/编辑流程实现，但阻止把当前纯文本直接当成可信出题依据。

分类是内容关键词建议，可直接修正；例如 M33 暂为 Other，revision 文档可能被建议为 Lecture。这些结果没有被解释为官方材料角色确认。用户“全部 lecture”仅保存在课程的 `user_statement` 来源字段。

## 实际执行的检查

| 检查 | 结果与口径 |
|---|---|
| `python -m pytest -c backend/pytest.ini backend/tests -q` | **20 passed，26.62 s**；真实 PostgreSQL 测试库 + 构造 PDF/缓存 fixture，不调用模型 |
| 并发及队列 | 两线程同 key 得到同任务；冲突输入拒绝；outbox 重发产生重复消息但 claim 仅一次；旧 epoch 写入被拒绝；预算/截止执行 |
| PDF / 归属 | 重复别名复用、同名不同字节独立、替换后旧来源、缓存复用、物理页边界、跨用户 404、CSRF、分类冲突、答案关联归属及 revision、私有路径越界、冻结任务输入不匹配 |
| 模型边界 | 无适配器时不执行；fixture 不能假称 live；unknown usage 不记成 0 |
| `manage.py check` / `makemigrations --check --dry-run` | 无问题 / 无缺失迁移 |
| OpenAPI validate + TS 生成 | 通过，真实输出字段有 schema；retry 返回 202 |
| `pnpm --dir frontend typecheck` / `build` | 通过，生产静态构建成功 |
| `scripts/test_workspace.py` | **8 项通过**：本地会话及 11 份实物、分类弹窗键盘关闭、原始第 14 页及刷新、任务入口及刷新保留同一任务、搜索空状态、混合上传局部失败、390px 布局、无浏览器运行时错误 |
| 全部服务/数据库停止后重启 | 成功；重启后上述 8 项浏览器检查及构建通过，11 份材料与原任务仍可访问 |
| 真实 worker 故障注入 | 下述同一业务任务恢复成功；保留完整祖先/attempt 记录 |

测试命令需使用 README 所示 `.venv` 解释器。浏览器测试实际访问运行中的应用，未 mock HTTP；后端解析缓存测试使用明确的 Fixture 文本，真实 Docling 样本处理单独记录。没有声称所有计划中的测试文件名或“先红后绿”步骤均已执行；部分首轮检查在实现后补充，前端单元测试由当前浏览器集成检查替代，后续按交互复杂度补充。

截图：`var/screenshots/materials-desktop.png`、`source-desktop.png`、`materials-mobile.png`、`source-mobile.png`。原始 JSON 验证记录保存在 `var/browser-checks.json` 和 `var/recovery-check.json`，不提交真实课程页面。

## 保留的失败、修复与真实恢复

1. 依赖安装/数据库连接最初遇到沙箱临时目录或回环连接权限；在用户已授权的本地环境设置范围内使用获准执行方式完成。没有更改全局 Python，也没有展示凭据。
2. 开发中新增解析内容 hash 字段时，两个任务在迁移完成前读取新模型，分别产生 `ProgrammingError`。失败诊断保留：M46 `0b33d369-727d-4803-918e-efc683f7c4c7`；M48 `051732d6-aab8-422b-aa03-2d02f48b30bc`。已迁移并重试；README 明确更新结构时先停服务。
3. dispatcher 曾因临时数据库连接超时退出；已补充重连循环，使已提交的 outbox 不会因单次连接失败永久滞留。`start` 会补起已停止的本项目进程。
4. 浏览器脚本最初没有等待来源关闭导航完成，随后又错误混合 Playwright 的文件路径与 buffer；修正测试驱动后 7 项通过。未把这些失败计为通过。
5. M46 通过页面 **Retry processing** 创建新任务 `f5395d87-0fca-4875-8c3d-aae00e73f8b7`，完成解析。
6. M48 的首个重试 `fb1d695d-c7b8-4fee-b411-6c85623dad90` 被取消，后续任务 `e2c19ee5-08f1-4149-9f4a-98bf0452239a` 在真实解析时终止项目 worker。租约恢复后同一任务 epoch **1 → 3**，attempt 1 为 interrupted，attempt 3 succeeded；失败与取消祖先未被覆盖。
7. 故障注入驱动遇到另一次 API 重启产生 HTTP 500 而停止观察；业务任务继续恢复。后续通过 `manage.py check_recovered_task e2c19ee5-08f1-4149-9f4a-98bf0452239a` 读取持久记录并断言成功，不能把原驱动的一次运行报成全程通过。

## 与计划的映射

| 批次 / 任务 | 当前状态 | 对应验收边界 |
|---|---|---|
| 1 / T1 工程与任务 | 本地实现及本批检查完成 | P0-01 的受控会话/资源归属子集；任务幂等/取消/恢复基础。正式邀请、多课程 UI、生成唯一发布仍在后续范围 |
| 1 / T2 PDF 与证据 | 本地实现及本批检查完成，公式准确性受限 | AC-02-01 的数字 PDF 子集、AC-02-02/03/04；AC-03-01/02/03 的可读取/可定位及失败表达，不声称图表/公式全部正确 |
| 2 / T3–4 课程分析/编辑/确认 | 未开始 | 可先开发有明确 fixture 标识的契约及本地编辑；真实 AI①待凭据和数据处理条件 |
| 3 / T5–6 配置/蓝图 | 未开始 | 后续推进 |
| 4 / T7–8 题答/核验 | 未开始 | 后续推进 |
| 5 / T9–10 阅读/PDF/找回 | 未开始 | 后续推进；现有“原始 PDF 下载”不是生成的两个 PDF |
| 6 / T11–12 集成/六次验收 | 未开始 | **六次真实生成验收 0/6**，不拿材料解析或 fixture 测试替代 |

实现路径按实际职责合并了部分计划文件，例如 outbox 在 management command、用量在 AI contracts、测试目前在 `backend/tests/` 平铺；Windows 原生服务替代未具备的 Linux 容器运行环境。未安装 Docker/WSL。主要依赖为任务持久化、PDF 结构和原始页渲染所需；大体积 Docling/PyTorch 权重是本地解析的主要维护与资源成本。

Git 已建立历史资料基线 `ab100ab`；课程原件、私有配置、数据库、缓存和输出均在忽略范围。批次完成时提交可运行源码与验证说明。没有改写正式 PRD、技术设计或历史原型。

下一步为第一轮批次 2。API key 后续由用户提供；真实调用还需要具体外发/账户数据处理条件落定。课程直接编辑、来源/缺口数据结构和确认版本等本地工作可独立推进。当前按最新指示停在第一批交付点，没有进入第二轮。
