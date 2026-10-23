# 视觉证据路径实施与验证记录

日期：2026-10-24（Asia/Shanghai）。范围：[视觉证据路径计划](superpowers/plans/2026-10-24-visual-evidence-path.md)第 1–4 步。由 Claude Code 实施，提交为 `ad36b71`、`0f5ce41`、`d0bf5fb`、`a3a496e`。

## 结论与边界

第 1–4 步的本地功能已实现，并通过下面列出的检查。**真实页图转写调用 0 次，`TranscriptionGrant` 0 条**；真实 QM 课程的草稿、确认版本和原材料都没有改动。第 5 步（真实转写和重新分析）还没执行，需要用户授权，另外有一个预算问题待用户决定，见文末。

转写结果是模型候选，不是人工核对；课程分析只读取转写文字，不发送页图。本记录不声称公式已经读对，也不声称 M35 的阻塞已经解除。

## 实际交付

| 领域 | 文件与行为 |
|---|---|
| 分流 | `materials/routing.py`（`pdf-route-1`）：信号包括空公式区域、大图（面积 > 20000 pt²）、表格、文字少于 80 字符、整页图；只看版面标签和文字量。`model_requested`、`manual` 两个信号由分析结果和授权记录加入 |
| 转写契约 | `ai/visual.py`、`ai/prompts/visual_transcription.md`：通用核心加上 formula/table/chart/diagram/image_text/other 分类条目；严格 schema；拒绝 `native_data`、拒绝内容为空的可读条目、拒绝来源不一致；第一批 PageReview 通过只读适配器映射 |
| 数据 | `VisualTranscription`、`TranscriptionGrant` 及 migration `materials.0005`；两表都有数据库 UPDATE 拒绝触发器。缓存键为 evidence、解析 hash、页图 hash、模型、提示词版本、schema 版本 |
| 任务 | `materials/transcription.py`、`transcribe_visual_one`、`visual_transcription` CLI。解析完成后、授权创建后、任务成功后（续排剩余页）会自动调度；`transcription_policy` 决定哪些页可以发送；线程池受控并行，默认 6；每页单独落库，失败互不影响；取消后不再派发新页；结果未知的调用不重放；任务调用上限等于页数，单个任务最多 120 页 |
| 分析接入 | `courses/context.py`、`courses/analysis.py`、`courses/schemas.py`、提示词 `r1-course-analysis-2`：每页带分流结果；视觉页附上转写或 `visual_pending` 标记；已转写页只发送精简转写，不发送抽取文字；新增 `visual_review_requests`，先校验，再写入任务结果 |
| 页面与接口 | 材料列表的转写进度及轮询；来源面板显示分流原因、状态和 “Model candidate · not verified” 转写；分析预检列出待转写页。OpenAPI 与前端类型已重新生成 |

## 实施中发现并修复的问题

1. **竖版页图超出接口限制**：A4 竖版页按现有渲染比例高 1684 px，超过官方适配器的 1600 px 上限。M05、M06、M46 这类竖版页原本会全部失败。现在只把发给模型的那份图缩到最长边 1600 px，来源面板显示的原图和第一批的图片缓存都不受影响。已有测试覆盖。
2. **分析输入超过准入上限**：真实课程的分析准入估算一开始是 62,282 字节，超过 60,000。去掉与整页转写重复的可读条目和分流信号之后，降到 51,097。
3. 测试暴露的两处测试本身问题：一是多线程看不到非事务测试库中的数据，相关测试改用单线程或 `transaction=True`；二是 fixture 页文字短，会同时触发两个信号，修正了断言。

## 实际检查

| 检查 | 结果 |
|---|---|
| `pytest -c backend/pytest.ini backend/tests -q` | **136 passed**（新增 38 项：契约/分流 19、转写任务 12、分析与接口 7）。模型一律使用 fixture 提供方，不访问网络 |
| `makemigrations --check --dry-run` | No changes detected；开发库已在停服后执行 `materials.0005` 迁移，再启动服务 |
| `spectacular --validate`，生成前端类型 | 通过 |
| `tsc -b`、`vitest --run`、`vite build` | 通过；前端单测 12 项。本机 shell 没有 `pnpm`，改用 `node node_modules/...` 直接运行同样的工具 |
| 内置浏览器 | fixture 课程 `B4-VISUAL-FIXTURE`：列表显示 “Page images: 1/2 transcribed · 1 awaiting consent”；来源面板第 1 页显示转写候选、第 3 页显示等待授权；375 px 宽度下无横向溢出；无控制台错误。真实 QM 课程只读检查：11 份材料都显示待授权；分析预检显示 “36 pages · 5 … · 18 pages need their image read”，对话框关闭，未提交 |
| `manage.py visual_transcription`（只读） | 真实课程 237 页：164 页 awaiting_consent，73 页 not_needed |
| 真实 18 页范围预览（只读） | scope hash `fac78fac5a832a006919cd3d677c343daa4d971b37143a3386acee7c3b6de893`；未写入授权记录 |
| `manage.py audit_batch1` | 65 个原始路径，0 处 hash 差异 |
| `scripts/test_workspace.py`、`scripts/test_course_profile.py` | **未运行成功**：当前用户目录下没有 Playwright Chromium（`ms-playwright` 不存在）。安装浏览器需要用户同意，所以没有安装。`prepare_profile_browser_fixture.py` 已执行，新建了一个 B2-TEST fixture 课程 |

## 与计划不一致之处

- 真实课程需要页图的页数是 **164**，不是计划估算的 149。新规则还把“表格”和“文字过少”算作视觉信号。
- 本次分析选中的 36 页中，需要新转写的是 **18 页**：在计划列出的 17 页之外，加上 M46 p3（表格 + 文字少）。
- 第一批的 5 页 legacy 结果会进入分析，但材料列表和来源面板只统计新格式的转写，所以这 5 页在列表里仍显示为待授权。

## 待用户决定（第 5 步之前）

1. **授权 18 页页图转写**：M05 p3、5；M06 p2、6；M34 p28、31、32；M35 p2–6、8、9、14、15；M46 p3、4。授权命令见 [handoff](handoff.md)。
2. **分析输入预算**：拿已有 5 页转写的平均大小（每页约 1,487 字节，抽取文字约 720 字节）推算，18 页都转写后准入估算约 **64,900 字节**，超过 60,000。这个上限按 UTF-8 字节计算，实际 token 数要少得多：第二批准入估算接近上限时，实际输入只有 17,381 tokens。可选做法有三种：改成按 token 估算准入，调高字节上限，或者把分析拆成两次调用。三种都属于预算规则变更，需要用户决定。实际大小要等真实转写完成后才能确定。
3. **定义冲突**：重新分析后会以三个选项的澄清问题呈现，由用户选择。
