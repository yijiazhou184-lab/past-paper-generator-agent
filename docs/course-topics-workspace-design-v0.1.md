# 整门课程的 Topic 工作区设计 v0.1

日期：2026-11-01（Asia/Shanghai）。状态：**用户已要求扩展设计与开发计划；本文具体数据契约、布局及分期为推荐方案，尚未实现**。界面、题卷和答案使用英语。

依据：[首轮设计](round-1-design.md)、[四轮路线图](mvp-development-rounds-v0.1.md)、[第五批实测](batch-5-validation.md)及用户提供的 Materials 截图。本次只修改文档；原材料、数据库、服务和代码不变，未执行 Git 拉取、提交或推送。

## 1. 目标、现状与排期

目标：让同一门课的材料、课程理解和练习配置围绕 **Course → Topics → Knowledge** 组织。增加一个 Topic 使用数据与已有流程，不复制一套 Topic 2 页面。

已核对现状：
- MaterialsPage.tsx 的章节卡片及下一步说明写死 Topic 2；材料表没有 Topic 归属筛选。
- ProfilePage.tsx 的 Selected chapter 固定显示 02 / Differentiation & optimisation；课程草稿是一个扁平 knowledge_nodes 列表。
- Generate 的 config.topic_ids 实际指知识点 ID，并非章节；新设计必须区分，不能原地改变旧字段含义。
- courses/context.py 中 PAGE_SELECTION、TARGETS 及材料清单仍与 QM Topic 2 绑定；只做下拉框不能完成新 Topic 的分析。
- 当前 Paper/ContentVersion、课程确认及任务输入已冻结，旧结果不得因新目录结构而重算或改写。

推荐分期：
1. **第六批前置 U1–U3**：章节目录、材料关联和浏览、按章节分析/编辑/确认、从全课程知识树中配置单个章节。建立新 Topic 的真实完整流程条件，保留原 R1–R6。
2. **第二轮首批 U4**：启用跨 Topic 知识点组合、覆盖分配及真实多章节生成；随后再做完整模拟卷。U4 的最终界面现在一并设计。
3. 全面多学科能力包与线上账户仍依四轮路线图推进。这里的 Topic 是同一 Course 内的章节，不是另建一门课。

以上将第六批从纯验收增加了明确的前置开发工作，应在实际开工时作为范围增量记录。第六批单 Topic 能力验收不能冒称跨 Topic 混合生成已完成。

## 2. 全局导航与状态语义

左侧仍为 Materials / Course profile / Generate / Papers，顶部保留 MSIN0180 / Quantitative Methods。课程名称来自课程数据。

统一内部实体 Topic，产品标签统一 Topics；老师材料中的 Chapter 可作为别名/原编号保留。标题和顺序来自登记数据，不按文件名或数组下标推断章节。

- Materials 的 Topic 选择是**查看筛选**。
- Course profile 的 Topic 选择是**编辑与审阅范围**。
- Generate 的 Topic/Knowledge 选择是**本次出题范围**。
- 三者共用目录，但不共用一个会静默改动练习配置的全局 selectedTopic。
- 跨页按钮可以显式携带 Topic 作为导航建议；已有 Generate 草稿只显示“Apply this topic to the current configuration?”，需主动应用。
- 切换页面或 Topic 不发起 AI、不重新确认、不改变任务快照。

Topic readiness 分开呈现：No materials / Needs analysis / Needs information / Ready for review / Confirmed / Changes pending。Parsed 只代表材料解析完成；Confirmed 也须与所选知识点可用性共同判断，不能把整门课所有章节自动标为可生成。

## 3. Materials：按 Topic 查看 Course library

### 布局与主要操作

去掉固定的 Your first practice chapter 大卡片，改成课程材料工作区。保留现有上传与表格样式。

~~~text
Materials                                     [Upload PDFs]
Your course, organised by topic.

Topics                     Course library
[Find a topic...]          [All topics v] [Type v] [Processing v] [Find a material...]
All materials (11)         Showing ... matching materials / ... unique pages
Course-wide                Material                Topics              Type / Status
Topic 2                    Topic 2 Lecture 2...     Topic 2             Lecture / Parsed
  Differentiation...       Mock exam questions...  Course-wide         Past paper / Parsed
New topic [demo]           [View source]            [Manage topics]
Unassigned
[Add topic]                [Review this topic] [Analyse selected topics]

[Processing activity (3)]  collapsed unless attention is required
~~~

