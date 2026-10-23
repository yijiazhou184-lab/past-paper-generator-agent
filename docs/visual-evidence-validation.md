# 视觉证据路径实施与验证记录

日期：2026-10-24（Asia/Shanghai）。范围：[视觉证据路径计划](superpowers/plans/2026-10-24-visual-evidence-path.md)第 1–4 步。由 Claude Code 实施，提交为 `ad36b71`、`0f5ce41`、`d0bf5fb`、`a3a496e`。第 5 步的真实转写部分于同日执行，见“真实转写”一节；带转写的重新分析尚未执行。

## 结论与边界

第 1–4 步的本地功能已实现，并通过下面列出的检查。实施阶段真实调用 0 次；之后经用户授权，对 18 页执行了真实转写（1 条 `TranscriptionGrant`，18 次调用）。真实 QM 课程的草稿、确认版本和原材料都没有改动。带转写的重新分析还没执行，因为分析输入超过了准入上限，需要用户先决定预算规则，见文末。

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

## 真实转写（第 5 步前半）

2026-10-24，用户在对话中授权把以下 18 页页图发送给官方 OpenAI API 做转写：M05 p3、5；M06 p2、6；M34 p28、31、32；M35 p2–6、8、9、14、15；M46 p3、4。授权记录的 scope hash 为 `fac78fac5a832a006919cd3d677c343daa4d971b37143a3386acee7c3b6de893`，与预览一致。

| 项目 | 实际值 |
|---|---|
| Task | `f1fb8733-b950-4712-838d-e0274c5f53b6`，状态 succeeded |
| 模型 / 目的地 | `gpt-6.1-sol` / 官方 Responses API，`store:false`，SDK 重试 0，并发 6 |
| 结果 | 18 页全部 `transcribed`；0 页失败；0 次缓存命中；没有续排任务（其余 146 页未授权，仍然待授权，没有发送） |
| 耗时 | 排队 0.9 秒；执行 136.5 秒；提交到完成共 137.3 秒。单次调用 14.8–55.3 秒，平均 30.0 秒 |
| Tokens | input 62,786；output 36,966；total 99,752（每页平均约 3.5k 输入、2.1k 输出） |
| 成本 | 未查询账单，不把估算当作实际扣费 |
| 原始记录 | `var/visual-transcription-f1fb8733-b950-4712-838d-e0274c5f53b6.json`（本地私有，Git 忽略） |

耗时说明：计划按“每页约 17 秒、并发 6”估算 18 页约需 1 分钟，实测约 2.3 分钟。原因是单次调用平均 30 秒，比第一批的单页核对慢。

**Claude 抽查**：对照原页图逐项比对了 4 页，结果属于模型候选的抽查，不是人工认证。

| 页 | 观察 |
|---|---|
| M35 p4（导数定义） | 标题、定义句和极限公式与原图一致；第二批的阻塞正是这页公式缺失。公式条目把 “provided that this limit exists” 也写进了 LaTeX，内容没错，只是没有拆开 |
| M35 p14（Rolle / 中值定理） | 两条定理与 \(f'(c)=\frac{f(b)-f(a)}{b-a}\) 一致；“cϵ(a,b)” 按原样保留；两张示意图的描述（曲线、虚线 c、平行线、a/c/b 标注）与原图相符。公式条目同样夹带了整句文字 |
| M05 p3（竖版 A4，已缩图） | 二元极限、分段函数、混合偏导、\(\int_1^\infty x^5e^{-x^3}dx\)、\(\int_0^{\cos x}e^{-t^2}dt\)、G 的 Lipschitz 条件均与原图一致；原文语病（“exists”）按原样保留。两条 source_issue 观察（只假设 C∞ 就要求全局常数 K；没有要求 p≠0）在数学上成立，但它们只是候选意见，不是对课程材料的更正 |
| M46 p3（表格） | 表格各行与原图一致；所指出的“Level 7)” 右括号没有配对，在原图上确实存在 |

## 带转写的分析输入（只读测量，未调用模型）

