# 与课程材料比较的原创性规则调整

> 当前决定（2026-10-31）：统一按题目、答案和评分的实际正确性核验；发现问题后由现有修复阶段处理，不按材料中的错误是否出于教学意图另设分类、禁用或判重例外。此前关于故意错误示例的专门约束已撤销。
>
> 实现状态（2026-11-01）：用户要求的前四项——统一来源判重、精简 `source_overlaps`、接入现有核验/修复、版本绑定与离线检查——已实现。当前 `generation-v6` 已加载到本地服务；真实运行由用户自行发起，旧任务的失败记录不改写，新规则实际质量尚未实测。专门清单、输入传递和提示词约束继续保持撤回。

## 一、来源比较的统一规则

- 题目指题干给出的具体材料，仅数字或记号不同视为相同。
- 结论指要求得出的结果种类，仅最终数值不同不代表结论不同。
- 与课程材料及历年卷比较，题目和结论都相同才判重复；不同题目使用相同标准方法或步骤可以接受。
- 不设置按来源意图、特殊标签或页码触发的额外失败条件。
- 原材料、确认课程、冻结蓝图、历史转写和任务结果保留；原文出现的标签只是来源内容。

## 二、精简语义输出（已实现）

`source_overlaps` 每条保留 `subpart_id`、`source_id`、`same_stimulus`、`same_conclusion`、`note`。

- 不复述两边结论，不要求逐项展开依据，不输出“是否重复”。
- 正常比较 `note` 为 null；疑似照搬或无法判断时才给一句简短说明。
- 判断允许 null，不能把信息不足自动当作 false。
- `same_reasoning` 原本服务于已撤销的例外，不再作为必需输出或判重条件。
- 精简减少的是解释性输出；实际 token、耗时与判断质量需同样例对比，尚未实测。

## 三、最小实施范围（已实现）

1. 复用现有有限范围检索，明确本次需要比较的小问与来源；不对全部小问和全部材料做穷举比较，不另建检索系统。
2. 语义模型返回比较事实，代码按上述两项条件判定 `semantic:qN:originality`。必要事实不足为 inconclusive，审阅未完成为 not_checked；不能按空列表自动放行。
3. 保留现有 NUMBER_SWAP_DUPLICATE 程序检查及分组结果汇总。
4. 复用现有错误记录和一次定向修复，不新增调用阶段或独立修复流程。题答中的实际错误仍由通用数学、逻辑及语义检查处理。
5. 测试覆盖：同题同结论拒绝、不同题共用标准方法接受、仅换数字拒绝、缺失事实不冒充通过、分组汇总与定向修复。
6. 版本已更新为 `generation-v6` / `review-policy-v3` / `originality-policy-v2`，schema、提示词和策略共同进入预检 context hash，运行时核对冻结策略。旧授权不静默沿用；现有课程和已确认结构无需为本次改动重新规划。

## 四、此前撤回专门约束的落实记录

- 删除上一轮新增的标记汇总函数及专用测试，移除规划、出题、核验和修复中的专门输入。
- 删除相关提示词约束和课程分析中的专用 issue 要求；不禁止找错题这一题型。
- 新页图/页面核对输出只使用 parser_loss、source_issue、uncertain。历史类别通过只读兼容保留，既不改写旧来源 hash，也不用于特殊规则。
- 网站操作、数据库结构、生成预算、一般正确性检查和修复边界保持现有机制。本次不发起模型请求或真实任务。
- 2026-11-01 验证：visual_contract、visual_transcription、generation_sources、generation_review_budget、generation_execution 共 67 passed，93.05 秒；独立临时测试库，未调用真实模型。这 67 项属于此前撤回约束的验证；来源判重后续实现的检查见下节。

## 五、实现文件与实际验证（2026-11-01）

| 文件（相对项目根目录） | 已实现职责 |
|---|---|
| `backend/app/generation/content_schemas.py` | 五字段 `SourceOverlap` 契约，两个判断允许 null，短 note 上限 300 字符；模型不再输出 originality 类别的裁决。 |
| `backend/app/generation/source_originality.py` | 复用既有检索，每小问选至多 2 个不同来源页，按两项事实生成必要原创性检查；缺失/冲突事实不能冒充通过。 |
| `backend/app/generation/review_input.py`、`reviewer.py` | 比较材料覆盖已冻结课程和历年卷来源，复用同一份证据正文及既有每大题最多 6 段检索上限；没有新增外部数据获取。 |
| `backend/app/generation/semantic_review.py`、`check_progress.py` | 保存和汇总分组事实与目标，未完成阶段如实保留 not_checked；事实进入报告版本 hash。 |
| `backend/app/generation/repair.py`、`backend/app/ai/prompts/repair.md` | 确定重复使用现有一次修复，仅修相关大题；缺少判断依据本身不要求盲目改题。 |
| `backend/app/ai/prompts/semantic_review.md`、`question_pairs.md` | 说明同题且同结论规则与短事实输出，允许共享标准方法，不引入来源意图例外。 |
| `backend/app/generation/review_policy.py`、`originality_policy.py`、`runtime.py` | 新策略版本与冻结内容校验，预算和调用阶段不变。 |
| `backend/tests/test_source_originality.py`、`test_generation_sources.py`、`test_intra_paper_rule.py` | 三值逻辑、缺失/冲突、来源边界、限定比较目标、定向修复、拆分汇总及中断保存、版本失效检查。 |

实际运行所有 `backend/tests/test_generation*.py`，加 `test_source_originality.py`、`test_intra_paper_rule.py`：**116 passed，168.61 秒**。通过项目虚拟环境 Python 的 `pytest.main`，参数 `-q -c backend/pytest.ini -p no:cacheprovider`；预设随机独立测试库 `test_ppg_generation_v6_<uuid>`，结束后删除。测试适配器使用明确的合成事实，真实模型缺失事实不会由 fixture 补齐。真实 OpenAI HTTP（含计数）被测试拦截。

Django `manage.py check`：**0 issues**；`git diff --check` 通过。无需数据库迁移。现有脚本 `restart-workers` 和 `restart-api` 已成功执行；重启前无 queued/processing 业务任务。

只读浏览器检查：[QM Generate](http://127.0.0.1:5173/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/generate) 显示四大题和已确认结构，Generate practice 可用；历史候选可阅读且答案默认关闭；0 JavaScript 错误，登录后 0 写请求。检查产物在 Git 忽略的 `var/source-overlap-v6-local-check-2026-11-01.json` 和 `var/screenshots/source-overlap-v6-generate.png`。

模型调用记录前后均 153，活动任务为 0。本次未发起真实模型、官方输入计数、规划或生成；未提交网页预检。用户可从原 Generate 入口查看新预检，再自行点击 Start generation and checks。实际 token、拆分耗时和最终质量仍需新任务验证，不能用离线通过替代。
