# 视觉证据路径：页级分流与页图转写

> 状态：**已完成**（2026-10-24）。第 5 步的真实转写和重新分析均已执行，完成标准已达成。实施结果和偏差见 [验证记录](../../visual-evidence-validation.md)。依据已确认的 [AI 技术方案 v0.1 §4](../../ai-technical-design-v0.1.md)“结构化解析＋页面视觉证据”及 [第二批记录](../../batch-2-validation.md) 中的两组阻塞事项。本计划不改写 PRD、技术方案或首轮原计划。

## 1. 目标与边界

**目标**：解除真实 QM 课程的公式缺口阻塞。抽取文字不足以表达内容的页面，改由页图转写后再进入课程分析。

**原则**：数据契约按“任意科目、任意格式”设计；首轮只实现 PDF，以及 QM 中的公式和图形。

| 本次包含 | 本次不包含 |
|---|---|
| PDF 页级分流规则及原因记录 | Word/PPT 适配（LibreOffice 渲染、幻灯片和章节定位） |
| 通用转写契约；实现公式、图形和页面文字 | Accounting 表格、BA 图表的专项验证（第三轮按真实样本验证） |
| 材料层转写任务，带缓存、授权、取消和恢复 | 局部裁图和高分辨率重渲染（契约预留 bbox 字段） |
| 课程分析读取转写结果；模型可申请升级页面 | 修改 `PAGE_SELECTION` / `TARGETS` 的首轮固定选页 |
| 来源面板显示转写候选（LaTeX 原文显示） | KaTeX 渲染（批次 5 引入）、Docling 公式增强对照 |
| 定义冲突以选项式澄清呈现 | 替用户确认课程或选择定义 |

## 2. 通用契约

**分流决定** `RouteDecision`（纯函数计算，结果写入任务快照和分析输入）：

- `locator`：`{kind: pdf_page | slide | section, value, bbox: null}`，首轮只产生 `pdf_page`。
- `route`：`text | visual | unsupported`。
- `signals[]`：取值为 `empty_formula_region | large_figure | table_region | low_text_density | full_page_image | model_requested | manual`。
- `rule_version`：规则版本号，用于追溯旧结果。

首轮 PDF 规则：

- 只要命中任一视觉信号，该页就走 `visual`；拿不准的页也走 `visual`。
- `full_page_image`（页面几乎没有文字，只有一整张图）照样走 `visual`。如果模型判断该页是扫描件或手写，转写结果标为 `unsupported_input`，不当作成功理解。
- 规则只依据 Docling 的版面标签和文字量，**不看科目名称或文件名**。

**页图转写** `VisualTranscription`（每页调用一次，严格 schema）：

- 通用核心：`source`（与现有 SourceRef 一致，加 locator）、`status`（`transcribed | partially_readable | unsupported_input | unable_to_determine`）、`faithful_transcription`、`findings[]`（沿用第一批的 parser_loss / source_issue / intentional_wrong_example / uncertain）、`unresolved[]`。
- `items[]`：`kind` 取 `formula | table | chart | diagram | image_text | other`；每项都带 `location`、`legibility`、`value_origin`（`native_data | read_from_image | not_applicable`）。各类型的专属字段在不适用时为 null：
  - formula：`latex_as_printed`
  - table：`columns`、`rows`、`units`
  - chart：`axes`、`series`、`labelled_values`
  - diagram：`elements`、`relations`
- 按原样转写，不纠正原文；图上读出的数值一律标 `read_from_image`。

**缓存与不可变**：一条转写结果的键是“evidence + 解析内容 hash + 页图 sha256 + 模型 + 提示词/schema 版本”。结果写入后不可修改（沿用现有数据库 UPDATE 拒绝触发器）。键不变就直接复用，不重新调用；解析内容或页图变化时，旧结果自动失效，不能再被引用。转写结果始终是**模型候选**，`Evidence.fidelity_status` 保持 `needs_review`。

第一批已有的 5 页 `PageReview` 结果通过只读适配器映射到新结构（`schema_version` 标为 legacy），不重新发送。

## 3. 实施步骤（每步完成后单独提交）

1. **契约与分流**：
   - 新增 `materials/routing.py`（规则和 `RULE_VERSION`）以及 `ai/visual.py`（schema，提示词放在 `ai/prompts/visual_transcription.md`）。
   - 新增 `VisualTranscription` 和 `TranscriptionGrant` 两个模型及 migration。
   - 测试：基于构造的 Docling 区块验证分流结果；验证 schema 严格性、来源不一致时拒绝、`value_origin` 必填、legacy 映射。