线框中的 11 是当前材料总数背景；加入 Topic 后的分组计数和 New topic 均是演示，不能硬编码或伪称已分类。真实示例文件沿用 M34 Topic 2 Lecture 2、M35 Topic 2 Lecture summary、M48 Topic 2 seminar。具体标题显示完整文件名，必要时换行。

行为约定：
- 默认 All materials；点击一个 Topic 显示关联该 Topic 的文件及页段，URL 保留 topic、搜索词、类型和处理状态。
- 特殊入口 Course-wide / Unassigned 不是 Topic 实体，不能作为知识点传给生成。
- 选中 Topic 时，可勾选 Include course-wide materials；展示分组来源，默认仅查看该 Topic 直接关联材料。Course-wide 可随时独立查看。
- 一个 PDF 可关联多个 Topic：例如复习卷跨章节；表格在当前结果中只出现一次。全课程文件/页数按唯一内容统计，不能把各 Topic 页数相加冒充课程总页数。
- Manage topics 打开侧栏：多选关联章节、可选物理页范围、关联说明、来源/人工分类状态；Save topic links 后显示保存反馈。教材归类不等于官方考试范围。
- 上传时可预选当前 Topic，上传前明确显示并允许改为多个 Topic、Course-wide 或 Unassigned。未选 Topic 的上传保留在 Unassigned，不擅自归到 Topic 2。
- 重复文件显示已存在位置，使用 Link existing material 明确追加关联；复用 Blob/解析，不复制原材料或丢掉其他 Topic 的关联。
- Add topic 只创建名称/编号/顺序及归属，不调用模型。可依据 syllabus 提出名称建议，但须显示依据和待确认状态。
- 编辑名称/顺序使用稳定 Topic ID，不使材料链接或知识点身份失效。暂不提供破坏性删除；归档已关联 Topic 需保留旧卷引用，另行实现完整删除联动。
- 旧模型验证横幅合并为 Processing activity，可展开历史记录；需要处理的当前错误单独保留。原 task/diagnostic 不删除。
- 选中 Topic 后 Review this topic 打开对应 profile；Analyse selected topics 先选定范围并展示精确预检，不自动分析整门课。
- 查看来源保持 material_version_id / parse_version_id / physical_page 固定；关闭来源面板恢复原 Topic 筛选。旧链接不能跳到文件最新版本。

### 状态

| 状态 | 行为 |
|---|---|
| 空课程 | Add PDFs / Add topic；显示 Course-wide、Unassigned 空状态，不虚造课程章节 |
| Topic 无资料 | No materials linked to this topic；Upload PDFs / Link existing materials |
| 搜索无结果 | 保留筛选，提供 Clear filters，不冒称课程无材料 |
| 加载/切换 | 保持筛选标题与表头，用局部 loading；迟到响应不能覆盖新 Topic |
| 上传部分失败 | 逐文件结果；成功文件保留，新上传文件暂留结果区，避免因筛选立即“消失” |
| 保存失败/冲突 | 输入与选项保留，Retry；revision 冲突展示差异 |
| 处理超时 | 显示真实 task 状态和 View task；不能按耗时猜测失败 |
| 长目录/长文件名 | Topic 列表搜索，长标题换行；桌面侧栏可滚动，窄屏换成选择器 |

## 4. Course profile：整课概览与按 Topic 编辑

~~~text
Course profile
[Course overview | Topic 2 - Differentiation and optimisation v]
Course version 2                      [Manage topics]

Topic readiness                       Selected topic
Topic 2       Confirmed               [Knowledge] [Scope & methods] [Exam reference]
New topic     Needs analysis [demo]    Knowledge and learning requirements
Course-wide   Review required [demo]   ... editable nodes and evidence ...
                                      Clarifications for this topic
                                      [Save changes] [Review & confirm topic]
~~~

