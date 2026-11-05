# R1 Repair Diagnostics Implementation Plan

> **Execution:** 按本聊天已授权范围顺序实施；本侧聊不使用子代理，不新设审批或真实模型调用。

**Goal:** 使每次定向修复收到明确、完整、符合检查器能力的失败信息。
**Architecture:** 程序输出结构化诊断并构造修复约束，模型建议只作参考；保持现有检查器与一轮修复，不扩展根式点表示。
**Tech Stack:** Django、Pydantic、现有隔离数学子进程与 pytest；无新增依赖。
**Spec:** 本聊天用户 2026-11-06 明确引用并确认的四项 R1 要求；docs/PRD-v1.0.md；AGENTS.md。用户要求细化后直接实施，优先于技能的额外确认与代理安排；本会话不用子代理。

## Global Constraints

- 不写死题号、课程、函数、材料页；根式案例只在测试和离线回放。
- 保留候选、旧报告、必要 gate、一轮修复、版本和调用限额；未知结果不重放。
- 不发送真实模型请求；旧失败状态不改；不增加根式检查器能力。

## Review Focus

- 不支持的 points 表达式必须定位到数组下标，不能只返回笼统异常。
- 必要 not_checked/inconclusive 同样进入失败清单，不能依赖模型提供 repair_requests。
- 泛化异常或缺少位置/理由时不能盲目付费修复。
- 修复不能删除/降级被阻塞的核心检查；新候选必须再核验。
- 旧报告可读，新诊断/提示词进入新输入哈希。

### Task 1: 具体数学诊断

**Files:** 新建 backend/app/generation/math_diagnostics.py；修改 math_worker.py、math_checks.py、checks.py；测试 backend/tests/test_repair_diagnostics.py。
**Interfaces:** diagnose_spec(raw:dict)->list[dict]；每项含 code/category/field_path/actual_value/allowed_format/message/actionable。math_check 添加 question_id/part_id/check_id。
- [x] 写不支持数字、域边界、AST 数字、错误结论、未知异常的失败测试。
- [x] 运行确认失败；实现格式预检及错误传播，保留 fail/not_checked/inconclusive 的真实含义。
- [x] 验证隔离子进程与父进程均保留诊断，核心项仍阻塞。

### Task 2: 完整修复输入与约束

**Files:** 修改 repair.py、prompts/repair.md、review_policy.py；新增 repair_diagnostics.py；测试 test_generation_repair.py、test_repair_diagnostics.py。
**Interfaces:** build_repair_failures(pair,checks)->list[dict]；repair 请求携带 failures、原题答、checker_contract、protected_check_ids、固定结构与允许编辑项。保留原 local_checks 兼容读取。
- [x] 写无模型请求仍能收集必要失败、无可执行原因时不调用、核心检查删除/降级拒绝的测试。
- [x] 根据程序诊断构造操作要求；模型建议不得覆盖格式约束。明确禁止对数字字面量问题采用加括号或同义根式字符串。
- [x] 修复输出仍经全部原核验；提升 generation pipeline 版本绑定新行为，不改旧快照。
- [x] 运行 test_repair_diagnostics、generation_repair、math_capability、generation_execution；离线核对原 R1 诊断但不重发或发布。

### Task 3: 验证与交接

- [x] 执行独立测试库命令：scripts/test_batch5_backend.py -c pytest.ini tests/test_repair_diagnostics.py tests/test_generation_repair.py tests/test_math_capability.py tests/test_generation_execution.py -q。
- [x] 记录实际结果与边界，更新 README / handoff，稳定提交并 push；不纳入用户其他文件。

## 实施与验证记录

已按本方案实施；实际文件、测试、兼容边界和交付状态见 [2026-11-06 验证记录](../../repair-and-course-confirmation-validation-2026-11-06.md)。真实 R1/E1 未重跑，旧结果不改。Git 提交/推送结果以最终交付记录及 git log 为准。
