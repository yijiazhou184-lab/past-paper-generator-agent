# 第二批实施与验证记录

日期：2026-10-23（Asia/Shanghai）。范围：已批准首轮计划的 **Task 3–4：课程分析、必要澄清、直接编辑和课程确认**。本记录不代表首轮全部完成，不代替六次真实出卷验收。

## 交付状态

第二批功能已实现并可在本地使用。真实 QM 分析产出了可审阅的 `needs_info` 草稿；真实课程尚未达到可确认状态，未替用户确认。独立标记的 fixture 课程验证了保存、回答、两次确认与冻结版本读取。结构规划、题答生成、两个 PDF 和六次真实出卷验收仍属于批次 3–6。

入口：

- Course profile：<http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/profile>
- 真实分析任务：<http://127.0.0.1:5173/tasks/cd0d0c32-50c2-4f42-a2b6-3e9d148dd702>
- 启动方式：[README](../README.md)。当前服务保持运行，内置浏览器保留真实课程页面。

## 实际实现

| 领域 | 实现与文件 |
|---|---|
| AI① | `backend/app/courses/analysis.py`、`context.py`、`schemas.py`、`backend/app/ai/prompts/course_analysis.md`。复用官方 Responses SDK、严格结构、来源校验、持久调用记录和预算；不启用工具或外部检索 |
| 精确授权 | `AnalysisGrant` 绑定课程、用户、context hash、发送清单和授权来源。冻结 36 页文字、5 份已有页核对、声明、模型、提示词和 schema；变化后不可沿用旧授权 |
| 数据 | `UserStatement`、`CourseMachineBase`、`CourseDraft`、`CourseVersion` 及迁移。机器基础、人工 patch 和有效草稿分离；确认版本有数据库 UPDATE 拒绝触发器 |
| 范围与来源 | 教学、当前考试声明、coursework、历史 mock 和产品排除范围分开。用户声明保持 declared/unverified；角色与来源类别不匹配、伪造来源、官方身份升级被拒绝 |
| 澄清 | `clarifications.py` 只让影响目标的问题阻塞；合并同一缺口的重复问题。已有 PDF 的抽取缺失标为检查现有页图；普通回答不能冒充教学证据。回答保留 UserStatement 和新 revision；需要重新分析时建立关联新任务 |
| 编辑 | `drafts.py` 使用 expected_revision 和幂等 key；409 保留输入。重分析在发布事务中读取最新人工 patch，保留运行期间的修改；变化及孤立项目展示合并警告 |
| 确认 | `confirmation.py` 校验保存版本、关键缺口、新回答是否已分析、材料分类/答案关联和模板约束；冻结 payload、来源、声明、人工修改和分析模式。确认不等于事实认证 |
| 页面 | `frontend/src/features/profile/`：知识折叠编辑、范围/方法、历史风格、建议模板、来源抽屉、问题回答、差异比较、版本历史。800ms 串行保存；确认只使用已保存 revision；Generate 入口读取冻结版本并明确后续功能尚未实现 |
| 任务 | analysis 接入现有队列、心跳、取消、deadline、epoch 和唯一发布；`needs_info` 为真实终态；刷新恢复原 task；旧任务输入不被回答或新分析改写 |
| 接口 | `config/urls.py`、`courses/api.py`、`contracts/openapi.yaml` 和生成的前端 API 类型。课程领域的 UI 类型另在 `features/profile/types.ts`，对应服务端 Pydantic/DRF 输出 |

页面与业务端点均有课程归属检查。直接修改声明文本另记 UserStatement，保留原始机器内容；无法通过 editable patch 修改 evidence ID、readiness 或 authority_status 来消除证据问题。

## 真实模型试运行

用户在本次对话明确授权下列范围发送官方 OpenAI API：M35 p2–17；M34 p14、28–33、41；M48 p20；M06 p2、6；M32 p2；M46 p3、4、6；M05 p1、3、5；M14 p5；M33 p22，以及第一批 5 页已有核对结果和“全部 lecture 属于期末范围”的用户声明。**未发送新页图**。

