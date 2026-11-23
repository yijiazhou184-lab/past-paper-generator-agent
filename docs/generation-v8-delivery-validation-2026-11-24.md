# generation-v8 已保存题卷交付补验

2026-11-24（Asia/Shanghai）。按用户要求完成第一条待办，补齐任务 `9b948991-2a7f-428e-93d7-ef874a0c8702` 的双 PDF 与独立逐小问审阅。

## 结果

- 3 道大题、9 个小问、45 分，独立复算、解答推理、评分点合计、单位和精度核对通过。
- 题卷 4 页，评分细则 12 页。真实网页提交一次导出，任务 `8b0c8d91-ab53-41f5-a602-a2c2afa5bb2b` succeeded，提交至完成 12.964 秒。
- 两份 PDF 均绑定内容版本 `97a42166-8d55-4a91-99ca-931222080c7a`，下载字节和 SHA-256 与数据库 PDFArtifact 一致，保存内容哈希验证通过。
- 原任务必要检查为 62/62 通过。本次离线重放的 26 项必要程序／数学检查全部通过。
- 模型调用记录前后均为 362，本次新增模型请求和输入计数均为 0。

## 环境和回归

干净 main 执行 `git pull --ff-only`，返回 Already up to date，基线为 `940d1dd`。通过 `scripts/local.py start` 恢复本项目服务。

首次定向回归复现 5 项失败，均因当前 Python Playwright 缺少 `chromium_headless_shell-1248`。执行项目虚拟环境的 `python -m playwright install chromium`，安装匹配浏览器及其配套运行文件。随后相同命令 **5 passed / 49.74 秒**。

```powershell
& .\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests/test_paper_render.py backend/tests/test_mock_exam_generation.py backend/tests/test_multi_topic_generation.py -q
```

覆盖长表格、图形和公式渲染，非法公式和缺失素材错误，以及混合练习、选答模拟卷、全必答模拟卷的双 PDF。此次验证使用现有实现，产品源码无改动。后端全库及前端测试未重跑。

## 独立审阅

先读取题面，写下独立解题结论，再读取已保存答案比较。独立推导及逐小问证据保存在忽略目录 `var/reruns/f7c7532e-v8/`。

| 小问 | 核对内容 | 结果 |
|---|---|---|
| q1-a | 四个单侧极限及分支使用条件 | 通过 |
| q1-b | 双侧极限判据与点值区分 | 通过 |
| q1-c | 内点连续性证明、正切定义域和相对定义域解释 | 通过 |
| q2-a | 对数定义域、乘积／商／链式求导及化简 | 通过 |
| q2-b | 三次逐阶求导和指定点代入 | 通过 |
| q2-c | 零点差商、非零点求导、两列反例及光滑性范围 | 通过 |
| q3-a | 对数真数正性、复合连续性和端点 | 通过 |
| q3-b | 一二阶导数、驻点、二阶分类及零二阶导数的不确定结论 | 通过 |
| q3-c | 候选完备性、端点比较、全局最优、货币单位和取整 | 通过 |

额外用 SymPy 交叉检查导数、驻点二阶导数与最优利润取整，逐一断言小问和答案 ID 对应、评分点合计等于小问分值，总分为 45。没有发现本次题答中的阻塞性数学错误。课程来源注记沿用冻结版本，本次未重新逐页认证原材料，也未进行新的全历史实质重复专项审阅。

## 网页与文件

真实 Chromium 浏览器核对 3 大题、9 个小问和 9 个答案。默认未请求答案，点击 Show answers 后读取，刷新后关闭。JavaScript 错误和 KaTeX 错误均为 0。唯一业务写请求为本卷 PDF 导出。

16 页全部渲染为 PNG 并查看，公式、分段函数和表格可读，未见文字截断、遮挡或关键内容缺失。保留非阻塞问题，题卷第 2 页及部分答案页留白较多，评分仍有单数 “1 marks”，题干内题号与模板题号存在重复。此次作为保存结果的交付验收记录。

本机证据包括 `saved-content.json`、`questions-review.json`、`independent-review.txt`、`review-results.json`、`browser-evidence.json`、`v8-questions.pdf`、`v8-answers.pdf` 及全部页面 PNG。确定性检查报告为 `var/generation-audit-9b948991-2a7f-428e-93d7-ef874a0c8702.json`。题答、课程数据及 PDF 均保持被 Git 忽略。

## 交接与边界

结束时前端 5173 和 API 8000 的 session 端点均 HTTP 200，活动任务 0，服务保持运行。原生成耗时 482.568 秒，加本次导出 12.964 秒，合计约 495.533 秒，120 秒目标仍未达成，用户等待间隔未计入。

本次完成该已保存题卷的交付补验。整卷检查按审阅点名修复的真实路径仍未触发，R2、R4/R5、完整模拟卷和跨课程事项继续按原记录跟踪。