- Course overview 列出全部 Topic 的材料、知识点、证据缺口、草稿/确认状态；显示课程级名称、考试信息、范围声明和共同方法规则。
- 选择一个 Topic 后，仅展示它的知识点、规则、来源、澄清问题及与之相关的课程级声明。课程级声明标为 Course-wide，并链接回共享编辑位置。
- 原 Selected chapter 02 标题改为真正可用的 Topics 选择器；未分析 Topic 显示 Analyse this topic / View materials，不能沿用 Topic 2 的知识点内容。
- 课程名、整体考试信息不在每个 Topic 草稿里重复生成相互冲突的副本。
- 保存继续使用当前串行自动保存、显式 Save changes 和 expected_revision 机制；修改路径按稳定 ID，不能按当前可见数组序号。
- 切换 Topic 时等待正在进行的保存；保存失败提供 Retry save、Stay here、Keep draft and switch。保留的草稿按 course/draft ID 恢复并持续显示未保存状态，不能冒充服务器已保存。
- 分析新 Topic 的结果只合并该目标范围；不得覆盖其他 Topic 的人工编辑。源材料版本、目标 Topic IDs、页段、用户声明、基础草稿 revision 进入任务输入和 context hash。
- 每个澄清问题记录 affected_topic_ids / knowledge_ids。只影响 Topic B 的缺口不阻塞已确认 Topic 2；Course-wide 冲突按明确影响范围提示。
- 用户回答带出处保存为 User-provided statement；不得自动升级成 Official source。分析模型发现未知事项时在产品流程提问。
- Review & confirm topic 展示本次 Topic、知识点、共享规则、证据及未决项；无阻塞后生成新的 CourseVersion。可在概览中勾选多个 ready Topic 批量确认。
- 推荐沿用课程级不可变快照，快照内增加各 Topic 的确认 manifest。新版本保留未改动且仍有效的已确认 Topic 内容，不把其他未审阅草稿一起确认。
- 对未纳入本次确认但有新编辑的 Topic，继续使用明确标识的旧确认快照或显示 Changes pending；新生成若受材料/共同范围变更影响，要求先复核，不能静默沿用旧事实。
- 修改共同考试范围时，列出受影响 Topic；不会因另一个无关 Topic 待补资料就让全课失效。
- 保存与确认反馈写明对象，例如 Changes saved for Topic 2 / Topic 2 confirmed in course version 3。

加载、保存冲突、分析失败/超时显示该 Topic 对应的原任务；刷新恢复 Topic 与 tab。长知识列表可搜索并折叠；确认摘要应明确审阅范围，不要求为查看另一章节而重新确认整门课。

## 5. Generate：从全课程知识树选择出题范围

最终设计支持从不同 Topic 勾选知识点，单 Topic 和多 Topic 共用同一选择器。

~~~text
Generate practice                      Course version [v3 v]
Practice type [Topic practice | Mixed-topic practice | Mock exam]
[Search topics or knowledge...]

Topics and knowledge                         This practice
[-] Topic 2 - Differentiation ...             2 topics / 5 knowledge points [demo]
    [x] Definition and differentiability     Topic 2: 3 selected
    [x] Differentiation rules                New topic: 2 selected
    [x] Stationary points                    Difficulty [Exam-standard v]
    [ ] Implicit differentiation             Main questions [3]
[-] New topic [demonstration]                 Question types [...]
    [x] Knowledge point A [demo]              [Save configuration]
    [x] Knowledge point B [demo]              [Review structure]
    [ ] Another knowledge point [demo]
    Confirmed [demo]
~~~

- Topic 标题可展开；复选框支持未选/部分/全选。点击主题 Select all eligible knowledge 仅选该主题当前版本中已确认且有教学依据的知识点；禁用项显示原因与 Review topic 链接。
- 所有 Topic 可浏览；未确认 Topic 显示状态而非从界面消失。搜索可跨 Topic 找知识点，显示完整 Topic / Knowledge 路径。
- 搜索、折叠、切换过滤器不清除已选项。侧栏显示全部已选 Topic 和知识点，含被当前搜索隐藏的项；可逐项移除或 Clear selection。
- Select all eligible topics 必须显式操作，展示会选多少 Topic/知识点；不能因筛选变化自动扩大范围。
- 单章节模式只允许一个 Topic；选择第二个 Topic 前明确切到 Mixed-topic practice，或保留单章范围。跨章节模式在 U4 后端支持后才可提交；前置阶段可浏览整课目录并配置任意一个已支持 Topic，不展示可提交的伪功能。
- Mock exam 不是勾选 All topics 的同义词：它还依赖考试范围、整卷模板、分区/选答和覆盖规则，在第二轮对应能力完成后启用。
- 修改 Topic、知识点、难度、题量或题型使结构确认失效，改回也必须重新确认；纯浏览筛选不影响配置。
- 所有知识点必须属于同一个冻结 CourseVersion。不得把 Topic 2 的 v2 和 Topic B 的 v4 拼成没有共同版本依据的快照。
- 若勾选知识过多而 2–4 道大题无法合理覆盖，显示具体冲突，建议减少范围或增加题量/使用后续完整卷模式；不悄悄丢知识点。
- 跨 Topic 蓝图显示按 Topic 的计划覆盖、题号、印刷分值、必答/可选覆盖及交叉知识题；单个题可覆盖多个知识点和 Topic，分数不重复累加。
- R1–R6 仍采用全必答；完整模拟卷的选答结构需分别计算 printed / attempt marks 与各允许作答路径的覆盖。
- Topic 内部 readiness 或课程版本变化后，对原选择逐项显示仍有效/需重选/待确认；采用新版本需用户明确应用。
- 预检只组装所选知识及必要共同证据，不因界面有“整门课程”就把所有 PDF、全部页图或旧答案一并发送。
- 页面 Summary 使用 Topics / Knowledge 两个独立计数，不能把现有 topic_ids 长度误报为章节数。