首次本地预检因完整元数据的保守 UTF-8 字节预算超限而拒绝，未建立任务、未调用模型。随后保留所有页文字，只移除重复发送的 parser/hash 元数据；完整版本及哈希仍保存在本地不可变任务快照中，没有缩小知识范围或放宽 60k/12k 限额。

| 项目 | 实际值 |
|---|---|
| Task | `cd0d0c32-50c2-4f42-a2b6-3e9d148dd702` |
| Context hash | `aee6c1dde75353e5f39e31360227c7d5dae912ffff8c1d40f9f0e7f728c9ea21` |
| 模型/目的地 | `gpt-6.1-sol` / `https://api.openai.com/v1/responses` |
| 调用 | 1 次真实调用；store:false；SDK 隐式重试 0；未发新页图 |
| 结果 | structured output parsed；8 个知识组；3 supported、5 partial；业务任务 needs_info |
| 单次 API 耗时 | 132.938 秒 |
| 提交到终态 | 137.306537 秒；**未达到两分钟目标** |
| Tokens | input 17,381；output 8,900；total 26,281；cached input 0；reasoning 414（已包括在 output 内） |
| 成本 | 未查询账单，不把估算视为实际扣费 |
| 原始记录 | `var/batch2-live-cd0d0c32-50c2-4f42-a2b6-3e9d148dd702.json`（本地私有、Git 忽略） |

真实结果正确保留 all-lecture 为用户声明，没有再次要求确认该范围。syllabus 只支持教学顺序；Coursework 1 的 Topics 1–4 和评分要求只适用于该 coursework；2024/25 mock 只支持历史风格。建议模板标记未校准到当前期末卷。

首次发布时问题分类器把模型问题、相关 issue 和 partial 节点重复计数，任务原始结果保留该历史计数 12。之后修正了分类展示和断言，不重写旧模型输出或任务记录；当前草稿显示 **两组阻塞事项**及 5 组折叠的非阻塞证据说明：

1. M35 p4–6、8–9、14–15 的定义、规则或定理公式未进入抽取文本。原 PDF 已存在；本地查看 M35 p4 原图确认导数定义清晰可见。这是系统需要补读现有页图，不是要求用户重新凑齐课程材料。第一批候选页核对没有覆盖这些摘要页。
2. M34 p28 / M35 p12 的 local extrema 定义采用全定义域量词。已在 M35 p12 原页上看到该表述，模型将其与标准局部条件区别记录。没有静默改写原材料，也未把用户确认当作教师更正。课程的 critical-point 约定一并保留待核对。

目前没有新页图的外发授权，课程分析也尚未包含自动补读这条分支。因此保留 needs_info 是本批真实限制，不能声称完整 Topic 2 已可出题。下一步应把现有原页补读及局部来源冲突处理接回课程分析；无需再次询问已回答的期末范围。

## 实际运行检查

| 检查 | 结果与边界 |
|---|---|
| 完整后端 `pytest -c backend/pytest.ini backend/tests -q` | **63 passed**，75.71 秒。包括第一批回归、来源/适用性、拒绝/截断/错误、跨用户、无授权、取消发布、CAS、幂等、合并和数据库不可变约束。模型失败场景为明确 fixture，非真实 API 请求 |
| `pnpm --dir frontend test --run` | **5 passed**。迟到响应、同 key 恢复、冲突暂停、标签刷新恢复及修正被拒字段后的新 key |
| `scripts/test_course_profile.py` | **9 passed**。真实 QM 页面只读检查 + 独立 fixture 课程写入；一次本地 HTTP 请求被故意 abort 模拟断网；其余操作访问真实本地服务，没有伪造成功响应 |
| `scripts/test_workspace.py` | **8 passed**，第一批材料工作区回归 |
| `scripts/test_ai_validation_view.py 32726231-997a-4c00-825d-60fbafc282d0` | **7 passed**，读取第一批已保存的 6 次成功调用；不重新调用模型 |
| `manage.py check` | 0 issues |
| `manage.py makemigrations --check --dry-run` | No changes detected |
| `manage.py spectacular ... --validate` / `pnpm ... api:types` | 契约生成成功 |
| `pnpm --dir frontend build` | TypeScript 和 Vite 生产构建成功 |
| 确认来源标记补充检查 | 最后补充版本冻结 `analysis_mode` 后，6 项草稿/确认测试重跑通过，契约与生产构建再次成功；旧测试版本缺少该字段时显示 unknown，不冒充 live |
| `manage.py audit_batch1` | 65 个原始路径 hash 全部匹配，0 改动；11 份真实 PDF 原解析任务仍 succeeded |

