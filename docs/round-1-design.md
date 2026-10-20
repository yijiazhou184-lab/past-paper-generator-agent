# Round 1 design：从材料到可恢复的章节练习

状态：**待审阅的首轮方案，未进入正式开发**。设计整理日期：2026-10-20；材料、参考页面及官方技术资料核对日期：2026-10-19。对应计划：[文件级实施计划](superpowers/plans/2026-10-19-round-1-qm.md)。

本轮重点是建立完整开发流程：材料进入系统，AI 形成有依据的课程草稿，用户必要时澄清并确认，系统规划本次练习，生成成对题答，检查、导出并保存可找回的结果。Quantitative Methods 的 Topic 2 是第一套验证数据，不要求先把整门课程的材料补齐。

本文件只新增设计，不替换既有 PRD 和技术方案。文内目录、接口、schema、数值限额和选型凡标为“建议”均等待本轮确认；示例不是生成结果，也不是已通过的测试。

## 1. 依据、现状与决定状态

### 1.1 依据

已阅读 [AGENTS.md](../AGENTS.md)、[PRD v1.0](PRD-v1.0.md)、[技术方案 v0.2](technical-design-v0.2.md)、[AI 处理流程计划](AI%20处理流程计划.md)、[AI 技术方案 v0.1](ai-technical-design-v0.1.md)、[MVP 开发轮次](mvp-development-rounds-v0.1.md)。正式产品行为以 PRD 为准；第一轮交付是其分阶段实现，不代表 P0-01 至 P0-14 全部完成。

| 状态 | 本轮含义 |
|---|---|
| 已确认要求 | 英语界面及题答；四个核心 AI 环节；课程和结构分别确认；题卷与答案分开；真实网页及两个 PDF；来源可定位；版本冻结、幂等、取消、唯一发布；质量优先并测量两分钟目标 |
| 已确认设计方向 | React + TypeScript + Vite；Router 管导航、Query 管服务器缓存；复杂表单 RHF + Zod；PostgreSQL 与私有文件存储；AI 技术方案 v0.1 为初步基线 |
| 用户本次补充 | “期末考试是整个所有 lecture 考试范围。”保存为 `User-provided scope`；可以作为本课程的明确范围输入，不冒充官方考试公告 |
| 本轮推荐 | Topic 2 章节练习；2–4 道大题；下面的页面、schema、六批次、限额、Django/任务库/模型/解析器组合 |
| 待验证 | 模型可用性及质量/延迟/费用；Docling 公式与页内位置；任务库兼容性；数学核验覆盖；PDF 长内容排版；部署环境 |
| 实际已存在 | 历史 HTML 原型、LiteLLM 接入准备、真实课程 PDF；尚无正式端到端产品实现 |

“全部 lecture”与“本次仅 Topic 2”不矛盾：前者描述课程考试范围，后者描述本次练习选题范围。当前考试学年没有单独确证，保留为空或用户声明；不因为这一元信息缺失阻止 Topic 2 设计或开发。

### 1.2 当前工程事实

- `prototype/index.html` 使用演示数据、本地缓存和定时器模拟进度；文件选择不读取内容，PDF 按钮未连接实际导出。本次检查其代码，未把历史浏览器演示结果当正式测试。保留原文件。
- `LITELLM_SETUP.md`、`requirements-litellm.txt`、`litellm-config.example.yaml` 和已有虚拟环境属于接入准备。元数据显示 LiteLLM 1.105.1、Python 3.12.14；示例仍含模型占位。历史模拟测试不证明真实供应商已接通。本次未读取密钥值、启动代理或调用模型。
- 当前目录不是 Git 工作树；本次不初始化。正式开发的第一批先建立忽略规则和可恢复基线。
- 历史进度报告里“没有课程材料”“没有 AGENTS”等表述已不符合当前文件状态；保留历史报告，在此记录差异。
- 已有 `.gitignore` 主要覆盖 LiteLLM 环境和 `.env`。课程原文、后续解析缓存、模型输出、数据库及下载文件需要在开发前补充忽略规则。

### 1.3 本轮边界

实现本地受控测试身份下，一个课程、一个章节、数字 PDF 的完整链路，支持三档难度、题型选择、大题数变化、证据查看、直接编辑、确认、后台任务、题答检查和持久结果。最小归属授权、错误记录与任务恢复从第一批开始。

完整模拟卷、多章节组卷、其他文件格式、课程更新的全面合并、联网补充、线上邀请账号、完整删除与反馈管理留给后续轮次。相关数据字段预留明确状态，但不建设空的“已支持”入口。首轮不要求软件作答、不执行 Mathematica/Python/R/Excel 代码；必要曲线、表格由受控程序生成供纸笔或计算器作答。

## 2. 首轮开发流程与可检查产物

```text
1 工程与证据
  PDF原件 → 文件身份/重复映射 → 解析版本 → 带页码的证据
           ↓
2 课程分析与确认
  AI① → 草稿 → 必要澄清/直接编辑 → 保存 → 课程确认版本
           ↓
3 配置与组卷规划
  配置 → AI②蓝图 → 结构摘要/差异 → 用户确认结构
           ↓
4 题答与核验
  冻结输入 → AI③成对题答/素材 → 程序检查 + AI④ → 必要修复
           ↓
5 输出与找回
  冻结内容 → 网页 + 题卷PDF + 答案PDF → 唯一发布 → 历史
           ↓
6 集成与真实验收
  故障/恢复检查 → 冻结配置与评审口径 → 六次真实运行 → 记录结论

持久化、版本绑定、归属授权、错误诊断、取消/重试贯穿全部批次。
```

每批都交付可单独检查的垂直切片；第二批不等六次验收才检查保存，第一批也不等生成完成才检查任务重复领取。模型适配器允许离线契约样例帮助开发，但界面及报告必须区分 `Design example`、`Fixture`、`Live model run`。

### 2.1 澄清是产品流程的一部分

**先从材料发现，再问最少的必要问题。** AI①返回结构化缺口，不由页面临时拼接问题，也不将所有未知都变成开工门槛。

1. 根据材料提取教学内容、考试声明、历史题型及未知项。每项声明记录来源类别、适用对象和版本。
2. 对照本次目标判定影响：`informational`、`needs_confirmation`、`blocks_selected_scope`。无关章节缺少材料只提示。
3. 对确实影响选定章节的未知提出可回答的问题，显示“为什么需要”“影响哪些内容”，提供直接回答、补充材料、调整练习范围三个入口。
4. 用户回答保存为独立、不可覆盖的 `UserStatement`。回答可解决工作流缺口，但不会把声明来源变成 `official_document`。
5. 合并为新的课程草稿 revision，呈现变更和残留疑问。用户可编辑，保存后确认。确认代表采用该版本，不代表所有来源已被官方核实。
6. 若任务因必要信息不足进入 `needs_info`，回答后创建关联的新任务和输入快照；旧任务及其问题保留。只复用依赖未变的成果。

示例：本次用户的“期末覆盖所有 lecture”填入范围声明，Topic 2 可以继续。若某 lecture 明确写着局部内容“不考”，系统标出具体局部冲突并询问其适用性；不把整门课程退回无范围状态。当前 Topic 10 的 LU 说明与 Topic 2 无关，不阻止本轮。

如课程有教学材料且用户明确给出考试范围，但没有历年卷，允许生成建议结构并持续显示 `Not calibrated to a current exam paper`。如果连目标知识内容都无法确认，不能靠用户点击确认伪造教学证据，应补充目标内容或缩小选题。

### 2.2 开工与验收的不同门槛

| 时点 | 必需条件 | 不要求预先解决 |
|---|---|---|
| 本次设计交付 | 设计与计划可审阅，范围和未知被清楚标注 | 完整 QM 材料、真实模型连接、官方考试公告 |
| 批次 1–3 开发 | 用户确认本轮方案；批准的开发环境；Git 基线；契约样例 | 全课内容、正式成本预算、六次模型成绩 |
| 第一次真实 API 试运行 | 可用且合规的账户/地区、密钥安全注入、发送数据范围和保留方式已确认、调用限额启用 | 所有页面已精修、所有知识点已通过 |
| 六次真实验收 | 模型/提示词/解析/限额/输入和评分口径冻结；完整输出与恢复链路；评审人明确 | 当前期末官方试卷；全 MVP 的所有功能 |

## 3. 首轮验证样本与建议配置

完整材料清单在附录 A；这里仅说明它如何支持开发。当前 `Quantitaive methods` 有 **65 个路径、51 个唯一 PDF 内容、1,497 个路径计页、1,107 个去重计页**。大小为 43,092,307 字节，去重后 35,181,118 字节。原材料不移动、不删除、不改写。

### 3.1 建议章节与知识边界

选用 **Topic 2 — Functions of a single variable: Differentiation and optimisation**。理由是 lecture、summary、seminar、additional questions、带答案的旧 mock 片段以及 assessment 均能相互参照，足以检验公式、定义域、边界、证明、商业应用和错误证据处理。

| 知识组 | 本轮目标与课程方法 | 主要物理页位置 |
|---|---|---|
| K1 定义与可导 | 导数定义、单侧导数、分段连接、连续与可导关系 | M34 p7–15；M35 p2–5、10–11；M48 p2–7；M06 p2–5 |
| K2 运算 | 和/积/商、幂/指数/对数/三角、链式法则、高阶导数 | M34 p16–24；M35 p6–9；M48 p8–12；M06 p6–7 |
| K3 极值 | 驻点、二阶判别及不确定情形、区间端点、局部/全局区别 | M34 p28–32；M35 p12–13；M48 p13–16 |
| K4 应用 | marginal revenue/cost、profit、性能与销售最优化；单位和可行域 | M34 p33–41；M48 p14–16；M46 p4 Q5；M05 p5 Q3(b) |
| K5 定理与论证 | Rolle、MVT、适用条件、简短证明/反例 | M34 p42–45；M35 p14；M48 p17–18；M46 p4 Q4；M14 p6–7 |
| K6 极限应用 | L’Hôpital，逐次检查不定式条件 | M34 p46–47；M35 p15；M48 p19–22；M14 p3–4 |
| K7 隐函数 | 单变量关系下 implicit differentiation 与切线 | M34 p48–49；M35 p16 |
| K8 单调性 | 导数符号与单调区间 | M34 p50；M35 p17；M48 p13 |

Topic 1 极限、代数和基本三角极限可作为明确标记的前置知识，不把目标扩成 Topic 1 综合卷。M33 为背景方法；M32 的 syllabus 说明教学顺序，不单独证明考试范围。