| 项目 | 值 |
|---|---|
| 页数 | 36 页：23 页已转写（18 页新转写 + 5 页 legacy），13 页走文字路径，0 页 visual_pending |
| 准入估算 | 提示词和 schema 13,608 字节 + 输入 53,133 字节 = **66,741 字节，超过 60,000 上限** |
| 每页大小 | 转写页平均 1,567 字节，最大 3,452；文字页平均 979 字节 |
| 本地准入 | `request_body` 返回 `TOKEN_BUDGET_EXCEEDED`。如果现在提交，会在本地被拒绝，不会发送任何数据 |
| context hash | `2eec410634486018e5e10d579b680e70a8664df20b2779496d83231d81d015f3`（尚未授权） |

估算按 UTF-8 字节计算，不是计费 token。第二批的准入估算接近 60,000 字节时，实际输入为 17,381 tokens，约 3.4 字节对应 1 token；照此粗略推算，本次约 2 万 tokens。这只是估算，未实测。

## 与计划不一致之处

- 真实课程需要页图的页数是 **164**，不是计划估算的 149。新规则还把“表格”和“文字过少”算作视觉信号。
- 本次分析选中的 36 页中，需要新转写的是 **18 页**：在计划列出的 17 页之外，加上 M46 p3（表格 + 文字少）。
- 第一批的 5 页 legacy 结果会进入分析，但材料列表和来源面板只统计新格式的转写，所以这 5 页在列表里仍显示为待授权。

## 准入改为按 token 计算（2026-10-24）

