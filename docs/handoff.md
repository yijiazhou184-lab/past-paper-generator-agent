# 交接：批次 4 本地完成，真实生成待精确范围授权

更新：2026-10-25，Codex。工作目录仅为 `C:\Users\Yijia\dev\past_paper_generator`；OneDrive 副本停用。接手按 AGENTS.md 第 6 节执行 status、pull --ff-only、README、log 和本文件。用户已经明确批准批次四正式开发，不要再要求确认实施计划。

## 已完成

首轮 Task 7–8 本地功能：独立生成预检授权、按大题成对生成、受限素材、程序/数学/盲解/语义/重复检查、一轮定向修复、候选及报告不可变历史、显式打开答案、固定来源、刷新与幂等恢复。迁移 generation.0003 / 0004 已应用；没有增加依赖。详细文件和检查结果见 [batch-4-validation.md](batch-4-validation.md)。

- 后端初次全量 179 passed；新增预检/execution/pairs 21 passed；修复数学冷启动后 checks/execution/repair 23 passed。数字有重叠，不是独立用例数之和。
- 前端 15 passed，类型检查、生产构建通过；Django check、迁移一致性、OpenAPI 类型通过。
- Playwright Chromium 本机实际可用；已跑独立 B4-FIXTURE 的本地 API + worker 完整页面验收，8 组断言通过、无浏览器 JS 错误，包括丢失响应恢复同一任务、显式答案请求、来源和 390px 布局。
- 早期任务轮询竞争已修复。原符号检查把冷启动算进 8 秒，繁忙时误超时；已改成 20 秒启动上限 + 每项计算 8 秒、同轮复用隔离进程。超时仍 not_checked 并阻止放行，失败记录未删除。
- 未将题卷发布为 Paper，未开发两个 PDF，也未进入第五/六批。

## 下一步：只剩本批真实验证

用户已收到本次精确范围授权问题，尚未收到允许。没有新增真实 generation 任务、GenerationGrant 或本批 provider 请求。不要把前批分析/规划授权当成出题授权，也不要重新询问已确认的开发计划或模型时限。

1. 让用户查看已生成的本地清单 `var/batch4-generation-preflight.md` 和完整 `.json`。context hash 为 `9992277e6ca50e4556da7587f075afadd2ca869c97348af46e19957374b9e294`。若输入/提示词/schema变化，重新生成预检并只就变化后的实际范围确认。
2. 获得该范围授权后，按现有网页/API提交一次真实生成及检查；不得自动重复未知付费请求。流程使用真实 QM 已确认 version 2、快照 `7e2a758e-7e7e-4a03-b618-e7c12d56b708`，3 大题/13 小问/60 分、建议 95 分钟。
3. 预检包含 30 页文字或保存转写：M05 mock p1,3,5；M06 additional p2,6；M34 Lecture 2 p14,28–33,41,46–49；M35 summary p4–6,8–10,13,14,17；M48 seminar p19–22。其中9页进入比较集合；另有冻结课程/方法/蓝图/配置/用户声明偏好和派生题答核验内容。无新页图。
4. 官方 OpenAI Responses API，当前模型 gpt-6.1-sol，store:false；最多16次模型调用及对应计数请求、单次240秒、任务600秒、并发最多2、修复1轮。密钥留在 .env.local，不读出或打印。
5. 无论通过、needs_info、失败或超时，如实记录真实耗时/tokens/检查门槛和可找回结果；对照固定材料抽查题答，标记“Codex 抽查”，不当认证。更新 README/验证记录，提交并push。用户只要求批次四，暂不自动进入批次五。

若授权未到，代码和本地验收已经可交付，不应为等待许可重复开发或继续生成 fixture。

## 服务与数据

`scripts/local.py start` 已复核能复用当前服务，网站 http://127.0.0.1:5173，API8000，PostgreSQL54330，worker/dispatcher运行。真实课程 11 个导入 blob 哈希一致；真实课程内容和历史原型未改写。最后页面记录在 `var/batch4-browser-check.json`，截图在 `var/screenshots/batch4-*.png`；精确输入、截图、数据、原材料和 .env.local 被 Git 忽略。

原有真实课程情况沿用批次三交接：45页分析、32页有视觉结果、8知识组supported、0目标阻塞；现有两条用户练习偏好只用于这门课程，不提升为官方事实或全产品默认。未授权的其他页仍未发送。

尚未验证真实题答质量/难度、实际扣费、两分钟完整出卷、PDF及六次验收。旧“本机无Chromium、批次四未开始”的交接描述已过时。