空状态分别指 No confirmed topics、No eligible knowledge、No search results；保存失败保留选中项；蓝图等待/失败显示真实任务；长树支持按 Topic 折叠和搜索。所有禁用项可通过键盘获知原因。

## 6. Task detail 与 Papers 的配套一致性

- 任务标题和冻结摘要显示当次 Topic 名称及知识点，不跟随当前浏览筛选变动；按 Topic 查看阶段覆盖可放入 Run details，真实错误仍在外部可见。
- Papers 列表增加 Topic 筛选与 Single-topic / Mixed-topic 标签；多 Topic 的一份卷仍是一条记录，不能复制到多个历史项。
- Paper detail 显示冻结时 Topic 名称、知识点、课程版本；Generate another practice 先按当前版本核对全部选项，有失效项逐项说明。
- 旧 Paper、ContentVersion、来源和 PDF 不重写。旧记录可通过明确的只读兼容映射显示 Topic 2；不能按当前材料重建旧题卷“来源”。
- 答案主动加载、答案区下方 Generate PDFs、Papers 导出及同内容重试、Run details 折叠全部保留第五批行为。

## 7. 推荐契约与兼容性

以下字段/接口是拟实施方案；具体 migration 编号在开工时按实际仓库确定。

| 对象 | 推荐新增或明确的约定 |
|---|---|
| Topic | id: UUID、course_id、code/name、order、revision、archived、provenance/source_refs；编号不是唯一身份 |
| MaterialTopicAssignment | material_version_id、scope: topic/shared/unassigned、topic_ids、page_ranges_by_topic、revision、provenance；关联变化不改变原文件 hash |
| CourseDraft v2 | topics 目录及 topic 状态、knowledge_nodes[].topic_ids；共同 claim 有 affected_topic_ids（明确 all 或具体列表）；保留人工 patch 与来源 |
| CourseVersion v2 | frozen_payload + topic_manifest（topic_id、确认草稿 revision、证据/关联 hash、知识 IDs）；一次版本包含所有实际被确认的范围 |
| PracticeConfig v2 | schema_version、course_version_id、mode、selected_topic_ids、knowledge_ids；旧 topic_ids 不原地换语义 |
| Blueprint / Task | 从统一课程版本派生目标知识和 Topic 覆盖、范围摘要；新配置/证据改变 context hash |
| Paper | 新卷冻结主题元数据与已用 schema 版本，旧卷 read adapter 只读兼容 |

关键边界：
- page_ranges_by_topic 按 Topic ID 分别保存该材料版本的物理页区间；同一 mock 的不同章节可引用不同页，区间允许重叠。Course-wide 文件的共享页段单列。空白页段不能自动表示获准发送整份文件；发送页清单仍由具体任务预检冻结。
- 一个知识点可关联多个 Topic，保持一个稳定 knowledge_id；勾选与题量统计去重，不能复制成多个作答要求。归属关系来自课程分析/审阅，不以名称相同就强行合并。
- v1 config.topic_ids → v2 knowledge_ids 仅在新配置/新快照边界转换；旧任务重试仍使用原契约。旧 hash、授权、课程和内容版本完全保留。
- 旧材料不得一律回填 Topic 2；只有明确属于首轮 Topic 2 的教学资料可以按已审阅清单建立关联，mock/syllabus 等候选公共资料由用途和页段决定。不确定保留 Unassigned。
- CourseVersion 当前唯一约束为 draft+revision。支持同一草稿 revision 分别确认不同 Topic 时，需调整为包含选择范围与前一确认版本的 confirmation fingerprint；同范围重放幂等，不同范围不得误返回同一确认。
- 新分析不再读取全局固定 PAGE_SELECTION/TARGETS；分析范围从 Topic/材料关联/显式页选择读取。取数候选与最终发送范围分开，必要页图另走原有授权。
- 共享声明或文件替换只标记实际受影响 Topic；旧确认和引用继续可读，新确认保存新 manifest。
- 材料读取、Topic API、确认、生成均校验 Course owner；UUID 或 URL 查询参数不是权限凭证。