建议暂不把 M34 p51–52、M35 p18 的 “Above and beyond” 一阶导数极值判别/曲线综合描绘作为本轮必测目标。这是收敛首轮的产品选择，**不是发现了官方不考声明**；普通导数符号与单调性仍在 K8。多变量微分、积分、ODE、线性代数、软件指令题不进入本轮。Challenge 增加组合推理、参数条件和论证深度，不借此超出确认范围。

### 3.2 证据用途必须分开

| 类别 | 可以支持什么 | 不能支持什么 |
|---|---|---|
| 教学内容与方法 | M34/M35/M48/M06 的知识、符号、课程使用的方法和典型练习 | 仅凭“讲过”推定每个内容必考，或把来源中的错误当数学真理 |
| 明确范围输入 | 用户本次声明“全部 lecture”；M46 p4 明确 Coursework 1 Topics 1–4；M45 p4 明确 Coursework 2 Topics 5–9 | Coursework 范围不等于期末范围；用户回答不自动升级为官方公告 |
| 历史风格/复杂度 | M05/M04 的 2024/25 mock；M14 p3 标注的 2021 summer exam 片段；M46 的题干与评分要求 | 旧卷的时长、计算器规则、题型分布、总分不自动成为当前考试规则 |
| 个人笔记与推断 | M01 提供检索线索、用户学习表述；AI 的建议结构/难度推断 | 不将笔记或模型推断写成官方事实，不以确认按钮洗去来源类别 |
| 扩展/未核实 | Above and beyond、来源疑似笔误、无官方解答的 assessment、未读清的截图 | 不把“未检查/无法判断”记为已通过 |

M05 p2：旧 mock 标注 2024/25、2 小时、100 分，A 两题共 55 分、B 两题共 45 分。它支持历史结构观察；本轮章节练习不用复制整卷。p5 Q3(b) 的分段 revenue 提供连续性、极值、二阶判别、单调、比较建议的综合题参照，17 分为整组分值，未提供逐小题官方分值。M04 p6–7 是相应答案，不能冒称完整官方 mark scheme。Q3(b)(vi) Mathematica 指令不采用；Q3(a) ODE 也不采用。

M46 内文为 2025/26 Coursework 1；p4 Topic 2 共 30 分：Q3 求导/分段可导 15 分、Q4 定理论证 8 分、Q5 参数化销售最优化 7 分；p6–7 要求方法、依据和步骤。目录未发现这份作业的配套官方答案。采用其方法深度作参考，不复制未发布答案或声称已核对评分细则。

M14 p3–4 的 2021 summer exam 极限片段是课内转载；不是已取得完整历年真卷。M15 为相关 revision questions，与 M14 页码不同，内容关联不等于相同文件。

### 3.3 Mathematica 与风险片段

M18、M19、M30、M36 登记为 `software_teaching_reference`；M19 p2 为求导指令，p3–8 为绘图示例，p13 的 Maximize 是多变量例子。M45 p4–5 含软件验证/截图要求，仅用于解释 Coursework 2 的要求。它们不改变已确认的软件作答边界；不生成代码任务，也不运行材料中的代码。M05 p5 的软件小问明确排除。

本次发现的检查样本用于开发验证，而非要求先修完教材：

| 来源 | 观察 | 产品处理 |
|---|---|---|
| M34 p14 | 文本提取顺序可能混淆单侧条件；图像可读 | 对照页面，保存正确结构及解析问题，不能只信抽取顺序 |
| M34 p41、M14 p5 | 纯文本层丢失根号等结构 | 标记公式需视觉复核，保留原页；本轮必须检验公式解析 |
| M34 p28、M35 p12 | “local” 定义的量词写成全域，疑似源文错误 | 保留来源原文并记录冲突；生成采用经核验的数学定义，不静默改原件 |
| M33 p22 | 指数/对数逆关系显示为 1，疑似源文笔误 | 该表达不进入可信公式集合，需解释/核验，不能复制 |
| M06 p3 | 计算在 x=1，结论一处写 x=0 | 记录局部不一致；不因此废弃整份文档 |
| M48 p20 | “What is wrong” 故意给出错误的 L’Hôpital 推导 | 作为诊断/反例题，不能当正确答案训练样例 |

### 3.4 输入包与练习规模建议

首轮主输入包建议选 M34、M35、M48、M06、M33、M05、M04、M46、M14、M15，10 个唯一文件、179 页；M32 的 58 页作为前置知识与 syllabus 的补充解析输入，合计 **11 个唯一文件、237 页**。M15 可复用对应问题证据检索，不重复放进每个模型上下文。M01 和 Mathematica 文档只登记用途，默认不进入出题依据包。其余目录保留清单，不要求首轮将 51 个唯一文件全部投入分析。

建议 `chapter_practice`，大题数允许 **2–4**，默认 **3**；题型为 `calculation`、`explanation_proof`、`applied_optimisation`。大题可混合题型，题型和知识标签落实到作答单元；不以“一大题只能一种类型”误拒绝合理组合。选择的每类题型至少有一个对应作答单元，否则蓝图校验失败。无 MCQ、通用长篇 essay 或软件题。

以下只是待确认蓝图示例，**Design example — not a generated result**：

| 配置 | 建议结构 | 分值/时长建议 | 覆盖 |
|---|---|---|---|
| Exam-standard / 3 | Q1 求导 12 分，3 小问；Q2 定理 8 分，2 小问；Q3 应用 10 分，3 小问 | 30 分 / 40 分钟；全必答；实际小问须符合已确认蓝图 | K1/K2/K5/K3/K4；轮换其余目标 |
| Foundation / 3 | 同三类，明确中间提示、简单函数与边界 | 建议 30 分 / 35 分钟，仍由蓝图提出并确认 | 不降低答案完整性 |
| Challenge / 3 | 参数分支、条件论证、综合最优化 | 建议 30 分 / 45 分钟 | 仅加深范围内推理 |
| Exam-standard / 4 | 四大题，可增加隐函数或 L’Hôpital | 示例 40 分 / 55 分钟；小问示例 3/2/3/2 | 检验结构真实变化 |

这不是“每题固定 10 分”或“每题固定时间”的算法。用户改参数后由 AI②重新提出结构，程序校验，再由用户确认；若超出临时支持范围明确提示，不暗中改回默认。2 道大题也能覆盖多个知识点，不要求每份练习穷尽 K1–K8。每份显示计划覆盖与实际覆盖。

### 3.5 六次真实验收与临时限额

六次顺序建议：R1–R3 同一冻结的 Exam-standard / 3 配置独立生成；R4 Foundation / 3；R5 Challenge / 3；R6 Exam-standard / 4。R1–R3 复用课程版本和确认蓝图，生成输入分别冻结当时历史，以检验新增练习及实质去重。配置相同不要求随机种子相同。R4–R6 各自确认新蓝图。

建议冻结的具体验收配置如下；它们仍须在真实运行前经结构确认，不能把下表当已产生的卷：

| Run | 难度 / 大题数 | 每大题分值；小问数 | 建议分钟 | 计划知识与题型 |
|---|---|---|---|---|
| R1 | Exam-standard / 3 | 12/8/10；3/2/3 | 40 | Q1 K1/K2 calculation；Q2 K5 explanation_proof；Q3 K3/K4 applied_optimisation |
| R2 | 同 R1 | 同 R1 | 40 | 同蓝图，新题；比较输入题与 R1 |
| R3 | 同 R1 | 同 R1 | 40 | 同蓝图，新题；比较输入题与 R1/R2 |
| R4 | Foundation / 3 | 12/8/10；3/2/3 | 35 | 同三类和知识组，增加明确提示，降低组合复杂度 |
| R5 | Challenge / 3 | 12/8/10；3/2/3 | 45 | 同三类和知识组，增加参数分支、条件论证，不扩范围 |
| R6 | Exam-standard / 4 | 10/10/10/10；3/2/3/2 | 55 | Q1 K2/K7 calculation；Q2 K5 explanation_proof；Q3 K3/K4/K8 applied_optimisation；Q4 K6 calculation + explanation_proof |

各次均全必答，三类题型全部选中；小问数建议在这六次中锁定，用于检验真实约束。R6 的四个 10 分只是该次候选结构，不是通用赋分规则。该组合让 K1–K8 在六次集合中都有目标位置，不要求每份卷全覆盖。

每次保存：材料/解析/课程/蓝图/提示词/模型/限额版本，完整尝试链，输入输出用量，真实阶段耗时，题卷、mark scheme、两个 PDF、检查报告、人工评审。失败、取消、超两分钟和修复均保留，不用重跑替换失败样本；额外复测单独编号。分析阶段另记录首次冷处理及可复用处理的耗时，不能把一次分析伪装成六次分析。完成判据见第 9 节。

临时参数建议 `r1-limits-proposal-1`，批准后冻结；均非实测能力：

| 项 | 建议限额与行为 |
|---|---|
| 上传 | 数字 PDF；单文件 20 MiB；单课程 100 MiB；最多 30 个上传路径、20 个唯一内容、300 个唯一页。重复路径仍受请求数量限制，内容页不重复计入 |
| 并发 | 本地全局 1 个活跃业务任务；同课程 1 个分析/规划/生成任务；生成内部最多 2 个模型调用并行；解析和 PDF 渲染各 1 个进程槽 |
| 时间 | 分析最长 900 秒，规划 180 秒，完整生成 600 秒，独立重导出 120 秒；超过 120 秒显示目标超时并继续，达到最长上限才失败 |
| 调用 | 每次分析最多 8 次、规划 2 次、完整生成 16 次模型请求，包含传输/结构重试及修复；SDK 自动重试纳入预算，禁止多层叠加 |
| 单调用 | 超时最多 150 秒且不超过任务剩余时间；最多 60k 输入 token、12k 输出 token；实际输出需求超限应拆组或失败，不能截掉答案 |
| 修复 | 每一候选题答集合最多 1 轮内容修复并重新核验；每个调用最多 1 次可重试的传输/结构重试；总预算优先；鉴权、拒绝、无效配置不盲重试 |
| 导出 | 每文件最多 1 次自动重试；之后由用户发起同内容重导出。每个重试任务仍受限额；不触发新题生成 |
| 费用 | 首轮先记录真实用量与价格版本，未取得为 null；不伪设已认可的美元预算。每次真实验收手动触发，调用/token/时限硬闸阻止无限运行 |

