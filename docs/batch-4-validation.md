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

本批尚未运行以下调用；这是已实现但待真实验证的路径：

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

未做真实 AI③/④ 调用、实际费用核对、教师级题答抽查、难度校准或两分钟完整出卷验收。受限检查器主要支持单变量求导、等式、值、极限、驻点、有界优化及明确可判定的洛必达检查；超出范围保留 not_checked / inconclusive。复杂证明依赖语义判断，不能冒充符号证明。固定历史比较集合为空、有限材料检索和合成判断均是明确限制。


## 最终浏览器验收与查看

- 课程：`fc14a93b-f943-437b-9549-a83cfe51e94f`（B4-FIXTURE，合成数据）。
- 结果：[82ff0ea5-7399-42e0-8af2-d5b279d4d393](http://127.0.0.1:5173/tasks/82ff0ea5-7399-42e0-8af2-d5b279d4d393)。
- 任务实际状态：succeeded；提交至完成 41.52 秒，其中执行 39.88 秒；模型调用 0 次。**这些是合成流程耗时，不是真实模型性能证据。**
- 报告：必需项 43，通过 43，门槛 allowed=True。语义与盲解判断来自合成适配器。
- `scripts/test_generation_content.py` 8组断言通过：入口、丢失响应后恢复同一任务、实际worker成功/刷新、主动获取答案/KaTeX、隐藏和重载不预取答案、固定版本来源、390px无整页横溢、无未捕获JS错误。
- 记录：`var/batch4-browser-check.json`、`var/batch4-fixture-outcome.json`；桌面题卷/答案和手机截图已保存并检查。
- 服务启动复核：`scripts/local.py start` 返回 http://127.0.0.1:5173，复用本项目进程。内置浏览器与预检文件的 open_in_codex 返回 queued，未把该返回值声称为用户已经看到页面。