用户决定：课程分析的准入改为按 token 计算，上限仍为 60k tokens；token 数用官方计数接口获得（[Counting tokens](https://developers.openai.com/api/docs/guides/token-counting)、[input_tokens.count 参考](https://developers.openai.com/api/reference/python/resources/responses/subresources/input_tokens/methods/count)，2026-10-24 查阅）。官方页面没有说明该接口是否计费、有哪些速率限制、数据如何保留，本记录对此也不作推断。

| 改动 | 行为 |
|---|---|
| `ai/responses.py` | 新增 `count_official`，调用 `POST https://api.openai.com/v1/responses/input_tokens`，只发送 model、instructions、input、reasoning、text 五项，不生成内容；固定官方地址，SDK 重试 0。`request_body(byte_admission=False)` 跳过字节上限 |
| `ai/invocations.py` | `count_call` 把计数请求记录为单独的调用记录（purpose `input_token_count`）。超过 60,000 时报 `TOKEN_BUDGET_EXCEEDED`，**不发分析请求**；计数失败也不发。中断后的计数可以重做，因为它不生成内容。`run_call(counted_tokens=…)` 用计数结果代替字节估算，并把来源写入调用元数据 |
| 课程分析 | 授权后先计数再分析。提交前的检查只确认请求结构有效，不再用字节数拒绝。快照新增 `admission`，所以 context hash 变了，需要新的授权 |
| 预检与页面 | 预检展示本地字节数，并说明授权后会先发一次计数请求、超过上限即停止 |
| 其他阶段 | 规划、页图转写、第一批核对仍沿用字节上限，没有改 |

**测试误发真实请求**：新增计数后，4 个已有测试只替换了生成调用，没有替换计数调用。设置会读取 `.env.local` 中的真实 key，这 4 个测试因此向官方计数接口发出了 **4 次真实请求**。请求内容是合成 fixture（提示词 “fixture”、证据为空、模型名 “fixture”），**不含课程数据**，全部被 OpenAI 以 404（模型不存在）拒绝。已修复：`conftest.py` 新增自动生效的 fixture，测试中一律删除 `OPENAI_API_KEY`；这 4 个测试也单独替换了计数调用。

检查：后端 pytest **141 passed**（新增 5 项：计数请求契约、字节上限只在没有计数时生效、超限时不发分析请求、限内时记录计数、预检展示准入方式）；前端 tsc、vitest 12 项、build 通过；`restart-api` 后，内置浏览器打开真实课程的预检对话框，确认显示正确，未提交。

新预检（只读）：context hash `b73c0b52ef37e65f626e58915cd52126e11ff5dce11c88c063034c72b1003108`；36 页（23 页使用转写，13 页使用文字，0 页待转写）；不发送页图；本地 66,229 字节；最多 8 次调用；包含两条用户声明：“All lecture content”，以及此前已保存、尚未分析的澄清回答（按标准邻域定义；critical point 只包括 f′(c)=0）。

## 带转写的重新分析（第 5 步后半，2026-10-24）

用户授权 context hash `b73c0b52ef37e65f626e58915cd52126e11ff5dce11c88c063034c72b1003108` 的预检范围：先发一次计数请求，再做课程分析。

| 项目 | 实际值 |
|---|---|
| Task | `c6161ed8-ce85-4d9f-893a-a70b320f1deb`（parent 为第二批的 `cd0d0c32`），最终状态 `needs_info` |
| 计数请求 | 官方 `input_tokens` 接口，1.6 秒，**19,169 tokens**，低于 60,000 上限 |
| 分析请求 | `gpt-6.1-sol`，`store:false`，129.97 秒；input 19,169（与计数一致），output 8,921（含 reasoning 216），total 28,090；cached 0 |
| 提交到终态 | **135.9 秒，超过两分钟目标**，如实记录 |
| 草稿 | revision 5；合并警告 0；`visual_review_requests` 为空 |
| 成本 | 未查询账单 |
| 原始记录 | `var/batch2-live-c6161ed8-ce85-4d9f-893a-a70b320f1deb.json`（本地私有） |

**阻塞事项的变化**（对比第二批的 `cd0d0c32`）：

| 第二批阻塞 | 现在 |
|---|---|
| M35 p4–6、8–9、14–15 的公式未进入抽取文本 | **已解除**。8 个知识组中 6 个 supported，包括导数定义、求导法则、驻点与极值、应用优化、Rolle 和中值定理、单调性；不再有 MISSING_ 类问题 |
| M34 p28 / M35 p12 局部极值定义冲突 | **降为 informational**。分析读取了用户此前保存的回答（按标准邻域定义；critical point 只包括 f′(c)=0），记为练习偏好 `EXTREMA_CONVENTION_PREFERENCE_RECORDED`，没有当作对课件的更正 |

计划 §5 的完成标准（M35 公式缺口不再以 MISSING_ 形式整体阻塞，分流原因和转写来源可追溯）**已达成**。课程仍未确认，数学正确性也没有经过验证。

**新的两个阻塞**：L'Hôpital's Rule 和 Implicit differentiation 都是 `partial`。本地查找发现，原因是首轮固定选页 `PAGE_SELECTION` 没有包含这两个主题的主要教学页，而不是课程里缺少这部分内容：

- L'Hôpital：只选了 M35 p15（总结页）。没有选的有 M34 p34、46、47，M14 p4，M48 p19、21、22。
- 隐函数求导：只选了 M35 p16。没有选的有 M34 p48、49（含例题）。
- 这 9 页里，8 页按规则需要读页图（M34 p46–49、M14 p4、M48 p19、21、22），M34 p34 走文字路径。

另有一个不阻塞的 `needs_confirmation` 问题，以及若干 warning：L'Hôpital 定理陈述缺少条件、反函数恒等式印刷有误、定义域与全局最优描述不明确等，留待用户审阅草稿时处理。

## 待用户决定

1. 是否扩大选页，把上述 9 页加进去。需要授权 8 页新页图转写，再授权一次新的分析输入。或者，也可以把这两个主题移出本轮练习范围。
2. 是否接受 135.9 秒的分析耗时；两分钟目标按 PRD 是出卷目标，课程分析的耗时单独记录。

## 扩大选页（2026-10-24）

用户决定把 9 页加入分析选页：M34 p34、46–49；M14 p4；M48 p19、21、22。`courses/context.py` 的 `PAGE_SELECTION` 已据此修改，分析范围从 36 页增加到 45 页，因此 context hash 会变化，需要新的分析授权。后端 pytest 141 passed。

其中 8 页需要页图转写。已生成精确范围预览，**尚未授权、未发送**：scope hash `0e2c3657c1d763addc869c0af4d370966cebd8c643cf96cc3f07b0a9c1c134f4`；模型 `gpt-6.1-sol`；页码为 M14 p4，M34 p46、47、48、49，M48 p19、21、22。M34 p34 走文字路径，不需要页图。

### 8 页转写结果（用户授权 scope `0e2c3657…`）

| 项目 | 实际值 |
|---|---|
| Task | `1b068ee2-d830-4a0e-b203-1806dda9e33a`，8/8 transcribed，0 页失败 |
| 耗时 | 排队 0.6 秒；提交到完成 51.9 秒；单次调用 11.8–39.7 秒，平均 25.7 秒 |
| Tokens | input 26,184；output 13,706；total 39,890 |
| 原始记录 | `var/visual-transcription-1b068ee2-d830-4a0e-b203-1806dda9e33a.json`（本地私有） |

**Claude 抽查**：M34 p47（洛必达例题，结果为 1/3）和 M34 p49（\(y^2=x^2+\sin(xy)\) 的隐函数求导）的推导与原图逐行一致；p49 右侧图的描述（两条略带波动的曲线在原点附近相交，坐标刻度 −10 到 10）也与原图相符。其余 6 页没有逐页核对。

### 新的分析预检（只读，未授权）

context hash `65b5d272e3449fa6085bb907f75bce1e735d5ce252b2110e7eca893868e9d92e`。共 45 页：31 页使用转写，14 页使用文字，0 页待转写；不发送页图；本地 77,462 字节（上次 66,229 字节对应 19,169 tokens，照此比例粗估约 2.2 万 tokens，未实测）。用户声明仍是那两条，最多 8 次调用。授权后会先发一次计数请求，再发一次分析请求。

### 45 页重新分析（用户授权 context `65b5d272…`）

| 项目 | 实际值 |
|---|---|
| Task | `409d5fa7-5381-4bec-bf68-2f142dfa85c8`（parent `c6161ed8`），**succeeded** |
| 计数请求 | 1.4 秒，**23,025 tokens** |
| 分析请求 | 142.6 秒；input 23,025（与计数一致，其中 cached 2,260），output 9,620（含 reasoning 459），total 32,645 |
| 提交到终态 | **148.6 秒，超过两分钟目标** |
| 草稿 | revision 6，合并警告 0；**阻塞 0 个，8 个知识组全部 supported**（包括 L'Hôpital 和隐函数求导） |
| 原始记录 | `var/batch2-live-409d5fa7-5381-4bec-bf68-2f142dfa85c8.json`（本地私有） |

非阻塞事项：
- 1 个 `needs_confirmation`：对 i3–i7 标记的原文问题（反函数复合印成 1、平方根定义域、正则性断言、极限去向前后不一、全局最优未论证）选择练习处理方式，三选项。
- 极值定义按用户回答记录。
- 若干 warning 和 info 说明，包括 seminar 中标明 WRONG 的证明只能用于错误诊断。

模型请求读页图：M35 p7（Lecture summary）。理由是这一页走文字路径，但求导记号中的分式被压平、在某点取值的写法损坏。这一页已经通过 `model_requested` 信号升级为视觉路径，状态为 awaiting_consent，**没有发送**。

本次结果说明草稿已具备进入 **Review & confirm** 的条件，但**课程尚未确认**：确认需要用户在页面上操作。练习偏好那一问是 `needs_confirmation`，不阻塞确认。供应商结构化输出合格，不代表数学内容已经验证。

### M35 p7 转写范围预览（未授权）

scope hash `00cf020b0898770244f2551b8e7213e9514a5cde01c13b2ed1463aab5e38abce`：1 页，即 M35 Lecture summary p7（evidence `e4e87d33-3eab-4a23-a7f1-a8dd02d76807`），信号为 `model_requested`，模型 `gpt-6.1-sol`。授权记录仍为 2 条，没有新增，也没有发送。

### M35 p7 转写结果（用户授权 scope `00cf020b…`）

Task `82fd4f4b-7092-409e-bb6f-7b91ca8bd9fd`：1/1 transcribed；提交到完成 20.4 秒，单次调用 16.3 秒；input 3,315（其中 cached 1,500），output 1,020，total 4,335。原始记录在 `var/visual-transcription-82fd4f4b-7092-409e-bb6f-7b91ca8bd9fd.json`。

**Claude 核对**：转写内容为 \(f'(x)\)、\(y'\)、\(\frac{df}{dx}\)、\(\frac{dy}{dx}\)，以及 \(f'(a)\) 或 \(\left.\frac{df}{dx}\right|_{x=a}\)，与原图一致。原抽取文字中，分式和取值竖线都已丢失。

这一页的公式在 PDF 中是数学斜体 Unicode 文字，Docling 没有把它标成公式区域，所以版面规则漏判了。是模型在分析中提出申请（`model_requested`）后才补上的，说明兜底路径有效。以后可以考虑把“文字中含数学字母数字符号”加为分流信号，本次没有改。

按用户要求**没有重新分析**。草稿仍是 revision 6；这一页的转写会进入下一次分析，届时 context hash 会改变，需要重新授权。