浏览器记录：`var/batch2-browser-checks.json`；真实页面截图 `var/screenshots/course-profile-desktop.png`、`course-profile-mobile.png`。fixture 准备记录 `var/batch2-browser-fixture.json`；测试课程名称/模式明确标为 fixture，不属于真实课程分析成功或六次验收记录。

过程中先发现并修正了：测试 fixture 缺少来源元数据、textarea 包裹标签导致精确定位失败、确认页返回时保存结果未同步 Query cache 导致澄清回答使用旧 revision。实际检查捕获了问题后重跑通过；没有省略失败来宣称通过。

## 本地环境处理

迁移前停下项目服务后，Windows 保留了旧 PostgreSQL 的孤立子进程，持有共享内存、日志和 54329 端口；旧库控制文件显示 `shut down`，主进程已完成 checkpoint。终止该孤立进程未在期限内退出。没有删除原库或强行覆盖数据文件。

经控制文件和路径核验，将干净关闭的完整原库复制到项目内 `var/postgres-20261023/`，使用空闲端口 54330；原 `var/postgres/` 保留。脚本现在从私有配置读取活动数据目录与端口，每次启动使用独立日志。旧测试连接失败时 pytest 长 traceback 回显了开发数据库连接参数，已旋转活动开发库密码，并把默认 traceback 改为 short；未输出或改动 OpenAI key。所有私有配置仍被 Git 忽略。

当前活动服务已恢复，原任务、材料和解析记录经检查保留；旧孤立进程不是活动数据库。没有宣称在第二台干净电脑或重新启动 Windows 后验证过。启动和 API 重启已在当前电脑验证。

## 需求对应与未覆盖边界

- P0-04 / AC-04-01–03：教学支持与考试声明分离；缺口真实保留；不从旧卷或个人陈述伪造教学依据。本次真实分析不是完整范围通过。
- P0-05 / AC-05-02–03：未校准建议模板可编辑，历史与当前范围分开。没有宣称当前正式期末结构已核实。
- P0-06 / AC-06-01、03：直接编辑、保存恢复、确认版本冻结通过本地及 fixture 检查。AC-06-02 仅实现重新分析/回答过程的人工保护，不代表完整材料新增/删除联动已交付。
- P0-12：分析任务采用原有恢复、预算、取消和幂等；needs_info 与 provider failure 分开；实际耗时超目标被保留。
- P0-14：课程、草稿、版本、来源及任务归属检查；本轮没有新增删除或线上账号功能。

批次 3 的配置与蓝图编辑可以在独立 fixture 确认版本上继续开发；真实 Topic 2 出卷前仍需补读公式、处理来源冲突并由用户确认课程版本。当前不进入批次 3，也不进入第二轮。

## 官方资料

查询日期 2026-10-23。沿用用户指定且第一批已验证可用的模型，不把模型名存在视为质量达标：

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)：严格 JSON schema、额外字段限制，以及拒绝/未完整输出仍须独立处理。结构合法不能证明数学正确。
- [OpenAI Data controls](https://developers.openai.com/api/docs/guides/your-data)：store:false 的应用状态控制不等于零数据保留；本项目继续限定已授权输入和官方目的地。

## 文件计划状态

原 [2026-10-19 计划](superpowers/plans/2026-10-19-round-1-qm.md) 和正式设计/需求不改写。本次实际文件与检查安排见 [第二批执行补充](superpowers/plans/2026-10-23-batch-2-course-profile.md)。没有新增依赖；继续使用已有锁定运行时与官方 SDK。