推荐 API：
- GET/POST /courses/{id}/topics；PATCH /courses/{id}/topics/{topicId}（expected_revision）。
- GET /courses/{id}/materials?topic_id=...&include_shared=...；PATCH /material-versions/{id}/topic-assignment（expected_revision）。
- GET /courses/{id}/profile?topic_id=...（只读投影）；分析预检/提交接受 target_topic_ids 和明确页清单。
- 既有 draft PATCH 维持稳定 ID path；确认接口增加 selected_topic_ids、expected_revision、base_course_version_id，服务端返回完整确认范围。
- 既有 generation 配置端点接受版本化 v2 body；validate_config 检查所有 selected_topic_ids/knowledge_ids 都属于 course_version。
- Topic URL 不等于任务输入：只有显式提交后的服务端快照是执行依据。

## 8. 视觉、响应式与导航恢复

沿用用户截图的浅灰白/白表面、深色文字、蓝紫主操作，不新增营销式大卡片。新增最醒目的结构是可搜索的 Topic 导航和知识树。

建议 token（仅设计，不修改现有 CSS）：
- page #F6F7FC；surface #FFFFFF；text #172134；muted #526181；accent #5B3FFF；border #DFE3EF。
- DM Sans 用于界面；数学继续 KaTeX；正文 15px / 1.6，标题 28–32px，辅助文字至少 12px。
- 内容表面圆角 10–12px，主按钮 pill，层级主要依靠间距与轻边框；焦点有清楚外框。
- 1440/1024px：全局侧栏 + 页面内约 220px Topic 导航 + 主要工作区；避免三列均固定宽度挤压公式。
- 768px：页面 Topic 导航换成顶部可搜索选择器；Generate 摘要移至主内容之后。
- 320px：纵向布局，Topic 树逐层展开；公式/表格可局部横滚，整页不横滚；固定操作条不覆盖内容。
- 原生 checkbox / select / button 语义，树展开用 aria-expanded，部分选中用 mixed；状态不仅靠颜色。
- URL 建议 Materials: ?topic=<uuid>&q=...&material=...&page=...；Profile: ?topic=<uuid>&tab=knowledge&source=...；未知/跨课程 topic 返回明确反馈。
- 更新来源参数时合并 URLSearchParams，关闭面板只删除来源字段，不能把 Topic 筛选一并清空。
- Generate 已保存选择来自服务端草稿，浏览筛选来自 URL；刷新、后退及迟到请求不能使两者互相覆盖。

## 9. 设计自审与验收对应

| 用户要求/易错点 | 对应设计/实施任务 |
|---|---|
| Materials 按不同 Topic 看 library | §3；U1/U2；跨 Topic 共用 PDF 的计数、页码与筛选测试 |
| Profile 真正切换 chapter | §4；U3；不同 Topic 的编辑、保存冲突、确认隔离测试 |
| Generate 选整课不同 Topic 的知识点 | §5；U3 提供整课目录和单章操作；U4 接通跨章配置、覆盖及实际组卷 |
| 新 Topic 不被 Topic 2 规则接管 | §7；U1/U3 去除上下文常量依赖；E1 新材料完整流程 |
| UI 看起来支持但后台仍单章 | §1/5 能力状态明确；U4 未完成不能提交混合练习 |
| 共享文件/知识点被重复计数 | §3/7；U1/U4 去重与全部选择测试 |
| Topic 切换丢编辑或来源位置 | §4/8；U2/U3 保存、后退、刷新、迟到请求测试 |
| 旧结果因新目录变化 | §6/7；U1 migration 及 legacy hash 不变测试 |

实施计划：[Topic 工作区文件级计划](superpowers/plans/2026-11-01-course-topics-workspace.md)；验收安排：[第六批计划](superpowers/plans/2026-11-01-batch-6-acceptance.md)。以上线框、状态和 API 尚未实现；没有运行页面或模型测试。