2. **后台自动转写任务**：
   - 新任务类型 `visual_transcription`：`materials/transcription.py`、`transcribe_visual_one` 命令，并加入 `core/queue.py` 映射。
   - **自动触发**：材料解析成功后，自动为 `visual` 页排队，用户不需要任何操作。缓存命中的页直接跳过。
   - **授权策略层** `transcription_policy(course, pages)`：先判断允许外发哪些页，再交给任务执行，任务代码本身不处理授权。
     - 开发阶段：只放行用户按页清单授权过的页（记录为 `TranscriptionGrant`，用命令行预检和授权），其余页标记为 `awaiting_consent`，不发送。
     - 上线时：换成“用户上传时已同意数据处理”，不再逐页授权。
   - **受控并行**：每页一次调用，并发上限可配置（默认 6，实际值参考 API 速率限制和实测情况定）。每页独立占用一个调用槽，单独落库，各页之间互不阻塞。整个任务共用一份 epoch、心跳和取消状态：取消后不再派发新页，已在途的页如果迟到返回，结果只保留为记录，不发布。
   - 失败处理：单页失败不影响其他页，失败页会标出原因。没有自动重试，结果未知的调用不重放。
   - 测试：缓存命中时零调用；hash 变化后失效；未授权页不发送；并发上限生效；单页失败时其他页照常完成；取消后不再派发新页，迟到结果不发布；跨课程访问被拒绝。全部使用 fixture 适配器，并发用可控延迟模拟。
3. **接入课程分析**：
   - `courses/context.py` 为每页附带分流决定，并附上有效转写或 `visual_pending` 标记。提示词升版，所以 context hash 会变化，需要新的 AnalysisGrant。
   - 分析的输入仍然**不含页图**，只含转写文字。
   - `AnalysisOutput` 新增 `visual_review_requests[]`（evidence_id 和原因），作为下次预检的 `model_requested` 信号。
   - 提示词规则：
     - `visual_pending` 的页按已知缺口处理，模型不得猜测内容。
     - 来源冲突类问题给出选项：按原文 / 按标准定义并注明差异 / 暂不纳入。
   - 测试：缺少转写时如实标记缺口；转写变化会改变 hash；升级请求能写回；人工修改的合并逻辑不受影响。
4. **接口与页面**（不加授权按钮）：
   - Materials 和 Profile 页显示每份材料的转写进度（已完成、进行中、待授权、失败），并链接到任务页。
   - 课程分析预检列出仍处于 `visual_pending` 的页，供用户在分析前查看。
   - 来源面板显示转写候选（LaTeX 按原文显示），并标明 “Model candidate · not verified”。
   - 同步更新 OpenAPI 和前端生成类型。
   - 浏览器检查使用 fixture 课程。
5. **真实运行（需要你分两次授权）**：
   - 授权 ①：18 页新页图转写（M05 p3、5；M06 p2、6；M34 p28、31、32；M35 p2–6、8、9、14、15；M46 p3、4）。原计 17 页；按实际规则，M46 p3（表格、文字少）也需要转写。
   - 授权 ②：带转写结果的新一次课程分析输入。
   - 运行后人工抽查几页转写，对照原页图，标为“Claude 抽查”，不算人工认证。
   - 记录实际耗时、tokens、失败情况，以及阻塞事项的变化。
   - 定义冲突由你在澄清中选择，我不代选。

## 4. 运行限额与预计

- 每页最多 1 次调用，单次 150 秒超时，输出上限 5k tokens，SDK 自动重试 0，`store:false`；任务调用上限等于清单页数。
- **估算，未实测**：第一批每页约 3k tokens、约 17 秒。并发 6 时，17 页约 1 分钟；全部约 149 个视觉页约 7 分钟，约 450k tokens。实际扣费未知。
- 转写在解析完成后自动在后台运行，用户整理材料期间同步进行，大部分情况下不需要专门等待。每个材料版本只做一次，不计入出卷两分钟目标。
- 实测时分别记录：解析耗时、转写排队耗时、转写执行耗时，以及从上传到可以分析的总耗时。压缩输出、换更快模型留到拿到实测数据后再决定。

## 5. 验证与交付

- 计划执行的检查（不代表已执行）：后端 pytest 全量、`manage.py check`、`makemigrations --check`、OpenAPI 校验与类型生成、前端 test/build、`scripts/test_course_profile.py` 和第一批回归、`audit_batch1`。
- 结果写入 `docs/visual-evidence-validation.md`，并更新 README「当前实现」。
- **完成标准**：M35 公式缺口不再以 “MISSING_” 形式整体阻塞，转为已转写或具体不可读项；分流原因和转写来源可以追溯。不以“课程已确认”或“数学已验证”作为完成标准。
