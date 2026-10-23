# Batch 3 Blueprint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落实首轮 Task 5–6：独立练习配置、可校验和编辑的蓝图、绑定版本的结构确认及不可变生成输入。

**Architecture:** 沿用 Django/PostgreSQL、持久任务及官方 Responses 适配器。配置用 CAS revision；蓝图每次修改保存独立不可变修订；确认绑定配置 revision/hash、课程版本及蓝图 hash。React Generate 页面只展示当前绑定的结构，旧任务可查看但不覆盖新配置。

**Tech Stack:** 现有 Python/Pydantic/DRF、React/TypeScript/TanStack Query、Vitest、Python Playwright；本批不新增依赖。

**Spec:** [首轮计划 Task 5–6](2026-10-19-round-1-qm.md)、[首轮设计 §4.5/5.3/6](../../round-1-design.md)、PRD P0-07/AC-07-01–04、P0-12/AC-12-01。

## Global Constraints

- 用户已授权按批次直接开发；本补充不重复设置审批。模板中的两个 superpowers 执行技能当前未提供，沿用本会话原生执行，不创建子代理。
- 保留所有原材料、历史结果和课程草稿。真实 QM 仍 needs_info，不替用户确认。fixture 与 live 从数据库贯穿到 UI。
- 2–4 大题、三档难度、三类作答要求；分值以 0.5 为步长，总分由程序汇总。选答结构保留并检查可计算性。
- 任何已保存配置变化递增 revision；改回原值也需重新规划/确认。未保存变化即时禁用确认/冻结。
- 规划最多 2 次调用、180 秒任务截止、每次最多 150 秒、60k/12k；不重放未知模型结果。真实规划需要本用途的精确输入授权，不沿用第二批课程分析授权。
- 本批结束于生成输入快照。AI③题答、AI④核验、网页及两个 PDF 属于后续批次；界面不创建假成功生成任务。

## Review Focus

1. 3→4→3 即使 hash 相同，旧确认仍失效；后端修订绑定与前端编辑标志均检查（Task 5/6）。
2. 旧规划迟到或取消后返回，不能覆盖新配置/发布候选（Task 5/6）。
3. 选答分数不等、重复编号、范围外知识、缺题型及伪造证据必须明确拒绝（Task 5）。
4. 多标签 CAS、未知保存结果、刷新恢复任务与确认；保留本地输入供比较（Task 6）。
5. 跨课程引用、未确认快照、修改后的旧蓝图、fixture 冒充真实、无授权调用均拒绝（Task 5）。

## Task 5：规划及冻结

文件：`backend/app/generation/{models,schemas,planning,snapshots,api,fixtures}.py`、迁移、`ai/prompts/blueprint.md`、`core/management/commands/plan_practice_one.py`；修改 settings/urls/queue/retry。测试 `backend/tests/test_blueprint_rules.py`、`test_generation_snapshot.py`、`test_planning_execution.py`。

接口：`save_config(owner, course_id, expected_revision, payload, key)`；`submit_plan(owner, course_id, expected_revision, context_hash, key, authorize=False)`；`run_planning(token)`；`edit_blueprint(...)`；`confirm_structure(...)`；`freeze_generation(...)`。

- [x] 先写有效两大题混合覆盖、错误总分/选答/证据/题型的断言，运行并确认未实现失败。
- [x] 实现 schema 与独立汇总、模型提示、冻结调用上下文/授权、持久任务和取消/迟到防护。
- [x] 实现配置 CAS、不可变蓝图修订、差异、确认、输入冻结；保留历史截止和空历史集合（Papers 尚未实现）。
- [x] 运行目标后端测试、Django check、迁移检查，完成审阅；后端全量 98 passed。

实际材料：冻结 CourseVersion 中的 Topic 2 目标/方法、M46 coursework 复杂度及 M05 historical mock 风格保持原来源类别；规划只读取已冻结索引与课程描述，不获取新材料。本轮真实课程未确认时只展示返回 Profile 的入口；独立 fixture 用合成证据验证交互。

## Task 6：Generate 工作区

文件：`frontend/src/features/generate/{GeneratePage,StructureSummary,config-state,useAction,types,generate.css}` 及测试；更新 router、TaskPage、OpenAPI/生成类型。浏览器脚本 `scripts/{prepare_generation_browser_fixture,test_generation_workspace}.py`。

布局沿用已批准浅灰白/白面板、DM Sans、蓝紫强调色；左侧本次配置，右侧按题展开的结构。顶部显示课程确认版本及模式，底部显示计算总分、建议时长和当前确认状态；手机改为单列。结构用于说明数学练习的知识与作答要求，不增加装饰性统计卡。

- [x] 测试本地编辑失效、改回不复活、迟到状态不覆盖、刷新保留未知请求 key。
- [x] 实现配置保存、规划范围预览、任务恢复、结构分值/时长/选答编辑、确认、冻结输入和下一批边界提示。
- [x] 运行前端单测/构建；真实本地服务上检查 fixture 完整流程、两标签冲突、旧确认拒绝、真实 QM 无确认入口、手机布局和来源链接。
- [x] 更新 README 与 `docs/batch-3-validation.md`，记录实测与未运行事项；前端 12 passed、第三批浏览器 13 项及课程页回归 9 项通过。

拟运行命令（仅执行后才写入验证记录）：`.venv/Scripts/python.exe -m pytest -c backend/pytest.ini backend/tests -q`；`pnpm --dir frontend test --run`；`pnpm --dir frontend build`；`manage.py spectacular --file contracts/openapi.yaml --validate`；`pnpm --dir frontend api:types`；`scripts/test_generation_workspace.py`。

完成条件：程序裁定结构、旧绑定无法确认/冻结、持久版本可找回、当前页面可操作，未执行真实模型与后续生成明确显示。

2026-10-24 收尾：本地功能与检查完成，真实 AI②调用尚未执行；首轮其余批次未开始。详细命令、修复、fixture ID、真实课程保留状态及启动条件见 [验证记录](../../batch-3-validation.md)。原计划中的 Docker、Node e2e 命令按当前 Windows 实现替换为已记录的本机 Python/Playwright 命令；没有声称运行原拟定命令。