两分钟目标仍适用于既定口径的真实分析和完整生成；人为等待确认不计入系统处理时间。阶段① analysis 端点为可审阅草稿就绪；若需澄清分别记录首次响应、后续系统处理与用户等待。generation 端点从正式提交至网页和两个 PDF 齐备并发布。规划单独计时，不能借规划阶段预生成答案缩短 generation。排队和自动重试纳入端到端耗时。

## 4. 页面设计

### 4.1 视觉参考与一致方案

已查看 [Refero 参考页](https://styles.refero.design/style/528eb1d4-8508-4dc6-87b4-c7b92d648dac) 的截图、样式说明和组件说明。截图表现为 Quizlet 风格的浅底、深字、蓝紫操作、几何字体和柔和色块卡片；原页面偏营销，本产品采用工作区的信息密度。

| 采用项 | 来自参考 | 本产品调整 |
|---|---|---|
| 颜色 | 浅灰白背景、白表面、深正文、蓝紫强调、淡紫选择态 | 蓝紫用于主行动/选中/焦点；红黄绿只表示错误、待处理、完成 |
| 字体 | Hurme 类友好几何无衬线，参考列有替代字体 | 建议 DM Sans 400/600，自托管前核对许可；系统 sans 回退。数学独立 KaTeX，不用 UI 字体硬排公式 |
| 层级 | 轻边框、圆角卡片、圆角主按钮 | 侧栏 + 工作内容；表格列表用于材料，阅读面板用于题卷；不复制 hero、轮播、营销大间距 |
| 组件 | 按钮、输入框、状态标签、内容卡片 | 来源抽屉、保存反馈、结构差异、任务时间线、主动开答案均为本产品建议 |

参考内部冲突采用统一解释：色彩说明曾限制 accent 的 CTA 用途，但按钮说明和截图使用蓝色主按钮，本轮按用户方向及截图采用蓝紫 CTA；不合法的 `#282e3` 取完整 token `#282e3e`；字重统一 400/600，不同时堆 700；导出代码中的 line-height 数值按正常 `24px/1.5` 解释。主按钮用胶囊圆角，输入框和普通按钮小圆角。仅提炼规则，不照搬导出代码。

建议 tokens：

```css
:root {
  --canvas: #f6f7fb;
  --surface: #ffffff;
  --ink: #282e3e;
  --text-secondary: #2e3856;
  --text-muted: #586380;
  --border: #d9dde8;
  --accent: #4255ff;
  --accent-soft: #edefff;
  --danger: #b42318;
  --warning: #8a4b08;
  --success: #167044;
  --font-ui: "DM Sans", system-ui, sans-serif;
  --text-base: 16px;
  --line-body: 1.5;
  --radius-input: 4px;
  --radius-card: 8px;
  --radius-primary: 999px;
  --shadow-overlay: 0 8px 24px rgb(40 46 62 / 10%);
  --space-unit: 8px;
  --content-max: 1200px;
  --sidebar-width: 216px;
  --reader-max: 72ch;
}
```

间距用 8/16/24/32；正文 16/24、辅助 14/20、页面标题 28/36、节标题 20/28。普通卡片只有边框，抽屉/弹层有阴影。单屏突出一个主行动。建议可点击目标至少 44px、可见焦点、错误文本不只靠颜色；保存/任务变动用适度 `aria-live`。具体色彩对比在实现后验证，不在此宣称达标。

### 4.2 页面流程与导航

```text
/courses/:courseId/materials
  ├─ Upload PDFs / Review sources
  └─ Analyse course → /tasks/:taskId
                         └─ Review course → /courses/:courseId/profile
                              ├─ Answer questions / Edit / Save
                              └─ Confirm course → /courses/:courseId/generate
                                   ├─ Review structure → Confirm structure
                                   └─ Generate practice → /tasks/:taskId
                                        ├─ Needs information → 原编辑页面
                                        ├─ Failed → Retry / Adjust configuration
                                        └─ Complete → /papers/:paperId
/courses/:courseId/papers → 所有本轮结果及未完成输出 → /papers/:paperId
```

左栏固定课程名与 Materials / Course profile / Generate / Papers。活跃任务在顶栏显示 `View current task`。来源统一为可深链的侧抽屉：`?source={evidenceId}`；全页备用路由 `/sources/:evidenceId`。窗口较窄时抽屉变全屏，关闭返回原滚动位置和焦点。

### 4.3 Materials

**任务**：导入 PDF，理解处理结果，修正分类/答案关联，查看证据和重复路径，再发起课程分析。

布局为标题和 Upload PDFs、紧凑上传区、材料列表、右侧来源面板。字段：原文件名、材料角色、版本/页数、处理状态、问题数、关联答案、重复来源。角色建议来自内容，可选 Lecture / Summary / Seminar / Additional questions / Past paper / Answer / Assessment brief / Personal notes / Software reference / Other；一份可含多个用途，不按文件夹名定论。

按钮：`Upload PDFs` 多选及拖放；逐文件上传和重试；`Edit type` 保存 revision；`Link answers` 指定试卷与题号/页范围；`View source` 定位原页；`Analyse course` 提交幂等任务并跳转任务详情。成功文件不因同批其他失败被清空。重复显示 `Already imported — parsing reused` 并保留本次路径映射，不再次计入证据权重。替换不覆盖旧版本；首轮不开放完整删除工作流。

| 状态 | 展示与操作 |
|---|---|
| 空 | `Add your course PDFs`，展示支持格式/限额和用途，不要求先凑齐所有类型 |
| 加载 | 文件上传字节进度可测才显示百分比；解析显示实际阶段/页数，不假造整体百分比 |
| 错误 | 文件行显示 `Encrypted PDF` / `Could not read this file` 等，重试或重新选择；局部公式问题显示页码 |
| 超时 | `Still processing — longer than the 2-minute target`，去任务详情/取消；达到上限后才失败 |
| 成功 | `Ready` 或 `Ready with issues`；显示可用证据与受影响片段，是否阻塞由目标范围决定 |
| 长内容 | 文件名可换行/展开，列表分页；页码导航和问题筛选，不一次加载所有页图 |

### 4.4 Course profile

**任务**：核对知识和方法、考试范围与证据，回答必要问题，直接编辑并确认课程版本。

布局：顶部版本和保存状态；左侧知识树/范围，中部可编辑详情，右侧 `Evidence and questions`。字段包括课程名、目标考试标签（可为空）、知识节点、方法/前置知识、范围包含/排除/未知、声明出处、历史风格、建议模板、缺口和冲突。来源标签固定区分 `Course material`、`User-provided`、`Historical paper`、`Personal notes`、`Inferred`、`Unverified`。

`Edit` 直接改字段；`Save changes` 保存，建议 800ms 防抖自动保存作辅助；显示 `Unsaved changes → Saving… → Saved` 或 `Could not save — Retry`。保存请求按 revision 串行；确认只能针对服务器已经保存的 revision。`Confirm course` 展示本版采用的范围、用户声明、未阻塞疑问和影响，成功生成 immutable version 后进入 Generate。`Answer question` 在页面内回答并更新草稿，提供变更摘要。

| 状态 | 展示与操作 |
|---|---|
| 空 | 没有草稿：`Analyse your materials` 回 Materials；已有材料部分缺失可照常分析可用部分 |
| 加载 | 骨架和 `Analysing course`，链接活跃任务；不以旧草稿冒充新结果 |
| 错误 | 字段旁错误；保存失败保留输入；409 revision 冲突暂停自动保存，比较服务器版本与本地修改后再提交 |
| 超时 | 分析继续状态与任务链接；编辑保存网络超时先查询 revision，防止重复确认 |
| 成功 | `Confirmed version 1`，可查看已冻结内容；再次编辑形成新草稿，旧版和已有卷不变 |
| 长内容 | 知识树折叠、按节点定位、证据逐页查看；保存/确认栏保持可见且不遮住末尾内容 |

必要问题示例：`What is the exam scope?`；本次已回答为 `All lecture content`，显示 `Provided by you`，无需再问。对“某公式无法读清”的问题则显示对应页与受影响节点，而不是抽象询问“材料是否完整”。

### 4.5 Generate

**任务**：设置本次章节练习，理解结构与差异，确认后开始生成。

两栏：左配置、右结构摘要。字段：Mode（本轮 Chapter practice）、Topic、Difficulty（Foundation / Exam-standard / Challenge）、Main questions（2–4）、Question types、课程确认版本。右栏展示各大题的目标、题型、小问数、分值、全必答/选答、总分、建议时长、覆盖与建议性质；保留 schema 的选答规则，本轮候选采用全必答，不自动改写已有选择规则。

`Review structure` 创建规划任务；返回后显示与上一结构的差异。`Confirm structure` 将配置 hash、蓝图 revision、课程 version 绑定。`Generate practice` 只有绑定有效时启用，提交后跳 Task detail。可编辑分值/时长/结构，但须重新通过程序检查并确认。

任何章节、难度、大题数、题型或已确认结构内容变化均使结构确认失效，显示 `Configuration changed — review the updated structure`。即使改回原值，也需要明确重新确认；不接受迟到的旧配置规划结果覆盖新表单。修改本次配置不更新课程默认值。

| 状态 | 展示与操作 |
|---|---|
| 空 | 未确认课程显示 `Confirm your course first`，链接 Profile；无选题提示选择章节 |
| 加载 | `Planning structure`，真实任务链接；保留配置可读，防止重复提交 |
| 错误 | 不可行约束具体解释并定位字段；资料缺口只阻塞受影响选择；可调整或回 Profile |
| 超时 | 规划仍运行可取消；不把未完成结构当可确认结果 |
| 成功 | `Structure confirmed` + 版本摘要；生成按钮启用 |
| 长内容 | 结构按大题展开、总分和主按钮固定摘要；长知识列表折叠，不把必需限制藏进 tooltip |

### 4.6 Task detail

**任务**：观察真实执行、耗时、等待信息、错误与可恢复动作。

页面显示任务类型、稳定 ID、输入版本、开始时间、累计系统时间、状态、真实阶段时间线、最近 heartbeat、诊断 ID。生成阶段为 `Preparing evidence → Generating questions and answers → Checking → Repairing (if needed) → Preparing web view → Exporting PDFs → Publishing`。实际跳过的修复标为 `Not needed`，未检查项为 `Not checked`；没有可测分母时不用进度百分比。

`Cancel task` 请求服务端取消；先显示 `Cancellation requested`，服务端确认后为 Cancelled。`Retry failed stage` 创建关联尝试并明确复用范围。`Review questions` 在 needs_info 时回原表单；答案保存后使用新的输入快照。`View result` 只在已发布时成为完成入口；输出失败可看 `Preview — not complete`。

| 状态 | 展示与操作 |
|---|---|
| 空/不存在 | `Task not found`，返回所属课程；未授权不透露任务内容 |
| 加载 | 初次加载骨架；暂时断网显示 `Connection lost — your task may still be running`，不推断后台失败 |
| 错误 | 展示哪个阶段失败、是否可重试、不会丢失什么、诊断 ID；可复制脱敏诊断 |
| 超时 | 超 120 秒显示 `Longer than the 2-minute target`，仍显示实际运行；达到硬上限后明确失败原因 |
| 成功 | 链接唯一结果和两个文件就绪状态；取消与完成以服务端已提交状态为准 |
| 长内容 | 阶段明细折叠；日志用摘要/分页，默认不输出课程全文或提示词全文 |

刷新或重新打开只 GET 原任务，不自动再次 POST。当前任务 ID 存于服务端课程状态；前端 URL 是主恢复入口，本地缓存仅作便捷链接。worker 重启后从持久 checkpoint 领取新执行代次，迟到的旧 worker 无权发布。

### 4.7 Papers / detail

**任务**：找回本轮结果、阅读题卷、主动打开答案、下载两个文件、从原配置再次练习。

列表字段：课程/主题、生成时间、难度、大题数、内容版本、完成/导出失败状态。点击进入 `/papers/:paperId`；历史版本可读，不随当前课程编辑而改变。

详情左侧大题目录，中间阅读正文，顶部配置摘要和 `Download question paper`，独立按钮 `Open mark scheme`。第一次只取题卷数据；答案不预取、不放隐藏 DOM。点击后加载答案视图并显示 `Download mark scheme`。可用显式 `?view=mark-scheme` 深链表达主动访问；普通详情和刷新普通 URL 默认题卷。下载答案本身也属于明确打开行为。

`Generate another practice` 创建新配置草稿，展示当前课程版本与原版本差异，再确认结构，不能重用旧幂等键。`Retry PDF export` 只对原 content version 重导出，页面明确 `The questions and answers will stay the same`。

| 状态 | 展示与操作 |
|---|---|
| 空 | `Your practice papers will appear here`，去 Generate |
| 加载 | 列表/正文骨架；答案点击后独立加载，不影响已读题卷 |
| 错误 | 某 PDF 失败显示文件名和重试；内容已冻结可预览但标 `Export incomplete`，不标全任务成功 |
| 超时 | 显示关联导出任务链接；继续/取消行为同 Task detail |
| 成功 | 同一 content version 的网页、题卷 PDF、mark scheme PDF 均就绪；下载为授权文件接口 |
| 长内容 | 章节锚点、宽公式局部横向滚动、图表可放大；PDF 长题可连续分页，题号与评分点不孤立 |

### 4.8 来源定位与核心布局草图

来源链接必须携带 `material_version_id + parse_version_id + evidence_id`；证据含 1-based PDF 物理页，印刷页码单独显示。两幻灯片拼一页的材料仍按物理页定位，另记页内区域。旧卷引用旧版材料；替换材料不得使旧链接跳到新内容。源不可访问时显示 `Source unavailable`，保留引用摘要和版本，不暗中跳最近版。页面展示已存的原页图与 bbox，高亮对应内容；无可靠 bbox 时标 `Page-level reference`。

以下均为 **Design example — not a generated result**：

```text
Materials · Quantitative Methods
┌──────────────────┬──────────────────────────────────────────────────┐
│ Materials        │ Materials                         [Upload PDFs]  │
│ Course profile   │ 11 unique files · Topic 2 working set             │
│ Generate         │ Name                       Type         Status    │
│ Papers           │ MSIN0180 Topic 2 -         Lecture      Ready     │
│                  │ Lecture 2 11_01_2026,                              │
│                  │ lecture slides (1).pdf           [View source]   │
│                  │ ...lecture slides (2).pdf       Duplicate        │
│                  │ Same content; original paths retained            │
│                  │                                [Analyse course]  │
└──────────────────┴──────────────────────────────────────────────────┘

Course profile
┌──────────────────┬─────────────────────────┬────────────────────────┐
│ Topic 2          │ Knowledge and scope     │ Evidence and questions │
│ Derivatives      │ Exam scope              │ User-provided          │
│ Optimisation     │ All lecture content     │ "All lecture content"  │
│ Theorems         │                         │                        │
│                  │ Selected practice scope │ Lecture 2 · PDF p29    │
│                  │ Topic 2                 │ [View page]            │
│                  │ [Edit]                  │ 1 local source issue   │
├──────────────────┴─────────────────────────┴────────────────────────┤
│ Saved                                    [Confirm course]          │
└────────────────────────────────────────────────────────────────────┘

Generate
┌────────────────────────────┬───────────────────────────────────────┐
│ Chapter practice           │ Proposed structure                    │
│ Topic 2                    │ Q1 Differentiation        12 marks    │
│ Exam-standard              │ Q2 Theorem reasoning       8 marks    │
│ Main questions [3]         │ Q3 Optimisation           10 marks    │
│ Types [✓] [✓] [✓]          │ 3 main · 8 subquestions · 30 marks    │
│                            │ Suggested time: 40 minutes            │
│ [Review structure]         │ [Confirm structure]                   │
│                            │ [Generate practice]                   │
└────────────────────────────┴───────────────────────────────────────┘

Task detail                          Paper detail
┌────────────────────────────┐       ┌─────────────────────────────────┐
│ Generating practice        │       │ Topic 2 · Exam-standard         │
│ Checking · 01:24 elapsed   │       │ [Download question paper]       │
│ ✓ Evidence prepared        │       │ [Open mark scheme]              │
│ ✓ Questions and answers    │       ├──────┬──────────────────────────┤
│ → Semantic checks          │       │ Q1   │ Question paper           │
│ ○ Exporting PDFs           │       │ Q2   │ 1. Differentiation ...   │
│ [Cancel task]              │       │ Q3   │                          │
└────────────────────────────┘       └──────┴──────────────────────────┘
```

这些是低保真布局和行为约定，不是已实现截图。桌面优先；小于 768px 建议侧栏收起、两栏纵向排列，320px 下保留完整操作与单列阅读。固定栏不得遮挡键盘焦点或错误信息。

## 5. 四个 AI 环节与程序职责

### 5.1 共同调用约定

模型只产生候选结构化内容，不直接写数据库状态、不访问任意 URL、不执行课程中的代码、不决定权限或发布。提示词分为固定职责、显式 schema、可信配置、标记为不可信数据的证据。每次记录 prompt/schema/model/parser/limits 版本和输入 hash。供应商输出先检查拒绝、截断、JSON/schema，再检查业务规则；结构化输出不等于内容真实。

统一结果外壳：

```typescript
type StageResult<T> = {
  schema_version: "r1.1";
  outcome: "complete" | "needs_info" | "failed";
  data: T | null;
  issues: Issue[];
  evidence_ids: string[];
};
type Issue = {
  code: string;
  severity: "info" | "warning" | "blocking";
  affected_ids: string[];
  explanation: string;          // English for product display
  evidence_ids: string[];
  suggested_action: string | null;
};
```

所有对象禁止未知字段；字符串/数组长度、数字范围和引用存在性由程序限制。持久 ID 由服务端创建；新输出节点可用响应内唯一 local key，解析后统一分配 ID 并重写内部引用。引用已有材料/证据/课程/题目时只能用输入提供的 ID，不能凭空提供文件路径或假页码。

### 5.2 AI① 课程与考试理解

**提示词职责**：提取课程知识、方法、前置条件；分开教学、当前范围声明、历史风格、个人笔记和推断；识别局部冲突与缺口；给可编辑草稿和有必要的问题。不能凭旧卷覆盖当前声明，不能把用户确认当官方认证。

**必要输入**：选定材料及解析版本、证据块/必要页图、角色和答案关联、已有 UserStatement、目标章节、允许的作答方式、已有草稿人工修改。本轮首次分析不需全课材料。

**输出 `CourseDraftPayload`**：

```typescript
type CourseDraftPayload = {
  title: string;
  target_exam: {label: string | null; academic_year: string | null};
  knowledge_nodes: KnowledgeNode[];
  scope_claims: Claim[];
  method_rules: Claim[];
  historical_style: Claim[];
  template_suggestion: TemplateSummary | null;
  clarifications: Clarification[];
  unresolved_issue_ids: string[];
};
// KnowledgeNode: id, title, parent_id|null, depth, prerequisite_ids[],
// method_ids[], evidence_ids[], readiness: supported|partial|unsupported
// Claim: id, text, subject_ids[], applicability, provenance,
// evidence_ids[], statement_ids[], status: supported|declared|inferred|disputed|unknown
// Clarification: id, question, reason, affected_ids[], impact,
// suggested_answers[], resolves_issue_ids[], status: open|answered|superseded
// impact: informational|needs_confirmation|blocks_selected_scope
```

`provenance` 是 `course_material | assessment_document | historical_paper | user_statement | personal_note | inference | external_source`；另设 `authority_status: attributed | verified | unverified`，不能仅凭文件名将其设 verified。材料署名与当前考试适用性是两个字段。

**校验**：节点引用存在；声明有来源或明确 inference；不同考试/学年的声明不混合；支持内容有教学证据；模板为建议时有标签；对选定章节的真正阻塞问题不能被 complete 掩盖。对无关节点的问题可 `complete + warning`。

**复用/失败**：解析、证据索引可复用；用户新回答只重做依赖变化的分析/合并。保存机器基础、人工 patch 和合并草稿，拒绝让重分析覆盖人工编辑。不可读页是 `unreadable_evidence`；不知道范围为 `needs_info`；供应商故障为 `failed`，三者不同。

### 5.3 AI② 本次组卷规划

**职责**：以确认课程版本和本次参数分配大题、作答类型、知识、分值、时间和素材；说明与参考结构的差异。规划不生成整套题答。

**输入**：CourseVersion、GenerationConfig、范围/方法规则、历史模板建议及校准状态、可用证据索引、支持能力和限额。

**输出 `BlueprintPayload`**：

```typescript
type BlueprintPayload = {
  sections: {
    id: string; title: string;
    question_ids: string[];
    selection: {mode: "all" | "choose"; choose_count: number};
  }[];
  questions: {
    id: string; number: number; knowledge_ids: string[];
    parts: {id: string; label: string; response_type:
      "calculation" | "explanation_proof" | "applied_optimisation";
      marks: number; knowledge_ids: string[]; asset_needs: string[]}[];
    evidence_ids: string[];
  }[];
  main_question_count: number;
  subquestion_count: number;
  subquestion_count_locked: boolean;
  printed_marks: number;
  attempt_marks: number;
  suggested_minutes: number;
  coverage: {knowledge_id: string; question_ids: string[]}[];
  differences: string[];
  calibration: "historical_reference" | "uncalibrated";
};
```

**校验**：大题数与请求一致；题号/part ID 唯一；所选类型被覆盖；分值为允许步长的正数（建议 0.5）；选答数合法且可计算 attempt marks，本轮全必答时两种总分相等；无范围外知识；不把分值/时间从原型机械乘出来。estimated 与 locked 小问数不能混淆，确认时明确。

**复用/失败**：缓存键为 course version + config hash + schema/prompt/limits 版本；只有完全一致才可复用建议。绑定失效后仍需用户重新确认。约束不可同时满足给具体冲突和调整建议，不偷偷删题型或扩大范围。

### 5.4 AI③ 题答及素材生成

**职责**：按已确认蓝图分组生成新题与配套完整解答、建议评分点、必要图表描述。题目和答案在同一产物中成对提交，页面传输再分离。

**输入**：冻结 GenerationSnapshot、指定 question IDs、对应教学证据和历史题参照、已生成其他题的摘要与重复限制、允许素材语法。只传必要片段，不默认把整个目录传给模型。

**输出 `QuestionPair[]`**：

```typescript
type QuestionPair = {
  question_id: string;
  stem: ContentBlock[];
  parts: {
    part_id: string; prompt: ContentBlock[]; marks: number;
    assumptions: string[]; response_type: string; knowledge_ids: string[];
  }[];
  answers: {
    part_id: string; worked_solution: ContentBlock[];
    final_answer: ContentBlock[];
    marking_points: {id: string; text: string; marks: number;
      alternative_group: string | null}[];
    acceptable_alternatives: string[];
    units: string | null; precision: string | null;
    checks: MathCheckSpec[];
  }[];
  asset_ids: string[];
  evidence_ids: string[];
  originality_notes: string;
  marking_basis: "suggested" | "source_supported";
};
```

`ContentBlock` 为受限 union：text、math（LaTeX）、table（列/行）、asset_ref。不接受任意 HTML/JS。`AssetSpec` 为 axis/series/domain/labels 或受限示意图元素；服务端验证范围、采样点数和标签后生成 SVG/PNG。不能让模型代码直接执行。数学检查使用受控表达式树和显式定义域。

**校验**：每个 part 恰有对应答案；答案真实解释推导/论据，案例包含完整示例解答；评分点按替代组计算不会双算；分值与蓝图一致；必要图表存在；不得因缺图让题目无法独立作答。无官方细分分值时用 `Suggested marking guidance`。

评分点规则：`alternative_group=null` 的分值求和；同一非空 group 表示同一个得分机会的互斥表述，按组内最大分值计入满分；各组与独立点的总分必须等于该 part 的 marks。完整替代解法写入 acceptable_alternatives，仍映射既有得分机会，不能额外加分。

**复用/失败**：保存到候选版本而非已发布卷；只可复用输入依赖和组 ID 都相同的完整、已校验分组。缺半份答案不得成功；生成失败可以只重做失败组，但重组后重新做跨题检查。取消后返回的候选不得获得写入/发布权。

### 5.5 AI④ 语义核验与必要修复

程序先检查结构/引用/范围/分值和受支持的数值符号约束，AI 再检查题意、方法、答案论证、范围/难度及实质重复。对代表性数学问题做独立盲解：只给题目与课程方法，不给生成答案，之后程序/评审比较。单模型自洽不能证明正确。

输入为候选 pairs、蓝图、课程版本、上传题与本人同课历史的检索候选及检索覆盖清单、程序检查、盲解结果。输出：

```typescript
type CheckReport = {
  candidate_version_id: string;
  checks: {
    check_id: string; target_ids: string[]; method: string;
    result: "pass" | "fail" | "not_checked" | "inconclusive" | "not_applicable";
    required_for_release: boolean;
    rationale: string; evidence_ids: string[];
  }[];
  duplicate_review: {
    compared_source_ids: string[]; compared_paper_ids: string[];
    retrieval_coverage: string; findings: Issue[];
  };
  repair_requests: {target_ids: string[]; issue_codes: string[]; instructions: string}[];
  coverage_summary: {required: number; passed: number; failed: number;
    not_checked: number; inconclusive: number};
};
```

`pass` 必须有可追踪方法和结论；未运行记 not_checked，条件不足或模型分歧记 inconclusive；不适用有理由。重复检查结合题干、数学结构和解题路径，不能只看词面或数值；报告列实际比较集合，不声称穷尽全部题库。

修复调用仍使用 AI③的 pair schema，只修改指定目标；形成新 candidate version，保留旧版与原因。修复后重跑相关数学检查及整卷结构/范围/重复检查。超出一轮或预算仍存在必需检查失败/无法判断，则任务明确失败或 needs_info，不发布“已核验”结果。非关键未核验项可作为明示限制，但不能以 warning 放行决定答案正确性的缺口。人工离线验收用于评价系统，不设成每份学生卷的额外审批按钮。

## 6. 核心数据、接口与任务契约

以下为首轮推荐 `r1.1` 契约；后端为事实来源，OpenAPI 生成前端类型，Zod 负责界面及时提示。ID 用 UUID；时间用 UTC ISO 8601；hash 用 SHA-256；产品显示按用户时区。JSON hash 采用稳定规范化序列化，不能依赖对象键的偶然顺序。

### 6.1 主要实体

| 实体 | 必需字段与不变量 |
|---|---|
| MaterialBlob | id, owner_id, sha256, bytes, mime, private_storage_key；同 owner 可物理复用，不能跨用户泄露重复信息 |
| Material / MaterialVersion | material_id, course_id, version_id, blob_id, original_filename, imported_path_aliases[], role_labels[], declared_dates, created_at；替换创建新版本，原件不可变 |
| ParseVersion | id, material_version_id, parser_name/version/config_hash, content_hash, page_count, status, issues；同 blob+解析配置可复用解析产物，引用仍绑定具体 material version |
| Evidence | id, material_version_id, parse_version_id, page_start/end, printed_label|null, bbox|null, kind, text/math/asset refs, fidelity_status；页码必须落在真实页数内 |
| MaterialRelation | source_version_id, target_version_id, relation_type, question/page_ranges, status；答案关系只覆盖声明范围，不能自动套全卷 |
| UserStatement | id, course_id, text, purpose, author_id, created_at, supersedes_id|null, supplied_source|null；保存回答原意，来源始终 user_statement |
| CourseDraft | id, course_id, revision, machine_base_id, manual_patches[], payload, material_manifest_hash, statement_ids[]；CAS 保存，不覆盖并发编辑 |
| CourseVersion | id, course_id, draft_id/revision, payload_hash, frozen_payload, evidence_manifest, statement_ids[], confirmed_by/at；确认后不可变 |
| GenerationConfig | id, revision, mode, topic_ids[], difficulty, main_question_count, question_types[], course_version_id；与课程默认值分离 |
| Blueprint / StructureConfirmation | blueprint_id, revision, payload/hash；confirmation_id, config_hash, blueprint_hash, course_version_id, confirmed_by/at；任一绑定变化即无效 |
| GenerationSnapshot | id, config, course_version_id, confirmation_id, blueprint payload/hash, material/parse/evidence manifest, history_cutoff/ids, pipeline/model/prompt/schema/limits versions；任务开始前冻结 |
| CandidateVersion | id, snapshot_id, parent_candidate_id|null, pairs/assets, hash, stage/check refs；不可就地覆盖修复历史 |
| Paper / ContentVersion | paper_id, owner/course, source_task_id, content_version_id, frozen pairs/assets/check report, config摘要, publication_status；网页与两个 PDF 共用同一内容 |
| Artifact | id, paper_id, content_version_id, kind: question_pdf/mark_scheme_pdf, status, sha256, bytes, storage_key, error_id|null；就绪须文件实际存在且通过渲染检查 |
| Task / TaskAttempt / Event | task_id, kind, state, stage, snapshot_id, parent_task_id, retry_of, execution_epoch, cancel_requested_at, started/finished, elapsed, deadline, checkpoint refs；attempt/model usage/stage errors 独立留档 |
| ErrorRecord | code, safe_message, retryable, stage, diagnostic_id, task/attempt IDs, provider_request_id|null；默认不含密钥、全文或完整提示词 |

### 6.2 推荐 API

统一前缀 `/api/v1`。所有资源执行 owner/course 授权；写操作 CSRF 防护，下载不是公开文件目录。错误形状为 `{code,message,field_errors,retryable,diagnostic_id,task_id?}`。

| 方法与路径 | 输入/输出及约束 |
|---|---|
| POST `/courses/{id}/materials` | multipart PDF + Idempotency-Key；返回 material/version、重复映射与解析任务 |
| PATCH `/material-versions/{id}/classification` | expected_revision、角色/关系；返回已存 revision |
| GET `/sources/{evidenceId}` | 返回固定版本元数据、页定位和授权页图链接；页图需同权限校验 |
| POST `/courses/{id}/analyses` | material manifest、statement IDs、目标范围；202 task_id |
| GET/PATCH `/courses/{id}/draft` | PATCH 携带 expected_revision；409 返回当前 revision/差异，不覆盖 |
| POST `/courses/{id}/statements` | 用户回答、clarification_id、expected_draft_revision；返回声明与新草稿/重分析动作 |
| POST `/courses/{id}/confirmations` | draft_id/revision；事务校验后返回 course_version_id；旧 revision 不能确认 |
| POST `/courses/{id}/plans` | config revision/hash + course_version；202 规划任务；结果 blueprint_id/revision |
| PATCH `/blueprints/{id}` | expected_revision + editable structure；服务端重算分值并失效旧确认 |
| POST `/blueprints/{id}/confirmations` | config_hash、blueprint_revision、course_version；返回 structure confirmation |
| POST `/courses/{id}/generations` | confirmation_id、config_hash、Idempotency-Key；只接受有效绑定，返回既有或新 task_id |
| GET `/tasks/{id}` | 状态、实际阶段、累计耗时、target_exceeded、retry actions、相关页面；刷新只读 |
| POST `/tasks/{id}/cancel` | 幂等请求；已成功返回 succeeded，已接受取消后禁止晚到发布 |
| POST `/tasks/{id}/retries` | retry_kind: failed_stage/export、当前输入依赖；新关联 task_id；无法复用时明确说明 |
| GET `/courses/{id}/papers` | 分页列表，包括 export_incomplete；已取消未发布的候选不列成完成结果 |
| GET `/papers/{id}` | 仅题卷/元数据/文件状态，不包含答案正文 |
| GET `/papers/{id}/mark-scheme` | 用户主动请求后才返回答案 |
| GET `/artifacts/{id}/download` | 授权后流式下载；校验 content version 和 ready 状态 |

### 6.3 版本、幂等、取消与唯一发布

业务 Task 与 outbox 同一数据库事务提交；队列只收 task ID。dispatcher 重发可重复，worker 按状态和执行代次幂等领取。不要把队列 job ID 当业务 task ID。

幂等键作用域为 owner + operation + key，保存请求 hash 与响应引用；相同 key/请求返回原对象，key 相同但请求不同返回 409。不同 key 同课程忙碌返回现有活跃任务链接，不启动第二份出卷。`Generate another` 才是新意图、新 key、新历史快照。

状态为 `queued → processing → succeeded | failed | needs_info | cancelled`；needs_info、failed、cancelled 是本次任务的终态，恢复产生关联新任务；超过 120 秒是附加标记，不是终态。取消在服务端事务中确认；发布和取消争同一业务锁，先提交的终态决定结果。已成功不改取消，已取消不可被迟到结果复活。

worker 有 heartbeat、lease 和递增 `execution_epoch`。恢复领取增加 epoch；checkpoint、内容冻结和发布都验证最新 epoch 及未取消。模型请求无法保证立即停止，但其迟到结果不能发布。长调用 timeout 小于剩余任务预算；关 worker 后可恢复未完成阶段，不能重复消费已完成的发布。

发布条件：必需检查通过、内容冻结、网页可读取、两个真实 PDF 同 content version 且 ready。数据库唯一约束确保每个原始 generation task 至多一个 paper/publication。PDF 失败保留 frozen content 和失败 artifact；重导出产生关联任务，复用已就绪的另一个 PDF，不生成新题、不增加第二份历史卷。原任务保留失败事实；成功恢复通过关联恢复结果说明，不改写首次性能结果。

新材料或人工回答使新草稿/规划依赖变化，但旧任务快照不变。若用户明确取消旧任务再改资料，按取消契约处理。首轮不实现完整删除，但授权或原件不可用时来源引用应明确失效，不能跳另一版本。

### 6.4 文件存储约定

私有数据根为运行时 `APP_DATA_DIR`，不放在前端 public/ 或 Git：

```text
blobs/{owner_id}/{sha256}.pdf
parses/{parse_version_id}/document.json
parses/{parse_version_id}/pages/{physical_page}.png
evidence/{evidence_id}/asset.svg
candidates/{candidate_version_id}/pairs.json
papers/{paper_id}/{content_version_id}/content.json
papers/{paper_id}/{content_version_id}/question-paper.pdf
papers/{paper_id}/{content_version_id}/mark-scheme.pdf
reports/{task_id}/checks.json
```

实际目录可在实现时按此职责细化，但所有文件路径由服务端生成，禁止用户提供任意路径。临时文件原子写入后登记 ready；文件存在不等于业务已发布。question PDF 模板不得收到答案字段，mark scheme 使用同一 frozen content 的答案投影。摘要、题号、页眉和 content version 校验用于核对同版输出。

## 7. 本轮技术推荐与执行前验证

选择优先沿用已确认方向，避免为首轮引入额外服务。以下官方资料查询于 **2026-10-19**；实际安装/真实 API 试用前重新核对可用版本与服务条件。

| 项 | 本轮建议、原因 | 执行前验证 |
|---|---|---|
| 前端 | React/TS/Vite；React Router Data Mode + TanStack Query；CSS Modules + variables；复杂表单 RHF/Zod | 锁定兼容版本；Router 不再建立第二份服务端缓存；复杂弹层按需 Radix，不先装大组件库 |
| 后端 | Python 3.12、Django 5.2 LTS + DRF；drf-spectacular/OpenAPI → TS 类型 | Django 5.2 的 LTS 支持与安全补丁；DRF、schema 工具兼容；具体补丁在实施时锁定。[Django 官方](https://www.djangoproject.com/download/) |
| 数据/任务 | PostgreSQL + Procrastinate；业务任务/outbox/恢复独立于队列 | 当前官方支持和 Django 集成、事务 enqueue、取消/重复投递/worker 重启；项目招募维护者的维护风险需验证，不因已有推荐而忽略。[官方文档](https://procrastinate.readthedocs.io/en/stable/index.html)、[Django 集成](https://procrastinate.readthedocs.io/en/stable/howto/django/basic_usage.html) |
| PDF 解析 | Docling 作正式数字 PDF 候选；保留原页图和区域；首轮默认不启用 OCR，不调用远端解析；pypdf 只做轻量文件核对 | 模型权重是否需下载、许可、离线 artifacts_path、CPU/内存/公式位置质量；公式 enrichment 需单独启用验证，不默认存在。本次 pypdf 审计不代表 Docling 已跑通。[高级选项](https://docling-project.github.io/docling/usage/advanced_options/)、[CLI](https://docling-project.github.io/docling/reference/cli/) |
| 模型接入 | 首轮直接官方 Responses API，候选 `gpt-6.1-sol`，默认 medium；同一模型先形成可比较基线；按题组并行，上限 2 | 账户模型访问、地区、schema/图像输入、推理预算、拒绝/截断、超时、真实质量/用量。必要盲解可评估 high，但须独立配置记录，不隐式变更。无真实测量前不承诺两分钟。[模型页](https://developers.openai.com/api/docs/models/gpt-6.1-sol)、[结构化输出](https://developers.openai.com/api/docs/guides/structured-outputs) |
| 代理 | 不将现有 LiteLLM 作为本轮正式依赖；单供应商直连少一层故障与配置 | 若后续需要跨供应商路由再比较；保留当前准备文件 |
| 数学核验 | SymPy 仅用于受支持表达式/定义域；程序校验 + 独立盲解 + 语义报告 | 不把不可信字符串直接交 `parse_expr`/eval；采用受限 AST 构造、复杂度/时间上限；符号失败标 inconclusive。[SymPy 说明](https://docs.sympy.org/latest/modules/parsing.html) |
| 网页/PDF | KaTeX + 可信 HTML 打印模板 + Playwright/Chromium；字体/数学就绪后导出 | KaTeX 宏支持、trust=false、长题分页、公式根号/上下标、SVG、答案隔离；浏览器包下载属正式实施准备。[KaTeX 选项](https://katex.org/docs/options)、[PDF API](https://playwright.dev/python/docs/api/class-page#page-pdf) |
| 本地运行 | 目标为 Linux 容器 Compose，API/worker 分进程，Postgres/私有数据卷；Windows 用已获准的兼容运行方式 | WSL2/Docker 是否已存在、资源和文件挂载行为；不在本阶段安装。若环境未满足，先做契约/纯前端工作，不静默改架构 |

外发只限已授权的必要证据片段、页图和生成内容，不自动上传整个 OneDrive 目录。建议 Responses `store:false`，避免将其误解为零保留；默认滥用监控日志、组织数据设置与特殊保留资格必须按账户情况核实。[官方数据说明](https://developers.openai.com/api/docs/guides/your-data)、[支持地区](https://developers.openai.com/api/docs/supported-countries)。本次没有向模型或外部解析服务发送课程内容。现有“允许考虑海外官方 API”是选型授权，真实试运行仍需落在已确认的数据处理范围内。

不设置未经验证的成本承诺；记录实际模型标识、usage、价格查阅时间及估算公式。缺 usage/价格时为 unknown，不能写 0。供应商失败不静默换便宜模型，否则六次样本失去可比性。

## 8. 开发批次概要

| 批次 | 可审阅产物 | 关键完成条件 |
|---|---|---|
| 1 工程基础、真实 PDF 与证据 | 本地工程骨架、任务基础、上传/解析/来源、版本/重复映射 | 指定真实文件可读取；原件 hash 不变；旧版本来源稳定；失败可定位 |
| 2 课程分析、编辑与确认 | AI①、澄清记录、Profile、保存/确认版本 | 用户声明有来源；缺口按目标判定；并发编辑不覆盖；确认只绑定已保存版 |
| 3 配置、蓝图与结构确认 | AI②、Generate、蓝图约束 | 题量/题型生效；参数变化失效确认；不能提交旧结构 |
| 4 题答、核验与修复 | AI③/④、候选版本、检查报告 | 完整成对题答；故障注入被拦；一轮修复可追踪；未检不伪装通过 |
| 5 网页、两个 PDF、结果找回 | 阅读/答案主动打开、PDF、唯一发布、恢复 | 同内容两文件；失败重导不换题；刷新/取消/重启不重复发布 |
| 6 集成与六次真实验收 | 冻结 manifest、六份完整运行记录及报告 | 所有失败保留；质量/功能/性能分别结论；明确本轮与全 MVP 差距 |

具体文件、签名、测试断言、计划命令和提交点见配套文件级计划。命令均是拟实施方案，不表示已运行。

## 9. 验收口径、待确认决定与可独立推进项

### 9.1 第一轮如何判定

每份真实卷必须符合确认结构，所有作答单元有可自查解答与评分点，题目可独立作答，不含未解决的严重数学/范围/题答对应错误，必要素材齐全，网页和两个 PDF 同版可读。全部结构检查必须通过；范围、重复和数学检查报告必须说明实际覆盖和未判断项。严重问题不能用总体平均分抵消。

人工评审建议记录逐题 `correct / minor_issue / major_issue / cannot_judge`，范围符合与否、与课程方法一致性、难度/风格评价及证据。`cannot_judge` 不计为正确。主观难度/风格、实质重复、核验覆盖率等具体阈值应在六次正式运行前冻结，遵守 PRD 参数 V 的要求；本设计不捏造已批准阈值，也不把模型自评分当 gold。

首轮报告分别给出：功能闭环、内容质量、恢复可靠性、分析耗时、完整生成耗时、成本与未验证边界。若质量/功能满足而超过 120 秒，写“首轮闭环可用，性能目标未达”，保留失败结论和改进项；不能称全 MVP 验收通过。完整 MVP 的 18 任务 × 3 次等要求仍有效，本轮六次不能抵扣为全部完成。

### 9.2 集中确认的决定

1. 是否采用本轮六批次，以及 Topic 2 / 三类作答要求 / 2–4 大题 / 默认 3 大题的建议；初始结构和时间分值均以蓝图确认，不设固定乘法规则。
2. 是否采用参考提炼的浅色工作区及五视图交互，尤其来源同版定位、课程与结构双确认、主动开答案和同内容重导出。
3. 是否采用本轮技术候选与临时限额；真实 API 前再核对账户、外发范围、保留设置和运行环境。无需先补齐所有 QM 材料或官方期末公告。

### 9.3 启动条件与独立工作

方案确认后，可先独立推进 Git 基线、工程骨架、数据库/任务契约、离线接口样例、页面布局、文件 hash/来源 viewer、编辑版本和故障测试。材料范围声明已有用户输入，不再作为设计阻塞。

依赖真实环境的事项按时点处理：数据库/worker 集成需运行环境；正式解析需验证 Docling 与权重；API 试跑需凭据和数据处理范围；六次验收需冻结质量阈值、评审人和运行版本。它们应写进实施任务与产品澄清流程，不要求现在一次问清所有未来参数。

## 附录 A. 材料审计与版本说明

审计根目录：`C:/Users/Yijia/OneDrive/past_paper_generator/Quantitaive methods`。下表路径均相对此根，保留原拼写和所有重复别名。M01–M51 是此次审计用内容编号，不是未来数据库 ID。相同 SHA-256 表示字节相同，解析可复用；文件名相近或知识相同不能据此合并。

本次对 65 个路径计算 SHA-256；对 51 个唯一 PDF 读取页数、元数据、首部与文本层，并检索相关范围/考试表述；均未报告加密或页读取异常。另对 33 个关键页面作图像核对，重点为 Topic 2、assessment、mock、笔记及源文问题。**没有逐页目视核验全部 1,107 页，也没有运行正式解析器或质量验收。** 读到文本不等于公式/图表已正确解析。

版本优先以内容 hash 标识；下表元数据日期只是文件生成/修改线索，不证明课程正式发布版本。文件名日期、内文学年、PDF 元数据冲突时分别保存，不猜“最新”。例如 M05 内文 2024/25；M45/M46 内文 2025/26，文件名 10_12_2025、元数据为 2026 年 1 月；M40、M42 等文件名与生成日期也不同。PowerPoint/assessment 模板的年份不是该讲义的版本。

材料角色依据内容核对，课程出处为材料自带署名/版式，不声称已与学校外部系统认证。M01 是含中英笔记与截图的汇编，作为 personal notes/unverified；M02 与 M13 是不同文件，不能因同属 Topic 3 additional questions 合并。M14/M15 是问题与带讲解版本的关系；M04/M05 为旧 mock 答案关系；其他 seminar/additional 的解答通常内嵌，是否覆盖某小问须按页关联。

| 内容 ID / 路径（重复别名全部保留） | SHA-256 | 页数 / 字节 | 角色 | PDF 元数据生成 / 修改日期 |
|---|---|---|---|---|
| **M01**<br>`39183fc0-eb33-4b7a-af78-1c61ce6be2ac_Quantitative_methods_for_business.pdf` | `26f5e98c43f73adaef11ea23d01daa734344231902c6478259693938bffe705d` | 69 / 10,782,102 | 个人笔记/截图汇编；出处未核实 | 2026-05-12 / 2026-05-12 |
| **M02**<br>`exam resources/additional question 3.pdf` | `61caa454c0a8756c140abfc3573c8494e938c5151a28773a37808685981bfc53` | 4 / 130,589 | Topic 3 additional questions；2 slides/page | 2026-02-03 / 未提供 |
| **M03**<br>`exam resources/Additional questions Topic 4 29_01_2026.pdf`<br>`lecture slides/Additional questions Topic 4 29_01_2026 (1).pdf` | `4b5db1037fad4b0dc0349558667aeea4dbfde94236fdaada00eb8d614db05c11` | 6 / 230,235 | Topic 4 additional questions | 2026-01-29 / 2026-01-29 |
| **M04**<br>`exam resources/Mock exam - answers 04_02_2025.pdf` | `a516b4a24571d3673d6a96d980561e768f2f543c5b9755caa7e226a99d4f668c` | 8 / 227,411 | 2024/25 mock answers；关联 M05 | 2025-03-27 / 2025-03-27 |
| **M05**<br>`exam resources/Mock exam - questions 04_02_2025.pdf` | `909871e303e65a1ec508c77cd610a2adb4acad4b36879dcbd1e7be17786f0ec5` | 7 / 265,972 | 2024/25 mock questions；关联 M04 | 2025-03-05 / 2025-03-05 |
| **M06**<br>`exam resources/MSIN0180 - Topic 2 - additional questions and answers 11_01_2026.pdf`<br>`lecture slides/MSIN0180 - Topic 2 - additional questions and answers 11_01_2026 (1).pdf` | `831eacd2089bb5e1b0e1bebc0f12cd7a9c808a697f5df25c01ca9c790b2128e6` | 8 / 188,206 | Topic 2 additional questions + embedded answers | 2026-01-11 / 2026-01-11 |
| **M07**<br>`exam resources/MSIN0180 - Topic 5 - Additional questions 05_02_2026.pdf`<br>`lecture slides/MSIN0180 - Topic 5 - Additional questions 05_02_2026.pdf` | `164b969fff24d68af0a23c70de54fdb1c66d6013f1d8b3d697fc82f9b69483b3` | 11 / 300,590 | Topic 5 additional questions | 2026-02-05 / 2026-02-05 |
| **M08**<br>`exam resources/MSIN0180 Topic 1, additional questions and answers 04_01_2026.pdf`<br>`lecture slides/MSIN0180 Topic 1, additional questions and answers 04_01_2026 (1).pdf` | `7c02e671675824377377633bad93ad13d95c00c28344bc9a4e033f5039a79c22` | 26 / 393,971 | Topic 1 additional questions + answers | 2026-01-04 / 2026-01-04 |
| **M09**<br>`lecture slides/lecture3 bg.pdf` | `f11f2aa621bb3ec477b1e9a932abcdf5c83721b3c3d943615b0235c6bd16a581` | 15 / 609,872 | Topic 3/4 mathematical background | 2026-02-03 / 未提供 |
| **M10**<br>`lecture slides/lecture3.pdf` | `992ecc89a69a32d1cad62c472b8749027189d03c2bb8f5b2a61be7a166b64e7a` | 9 / 331,379 | Topic 3 lecture summary | 2026-02-03 / 未提供 |
| **M11**<br>`lecture slides/lecture4 bg.pdf` | `a540ca5552410577135241247041f53bf849d5878bbb1b4f2400f1854a972c30` | 10 / 346,937 | Topic 4 mathematical background | 2026-02-03 / 未提供 |
| **M12**<br>`lecture slides/lecture4.pdf` | `6c3405e39d2e11598f85bd2a5f320d65819cfd2b962002fd850813cbe04e1528` | 8 / 348,895 | Topic 4 lecture summary | 2026-02-03 / 未提供 |
| **M13**<br>`lecture slides/MSIN0180 - Additional questions for Topic 3 29_01_2026 (1).pdf` | `9821b49b2426df970fd5d7fc109ae0c13cb510b16e62998303b64c4925829414` | 7 / 142,833 | Topic 3 additional questions；不同于 M02 | 2026-01-29 / 2026-01-29 |
| **M14**<br>`lecture slides/MSIN0180 - Calculus - Revision 19_03_2026.pdf`<br>`MSIN0180 - Calculus - Revision 19_03_2026.pdf` | `63e09f3f2e61e463ec0852fc93722b17f8535d7fe6d8c739e2bf05c312175471` | 15 / 321,087 | Calculus revision + worked explanations | 2026-03-19 / 2026-03-19 |
| **M15**<br>`lecture slides/MSIN0180 - Calculus - Revision questions 19_03_2026.pdf` | `56f970c1d414fbe31585c7f4c384880312184832b03588cf18d32c6cef46b55b` | 9 / 188,294 | Calculus revision questions；关联 M14 | 2026-03-19 / 2026-03-19 |
| **M16**<br>`lecture slides/MSIN0180 - Lecture 10 -  slides 18_03_2026 (1).pdf` | `a9ad959c2f4ae7869dae14cf7269f83decb440b9fa1e633bd989354bcd72bcee` | 23 / 433,008 | Lecture 10；p15 LU 标注 Not for exam | 2026-03-18 / 2026-03-18 |
| **M17**<br>`lecture slides/MSIN0180 - Math Background for Topic 5 05_02_2026.pdf` | `68f7a7dc79b6f093741b0823f15963f9010024564fa37c1cbadd7b5b3dbaf375` | 17 / 330,588 | Topic 5 mathematical background | 2026-02-05 / 2026-02-05 |
| **M18**<br>`lecture slides/MSIN0180 - Mathematica for topic 1 15_02_2026 (1).pdf` | `0ee3ef8d68eb59d78fe68a399b0a8f642401b46ba921a9f0242cd0d1b9256471` | 15 / 446,077 | Mathematica Topic 1；软件教学参考 | 2026-02-15 / 2026-02-15 |
| **M19**<br>`lecture slides/MSIN0180 - Mathematica Topics 2, 3 and 4 26_02_2026 (1).pdf` | `fde121838f1d49cd2cfe51aaab0408da43e5b9476a6510fccdd2db8808cdb4e6` | 15 / 501,309 | Mathematica Topics 2–4；软件教学参考 | 2026-02-26 / 2026-02-26 |
| **M20**<br>`lecture slides/MSIN0180 - Topic 3 - Lecture slides 25_01_2026 (1).pdf` | `69d86005b78b995226b4c7054a3346c529ebaf1e89ae8002a684f6c46cdc5afd` | 44 / 1,757,640 | Topic 3 lecture | 2026-01-25 / 2026-01-25 |
| **M21**<br>`lecture slides/MSIN0180 - Topic 4 - Lecture 29_01_2026 (1).pdf` | `2ecdb27600cd14b3d46a61ef458327b80db68ac8e6d05b8b408e1c9a5084ca10` | 43 / 981,053 | Topic 4 lecture | 2026-01-29 / 2026-01-29 |
| **M22**<br>`lecture slides/MSIN0180 - Topic 5 - lecture slides 05_02_2026 (1).pdf` | `df0c2e3f9195bb803f9efcc4e12b15ea16a71a59178d7578518d56b569e273a1` | 51 / 1,000,632 | Topic 5 lecture | 2026-02-05 / 2026-02-05 |
| **M23**<br>`lecture slides/MSIN0180 - Topic 6 - Additional questions 15_02_2026.pdf`<br>`MSIN0180 - Topic 6 - Additional questions 15_02_2026.pdf` | `02fddefa818d349efbd82d8931a2513d46ee5d5da70fd8fefda6da673b67dbd1` | 8 / 229,270 | Topic 6 additional questions | 2026-02-15 / 2026-02-15 |
| **M24**<br>`lecture slides/MSIN0180 - Topic 6 - lecture 12_02_2026 (1).pdf`<br>`MSIN0180 - Topic 6 - lecture 12_02_2026 (1).pdf` | `46f3e2dad6fb7819f1ac6798ada33776a7dcf6f1caee4f5d1aadea15f96c85a8` | 58 / 1,257,157 | Topic 6 lecture | 2026-02-12 / 2026-02-12 |
| **M25**<br>`lecture slides/MSIN0180 - Topic 7 - Lecture 26_02_2026 (1).pdf`<br>`MSIN0180 - Topic 7 - Lecture 26_02_2026 (1).pdf` | `6943dba42e3ec27c6bf42e5734e9f100a0c8ea1123d6a7add6617d0c25c2c9fa` | 32 / 1,101,422 | Topic 7 lecture | 2026-02-26 / 2026-02-26 |
| **M26**<br>`lecture slides/MSIN0180 - Topic 8 - Lecture 05_03_2026 (1).pdf`<br>`MSIN0180 - Topic 8 - Lecture 05_03_2026 (1).pdf` | `af4635dc7cd1ae33b3cc44c2d063cf9d2d895e0021c6378baed137d862d16531` | 49 / 688,488 | Topic 8 lecture | 2026-03-06 / 2026-03-06 |
| **M27**<br>`lecture slides/MSIN0180 - Topic 8 -Additional questions 05_03_2026.pdf`<br>`MSIN0180 - Topic 8 -Additional questions 05_03_2026.pdf` | `6c6a2b00f8fe19773d137183000813e02f08be3c80165edb61f8b79825e6987c` | 10 / 272,907 | Topic 8 additional questions | 2026-03-05 / 2026-03-05 |
| **M28**<br>`lecture slides/MSIN0180 - Topic 9 - Additional questions 12_03_2026.pdf`<br>`MSIN0180 - Topic 9 - Additional questions 12_03_2026.pdf` | `b8a23c2dcb082c1f6add798700b0bf77fefb9fa39d0648dc09f5b7dd45bdfac9` | 8 / 254,466 | Topic 9 additional questions | 2026-03-12 / 2026-03-12 |
| **M29**<br>`lecture slides/MSIN0180 - Topic 9 - Lecture - Determinants 12_03_2026.pdf`<br>`MSIN0180 - Topic 9 - Lecture - Determinants 12_03_2026.pdf` | `be1f9433fd823105b1f2da5f225c7ae6fbbb875d10134276fcdd706a29c4f59d` | 44 / 662,660 | Topic 9 lecture / determinants | 2026-03-12 / 2026-03-12 |
| **M30**<br>`lecture slides/MSIN0180 - Topics 5, 6, 7 - Mathematica 26_02_2026 (1).pdf` | `65b9c0187dc28a44427647f2abba777a6f442c9dcf94ef67a1a66d4077ba7215` | 14 / 309,583 | Mathematica Topics 5–7；软件教学参考 | 2026-02-26 / 2026-02-26 |
| **M31**<br>`lecture slides/MSIN0180 -Linear algebra revision 25_03_2026 (1).pdf` | `7c7d326cddcea6b5648b6d2e5aa536cdec2b52b31a673b3a11b572f7887c7ec8` | 21 / 382,391 | Linear algebra revision；p15 LU 标注 Not for exam | 2026-03-25 / 2026-03-25 |
| **M32**<br>`lecture slides/MSIN0180 Lecture 1, lecture slides, 11_01_2026 (1).pdf`<br>`lecture slides/MSIN0180 Lecture 1, lecture slides, 11_01_2026.pdf` | `f8b1c05d476118f825544a651348038c041fbae6322ec3ed6911c74fbb5d93b4` | 58 / 999,349 | Lecture 1 / introduction / Topic 1 / teaching syllabus | 2026-01-11 / 2026-01-11 |
| **M33**<br>`lecture slides/MSIN0180 Math Background for topic 2 11_01_2026.pdf` | `c360cae7e3d00adb1373d2c01c708e69e0c27ccdb2f88e5dee3e5e138cefc08c` | 26 / 584,286 | Topic 2 mathematical background | 2026-01-11 / 2026-01-11 |
| **M34**<br>`lecture slides/MSIN0180 Topic 2 - Lecture 2 11_01_2026, lecture slides (1).pdf`<br>`lecture slides/MSIN0180 Topic 2 - Lecture 2 11_01_2026, lecture slides (2).pdf` | `74296ca24bba7732303ff66b741b5616f08ee679305e5c2ce2c809c593cddc60` | 57 / 1,011,381 | Topic 2 Lecture 2 | 2026-01-11 / 2026-01-11 |
| **M35**<br>`lecture slides/MSIN0180 Topic 2 - Lecture summary 11_01_2026.pdf` | `d470abd9f0234f46b21f057f4fd0d47440c713ce2a9dd82f69975786666a7c9a` | 19 / 360,099 | Topic 2 lecture summary | 2026-01-11 / 2026-01-11 |
| **M36**<br>`lecture slides/MSIN0180- Topics 8 and 9 -Mathematica  19_03_2026.pdf` | `038f3bd419d4c6b50407f84c95ee5413671f2e230e2db86fc14375b7ad3335fb` | 23 / 346,496 | Mathematica Topics 8–9；软件教学参考 | 2026-03-19 / 2026-03-19 |
| **M37**<br>`MSIN0180 - Topic 6 - Seminar  15_02_2026 (1).pdf` | `c1f0dd207d911156e768c297869824c6618f9e928bfb9780c1fd7ada30f3965a` | 24 / 636,724 | Topic 6 seminar | 2026-02-15 / 2026-02-15 |
| **M38**<br>`MSIN0180 - Topic 6 - summary 12_02_2026 (1).pdf` | `6d93c48ea47119e47163d2d0d6965e373a53510d0a5bf6369d0cf4bfd433e79b` | 11 / 258,633 | Topic 6 summary | 2026-02-12 / 2026-02-12 |
| **M39**<br>`MSIN0180 - Topic 7 - Lecture summary 26_02_2026.pdf` | `b4c9f992e09dede1dfa798536a092b7a2cb6ba2f5048899bbfc37978d507c29f` | 12 / 444,982 | Topic 7 summary | 2026-02-26 / 2026-02-26 |
| **M40**<br>`MSIN0180 - Topic 7 - seminar 26_02_2026 (1) (1).pdf` | `c96b3bb3e7e4525643086c3a84672c19885884ffaa12047d92db02418c2ddad3` | 15 / 431,739 | Topic 7 seminar | 2026-03-05 / 2026-03-05 |
| **M41**<br>`MSIN0180 - Topic 8 - Lecture summary 05_03_2026 (1).pdf` | `8dc349177bc8e42ec8856fa2a8d77503018648466f44ccc63a27038a37bc88a6` | 21 / 330,846 | Topic 8 summary | 2026-03-05 / 2026-03-05 |
| **M42**<br>`MSIN0180 - Topic 8 -Seminar 10_03_2026.pdf` | `fbda323750781268bc473d10ea185ff23290fc20ca407a853a9d93d08dcbf2d8` | 23 / 424,115 | Topic 8 seminar | 2026-03-13 / 2026-03-13 |
| **M43**<br>`MSIN0180 - Topic 9 - Determinants -Seminar 17_03_2026.pdf` | `5869481928e73bc1eb4064ae9f59a0f9fccbee89e9a4317185e377fcdd003f32` | 25 / 448,588 | Topic 9 seminar / determinants | 2026-03-17 / 2026-03-17 |
| **M44**<br>`MSIN0180 - Topic 9 - Lecture summary 12_03_2026 (1).pdf` | `63bcddd4c55dd92ef578787ec63d0240db9b47032f96def2a62312d4530d2498` | 16 / 313,532 | Topic 9 summary | 2026-03-12 / 2026-03-12 |
| **M45**<br>`MSIN0180 Coursework 2 Brief 10_12_2025.pdf` | `cef9cced2bfea17294031a22abc8d24510f41a0235a999d3de3402ad4f21d438` | 7 / 257,614 | 2025/26 Coursework 2 brief；Topics 5–9 | 2026-01-04 / 2026-01-04 |
| **M46**<br>`MSIN0180Coursework 1 Brief 10_12_2025.pdf` | `7f8bd04c80f53078064a3e93ccc50695b1ee65f0882d7098e40a77d185c5707f` | 7 / 256,035 | 2025/26 Coursework 1 brief；Topics 1–4 | 2026-01-05 / 2026-01-05 |
| **M47**<br>`seminar slides/MSIN0180 - Seminar 4 29_01_2026.pdf` | `7f34d39bf98857d63cb6569ce695c9025d8afd20bfc99a218925088d560415fb` | 21 / 694,859 | Topic 4 seminar | 2026-01-29 / 2026-01-29 |
| **M48**<br>`seminar slides/MSIN0180 - Topic 2 - seminar 11_01_2026.pdf` | `21275c7f9001cf44a07076ceaf17169545f13171e9fba550823e175911438ca8` | 23 / 515,555 | Topic 2 seminar + embedded worked examples | 2026-01-11 / 2026-01-11 |
| **M49**<br>`seminar slides/MSIN0180 - Topic 5 - Seminar 05_02_2026 (1).pdf` | `e3dba7f5544340cdd4ddd8a3cd4574318af8020aa062f947cae552a5dfbfcb08` | 20 / 457,362 | Topic 5 seminar | 2026-02-05 / 2026-02-05 |
| **M50**<br>`seminar slides/MSIN0180 Topic 1, seminar 11_01_2026.pdf` | `7536e5d1d8a7428b22c673c3a9d094be5161ae379ad233184e54088667e9de02` | 24 / 463,428 | Topic 1 seminar | 2026-01-11 / 2026-01-11 |
| **M51**<br>`seminar slides/seminar3.pdf` | `4014924fe71a03e12ce1ec9a0186e1b865b29b3e983f2302077bec0e90d24427` | 11 / 528,471 | Topic 3 seminar；2 slides/page | 2026-02-03 / 未提供 |
