# 交接：批次 4 计划待确认

更新：2026-10-24，Claude Code 交出。按 [AGENTS.md](../AGENTS.md) 第 6 节，接手方先执行 `git status`、`git pull --ff-only`，并阅读 README「当前实现」和本文件。

## 目标

开始首轮批次 4：AI③ 题答生成、AI④ 分层核验与一轮修复，并合并“确认后出题”入口。计划见 [2026-10-24-batch-4-question-generation.md](superpowers/plans/2026-10-24-batch-4-question-generation.md)，状态为**等待用户确认**。用户确认前不要开始编码。

## 已完成（均已提交并推送）

- 视觉证据路径：页级分流（`pdf-route-1`）、页图转写任务（授权、缓存、并行，竖版页缩图）、转写接入课程分析，以及页面展示。记录见 [visual-evidence-validation.md](visual-evidence-validation.md)。
- 课程分析：准入改为官方 token 计数（上限 60k）；单次调用时限 300 秒，其他阶段仍为 150 秒；澄清问题改为选项式作答；已回答的问题不重复询问；用户回答附带原问题（迁移 `courses.0004`）。
- 真实 QM 课程：用户已确认 **version 2**（0 阻塞，8 个知识组 supported，含两条练习偏好：局部极值按邻域定义、critical point 只指 f′=0 的点；有争议的原文按标准解释并注明差异）。
- 批次 3 真实验证完成：blueprint-v2（小问标签只写字母，另有 focus 字段），真实规划得到 3 道大题、13 个小问、60 分；用户已确认结构并冻结快照 `7e2a758e-7e7e-4a03-b618-e7c12d56b708`。记录见 [batch-3-validation.md](batch-3-validation.md)。
- 已确认的设计决定：
  - 批次 4 去掉单独的 Prepare generation，改为点 Generate practice 时自动冻结，经预检授权后出题。
  - “有争议时一律用标准解释”**不**设为全产品默认规则；仍逐个由用户澄清。

## 下一步

1. 请用户确认批次 4 计划，包括建议的生成、盲解、核验单次时限 240 秒；如需调整，先改计划。
2. 确认后按计划第 8 节分 6 步实施，全部使用 fixture。每步测试后单独提交。
3. 实施完成后，先把出题预检的精确输入给用户看，取得授权后再在真实快照上运行一次。

## 约定与注意事项

- 每次真实外发（页图转写、分析、规划、出题）都要用户在对话中按**精确的 scope 或 context hash** 授权；授权不能跨用途沿用。
- 测试 `conftest.py` 会删除 `OPENAI_API_KEY`，防止测试使用 `.env.local` 中的真实 key。此前曾因漏补 mock 向计数接口误发 4 次合成请求，不含课程数据。新增调用路径时，测试必须替换对应的适配器函数。
- 修改数据库结构时，先确认没有排队或执行中的任务，再按 README 执行 stop → setup → migrate → start。只改 API 代码时用 `restart-api`。
- 本机 shell 没有 `pnpm`。前端用 `node node_modules/<tool>/...` 直接运行 tsc、vitest、vite、openapi-typescript。

## 未验证事项

- 所有真实调用的实际扣费，均未查询。
- 页图转写只抽查了 7 页（M35 p4、p7、p14，M05 p3，M46 p3，M34 p47、p49），其余为模型候选，未逐页核对。
- AI② 规划只有 3 次真实样本，其中 1 次 needs_info，不能说明稳定性。
- 课程分析耗时 135–169 秒，超过两分钟目标。出卷耗时尚未测量。
- Python Playwright 回归脚本：本机当前用户没有 Chromium，未运行；安装前需要用户同意。

## 服务状态

本项目的 PostgreSQL（54330）、API（8000）、worker、dispatcher 和前端（5173）仍在运行，由 `scripts/local.py start` 启动。没有排队或执行中的任务。开发库迁移到 `materials.0005` 和 `courses.0004`。
