# R1 修复诊断与通用课程确认验证（2026-11-06）

本次仅实施用户在侧聊明确批准的两组方案：R1 明确修复原因，以及通用课程问题/决定/目标确认流程。先使用 writing-plans 细化，再开发；未扩展根式点检查器，没有新增模型阶段、依赖或真实 API 调用。实际仓库为 C:/Users/Yijia/dev/past_paper_generator；OneDrive 历史副本未改。

## 已实现

### R1

- math_diagnostics.py / math_worker.py / math_checks.py 输出 code、category、field_path、actual_value、allowed_format、message、actionable；父层补 question_id、part_id、check_id。超时和子进程异常明确属于检查能力/执行问题，不伪称题答错误。
- repair_diagnostics.py / repair.py 从所有必要非 pass 项构造完整失败清单，带原规格、原题答、检查器契约、固定题目结构及不可删除/降级的核心检查。不能依赖模型自行填写 repair_requests。
- 可执行的格式诊断可以启动原有一次定向修复；无明确原因时记录未修复原因，不消耗盲目修复。根式字符串不能靠加括号修复，必须改为受支持且覆盖同一结论的等价规格，或如实保留能力不足。
- 原一轮修复、完整重查、原候选保存、发布 gate 及预算保留。整卷重复仍仅修复组合中靠后的题，没有扩大成修复整卷。
- 新 pipeline 为 generation-v7-repair-diagnostics；原任务和快照不改。下一次真实运行必须取得新精确预检的授权。

### 通用课程流程

- schemas.py / issue_actions.py / clarifications.py：程序管理单选、多选、明确事实补充、源页审阅、调整范围、信息提示及待审阅；未知类型不自动变成文字框，也不因有几个字符串选项就自动成为可执行偏好。
- 固定选项携带受限 action：practice_preference、adjust_scope、needs_interpretation。课程事实或额外说明需要解释时才标记等待分析；保存不启动任何模型调用。源材料读取失败不能用人的断言代替。
- UserStatement.decision 保存身份、定义版本、作用范围、原始 meaning_key、选择、取代关系及应用要求；创建时间由原有 created_at 保存。一次 0009_user_decision_metadata 迁移，没有改写既有声明。
- decisions.py：有效输入去掉被明确取代的旧声明但保留历史；saved/applied/needs_analysis/needs_scope_review/needs_review 分开。旧自由文字可继续查看，不推断其所有内容都是已应用设置。分析输入还带原决定定义，帮助模型复用语义 key。
- 来源冲突选择只表示本次练习采用的口径；原不确定性保留。范围选择按实际目标 ID 保存，来源属性仍为 user_statement / declared / unverified。
- eligibility.py / topic_confirmation.py：组织目录与可考核目标分开；确认冻结所选目标及必要前置依赖。未选缺口可查看但不误阻塞；必要目标、前置或条件不足仍拒绝。只有明确标为局部例题且同一目标有其他充分教学证据，才可保留为非阻塞提示。
- 已确认目标、相关选择、声明、材料版本变化会要求新确认；新生成不可继续使用过期课程版本。旧任务与结果仍可读。
- API 新增 POST /api/v1/courses/{id}/review-selection，并保留 revision、owner、幂等检查。OpenAPI 与前端类型已同步。
- CourseIssueCard / ReviewObjectives：选择、可选补充、修改选择、保存反馈、失败保留输入、学习目标复选及来源跳转。未保存选择时禁用确认。使用既有风格，仅为新控件补齐布局。

## 本地数据与实际验证

所有后端测试使用随机命名独立 PostgreSQL 测试库；真实密钥移除并阻断未模拟的官方传输。合成课程用于交互验证，不能当作真实课程的 AI 质量结论。

- 后端全量：365 passed / 416.57 秒；最后补齐旧决定定义输入后，课程相关定向回归 38 passed / 28.64 秒（含该补充的新增测试）。此前 101 项关联回归、35 项确认回归也通过；这些属于重叠覆盖，不相加为测试总数。
- 前端 pnpm test --run：36 passed（10 files，10.21 秒）；pnpm build 通过（tsc 与 Vite）。
- Django check：0 issues；makemigrations --check --dry-run：No changes detected；spectacular --validate 通过。local.py 没有 status 子命令，服务实际状态通过进程归属和 HTTP 检查，未将该错误命令计为通过。
- 两门合成课程（History seminar / Life sciences seminar）：浏览器验证固定选择保存、刷新、同版本源页跳转、部分目标确认后进入 Generate；1440/1024/768/390 宽度无横向溢出；0 JS 错误。前置缺口、选项版本变化、越权、并发和幂等由后端测试覆盖。
- 真实 E1 只读：revision 4，0 CourseVersion，旧回答显示已保存/待解释；4 个来源审阅动作、0 个澄清文字框；来源定位到保存的材料版本与物理页；确认仍禁用。登录后 0 写请求、0 JS 错误，未代选或重分析。
- 真实 R1 离线回放：原 task 828c1c21-a550-4c55-b299-a7052020785a 仍 failed；rev2 的 q2-b 两个根式点现在准确定位 points[0]/points[1] 并标 UNSUPPORTED_NUMERIC_LITERAL。必要 gate 保留；q2 两项必要非 pass 进入修复清单。没有发送修复请求。
- 迁移前本机备份 var/confirmation-flow-2026-11-06/before.dump；完整性核对改动前 3,228 条业务记录和 46 个文件均未变化。新增内容仅为迁移与隔离合成样例，模型调用记录 209 → 209。

可复现主要命令（均已实际执行，使用仓库现有环境）：

```powershell
.venv/Scripts/python.exe scripts/test_batch5_backend.py -c pytest.ini tests -q --tb=short -x
.venv/Scripts/python.exe scripts/test_batch5_backend.py -c pytest.ini tests/test_course_decisions.py tests/test_course_issue_flow.py tests/test_course_review_integration.py tests/test_course_analysis.py tests/test_topic_analysis.py tests/test_topic_confirmation.py -q --tb=short -x
.venv/Scripts/python.exe scripts/test_course_confirmation_flow.py --fixture
# 以下命令在 frontend 目录执行
pnpm test --run
pnpm build
```

## 兼容边界与下一步

- 本次证明本地代码与交互修复，不证明新提示词已在真实 R1/E1 上通过。R1 根式点表达式本身仍不受支持；模型能否找到受支持等价验证方式尚未实测。
- E1 旧草稿节点缺少 node_kind，按 objective 保守读取；不会自动把一个有子节点的目标判成目录。可在 Node role 明确改为 Organisational group。旧的人类长文字声明保持已保存、等待解释状态；没有擅自改成新分析已应用。
- 新分析会使用有效声明、原问题定义、当前 schema/prompt；旧预检 826fce3f… 不再代表新输入。本次没有代用户创建或批准新的真实预检。
- 服务使用 scripts/local.py 复用并在 0 活动任务时重载。网页 http://127.0.0.1:5173；E1 页面 /courses/1aeae0e0-c154-4dae-b3e6-fa9b214840d7/profile?topic=2948d0da-c723-4cea-bb6b-386d0be37caa。内置浏览器打开请求返回 queued；页面可访问由 Playwright 实测。
- 批次6的后续真实验收未因本次代码开发自动执行；R1 原失败、R2 skipped、R3–R6 未执行的验收状态保留。

本机证据（均 Git 忽略）位于 var/confirmation-flow-2026-11-06：browser-flow.json、course-0-review.png、course-1-review.png、e1-readonly.json、e1-readonly.png、e1-source.png、r1-offline-replay.json、integrity.json、before.dump。不提交原材料、私密输入、运行数据库或密钥。
