# 交接：批次 4 首次真实运行已记录，修复已本地验证

更新：2026-10-26，Codex。工作目录仅为 `C:\Users\Yijia\dev\past_paper_generator`；OneDrive 副本停用。接手遵循 AGENTS.md 第 6 节。用户已批准批次四开发，常规修复无需逐批再确认；下一次真实模型运行须区分此前“一次运行”的授权。

## 本次目标与结果

用户要求“核查原任务及调用记录，排查错误，无错误后继续任务”。中断提交经核查没有创建任务、授权或调用记录，随后使用原幂等 key 创建唯一真实任务：

- 任务 `344da144-1127-46b2-b137-4707f98a6a04`，页面 http://127.0.0.1:5173/tasks/344da144-1127-46b2-b137-4707f98a6a04 。
- 原 context hash `9992277e6ca50e4556da7587f075afadd2ca869c97348af46e19957374b9e294`；用户已明确允许此范围运行一次，现已执行完毕。
- 终态 failed / GENERATION_NEEDS_INFO，保存了 revision 1 的 3 大题、13 小问、60 分题答和检查报告，没有 revision 2，没有发布。
- 9 次模型调用和 9 次官方输入计数均 completed；9 个模型响应 parsed。修复 q1/q2 返回 needs_info，不是 API 超时或未知结果。
- 提交至结束 385.842 秒，执行 385.064 秒；输入 164,364、输出 38,472、合计 202,836 tokens。实际账单未查询。
- 原报告 54 个必需项：15 pass、39 not_checked。不能称为题答通过或两分钟达标。原结果与错误保留，不改历史状态。

## 本地修复和验证

已修复：受限 AST 的分数/无穷区间/2–4 项加乘兼容；比较片段因阈值全部丢失；修复缺少实际检查诊断、比较片段及职责说明；跨题修复 target_ids 未缩小；修复 needs_info 未保存候选/报告入口；计数请求令用量汇总变成 unknown；手机任务页长调用标识溢出。

检查器契约现进入冻结 context，pipeline 为 generation-v2；旧 hash 不授权新上下文。语义提示词区分“完整报告”与“所有检查通过”；代码仍阻断每个必需非 pass 项。修复提示词不能要求模型假装运行检查、放宽定义域或删掉必要检查。

- 全量后端：195 passed（139.79 秒）；此前针对性 47 passed（95.48 秒），与全量重叠。
- 前端：15 passed；类型检查、生产构建通过。
- Django check、迁移一致性和 git diff --check 通过；没有新增依赖/迁移。
- 真实历史任务只读浏览器：5 组断言通过；题答分离、原报告、固定来源、刷新、390px 和无 JS 错误；阻止写请求，0 新模型调用。
- generation-v2 独立合成课程 `593b0b6e-7768-4140-b71d-a81edabf7aa7`；任务 `f252278c-ac9c-417e-bcce-3f0a6baa9811` succeeded；完整本地 worker/网页 8 组断言通过，模型调用 0。

只读离线回放：原候选程序/数学必需项 23，21 pass、1 not_checked、1 inconclusive。剩余 q1-d 全域绝对值可微性、q1-e 隐式关系定义域不能由当前检查器完整判定。比较池 9 页，实际返回来自 8 页的 9 个去重片段，各大题有 6 个候选。未做新语义审阅，未覆盖或提升原报告。

## 下一步与真实调用边界

本批计划要求的一次真实运行已完成并如实记录失败；修复后的真实 AI③/④ 验证尚未执行。用户没有授权无限重试。**不要用原“一次运行”授权自动再开付费任务，也不要恢复旧 context 到新代码后当作同一次未完成运行。**

修复版预检已准备：

- `var/batch4-generation-preflight-v2.md` / `.json`。
- hash `2c01982cb2c17aab36141f4dee249e4a8a6a1f06fb4a872849c796fdcdd52114`。
- 与原任务的完整 input 结构相等：同一课程 version 2、快照 `7e2a758e-7e7e-4a03-b618-e7c12d56b708`、30 个物理页；没有新增材料或页图。
- 变化为冻结检查器契约、pipeline 和修复/语义提示词。若再修改提示词或契约，重新生成预检，不沿用此 hash。
- 若用户授权再运行一次：官方 OpenAI Responses、gpt-6.1-sol、store:false；最多 16 次模型调用及对应计数，单次 240 秒、任务 600 秒、最多一轮修复，未知结果不自动重试。未创建新 GenerationGrant 或真实任务。
- 运行后如实保留任何失败、无法判断或耗时超标；不能保证更换输入后必定通过，不通过时不得发布。

可独立推进：检查器对分段/隐式约束的设计和本地单元验证、检索质量和性能分析。是否继续这类扩展按用户指令；不要静默扩到第五批/PDF/六次验收。本次未进入第五批。

## 服务、证据与复查命令

服务仍运行：http://127.0.0.1:5173，API8000，PostgreSQL54330，worker/dispatcher；API 已重启加载修复。复用/补起用 `scripts/local.py start`。

```powershell
# 两项均不调用模型，不改原任务、候选和报告
& .\.venv\Scripts\python.exe scripts/audit_generation_task.py 344da144-1127-46b2-b137-4707f98a6a04
& .\.venv\Scripts\python.exe scripts/test_retained_generation.py 344da144-1127-46b2-b137-4707f98a6a04
```

审计 `var/generation-audit-344da144-1127-46b2-b137-4707f98a6a04.json`；真实浏览器 `var/batch4-live-browser-audit.json`；合成浏览器 `var/batch4-browser-check.json`；截图 `var/screenshots/`。敏感数据、预检全文、原材料、环境和 var 均不进 Git。详细结论见 [batch-4-validation.md](batch-4-validation.md)。内置浏览器 open 请求返回 queued；实际页面由 Playwright 验证，不能把 queued 称为用户已看到。

尚未完成：修复后真实运行、真实原创性/难度校准、账单、两分钟完整出卷、Papers/两个 PDF、六次验收。课程材料和原型未改写。
