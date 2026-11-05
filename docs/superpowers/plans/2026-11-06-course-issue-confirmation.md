# Course Issue Confirmation Implementation Plan

> **Execution:** 按本聊天已授权范围顺序实施；本侧聊不使用子代理，不新设审批或真实模型调用。

**Goal:** 通用地处理课程问题、已保存决定、有效输入与按学习目标确认，避免重复询问及材料缺口文字框。
**Architecture:** 扩展现有问题/声明数据，程序决定可用操作和阻塞范围；固定选择可确定性应用，需解释的新信息才等待分析。课程版本冻结所选目标及前置依赖，目录只汇总。
**Tech Stack:** 现有 Django/PostgreSQL、React/TanStack Query、Pydantic、pytest/Vitest/Playwright；不新增依赖。
**Spec:** 本聊天用户 2026-11-06 引用并确认的五项课程流程要求及额外调用边界；docs/PRD-v1.0.md:172–189；AGENTS.md。用户授权细化后直接实施；不另加范围或代理。

## Global Constraints

- 通用课程数据驱动；产品与提示词不得写死数学/QM、材料或页码。
- 用户决定不提升为官方事实、不补造教学依据；必要前置缺口仍阻塞。
- 原分析/确认版本/任务不变；保存选择不启动模型；没有选项不能自动要求自由文字。
- 不增设模型环节、自动重试或实际付费验证；保留源页与已批准数据发送机制。

## Review Focus

- 缺少选项或未知问题应显示审阅操作，不能回退为必填空白。
- 同一决定换问法/ID仍可匹配；选项或范围实质改变则要求复核。
- 新人类确认取代旧临时声明；过期分析不能把已保存决定变回未回答。
- 目录汇总与可考核目标不同；部分目标可用，但必要前置不足必须拒绝。
- 选择/保存/确认并发与失败不能丢用户输入，也不能修改历史来源。

### Task 1: 问题类型与操作

**Files:** courses/schemas.py、clarifications.py；新 issue_actions.py；frontend profile/types.ts、ProfilePage.tsx（拆 CourseIssueCard.tsx）；现有 profile.css；测试 test_course_issue_flow.py、CourseIssueCard.test.tsx。
**Interfaces:** classify_gaps(payload,target_ids) 保留入口；问题 view 追加 kind/actions/options/decision 状态；已知类型有对应操作，未知 fallback=review_required。
- [x] 写资料缺口不含文本输入、未知空选项需审阅、偏好单选/可选补充、提示无需作答的测试。
- [x] 定义来源处理、信息补充、冲突决策、范围调整、提示/审阅的受限操作；链接既有来源和分析页，不增新模型阶段。
- [x] 前端按 action_kind 渲染；所有错误/保存反馈沿用现有样式，固定选项保持可键盘操作。

### Task 2: 决策身份、状态与有效输入

**Files:** models.py + 一次 metadata migration；新 decisions.py；drafts.py、context.py、topic_context.py、analysis.py、API serializers/contract；tests/test_course_decisions.py。
**Interfaces:** decision_identity(question,scope)->(key,definition_hash)；effective_statements(course,topic_ids=None)->list；answer_clarification 扩展 option_ids/可选补充/版本，但保留旧 text 接口。UserStatement 保存结构化 decision 元数据、supersedes、requires_analysis。
- [x] 写固定选择不触发模型、定义/范围改变失效、跨课程越权拒绝、并发 revision、旧文字保留待解释的测试。
- [x] 保存答案后区分 saved/applied/needs_analysis/needs_review；固定选择作为练习偏好直接生效，不认证来源。
- [x] 输入只含有效声明，显式保留被取代声明的引用与历史；更新上下文版本及哈希。旧上下文不修改。
- [x] 新分析按稳定决定身份恢复已有答案；过期的机器结论保留其输入版本，不覆盖后来的人类回答。

### Task 3: 学习目标选择与依赖确认

**Files:** 新 eligibility.py；schemas.py、drafts.py、topic_confirmation.py、generation/config_compat.py / schemas.py；API review selection/确认字段；ProfilePage、TopicKnowledgeSelector；tests/test_course_issue_flow.py、test_course_review_integration.py、topic_confirmation、topic_generation_config。
**Interfaces:** eligible_targets(payload,selected_ids)->含 dependency closure 和具体 blockers 的报告；持久化本 Topic 的选择；confirm_topics 冻结明确选中的目标/必要依赖。node_kind 区分 group/objective；旧记录保守兼容。
- [x] 写不同课程 fixture：目录 partial 不单独阻塞、已支持目标可确认、真实目标/前置缺口拒绝、无关例题不误阻塞、未知/空选择拒绝。
- [x] 支持用户选择当前练习知识；显示每个目标的来源、原因、影响与动作，目录显示汇总而非独立补证据。
- [x] 确认冻结所选范围、有效声明与依赖，生成配置不能选入未确认目标；改变相关选择要求新确认。
- [x] 资料不足仍保留 partial/unsupported，不通过用户点击自动改 supported。

### Task 4: 集成与交付

- [x] 隔离运行课程/章节/配置相关回归，迁移一致性、OpenAPI/typecheck、前端 tests/build；只跑与改动相关检查，必要时全库。
- [x] 用至少两门合成课程验证保存、刷新、单选、来源跳转、部分范围确认及前置拒绝。真实 E1 仅只读观察，不代填新答案或发模型。
- [x] scripts/local.py 复用服务，空闲后正常重载；提供可查看页面。记录 API 调用数不增加。
- [x] 更新 README、验证与 handoff，提交并 push；保留用户其他文档和课件。

## 实施与验证记录

已按本方案实施；实际文件、测试、兼容边界和交付状态见 [2026-11-06 验证记录](../../repair-and-course-confirmation-validation-2026-11-06.md)。真实 R1/E1 未重跑，旧结果不改。Git 提交/推送结果以最终交付记录及 git log 为准。
