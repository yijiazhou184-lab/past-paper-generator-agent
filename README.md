# AI Past Paper Generator

当前实现：第一轮 **批次 1（Task 1–2）本地材料工作区及有界 API 接入验证**。可上传数字 PDF、复用重复内容、编辑材料类型和答案关联、查看固定版本的原始页、跟踪/取消/重试解析任务。2026-10-22 已成功完成官方 `gpt-6.1-sol` 的 1 次合成检查及 5 页真实材料识别，结构化输出、来源绑定和选定数学断言通过。此前两次额度错误及充值后的成功尝试均保留。课程分析、组卷、答案生成和两个输出 PDF 尚未实现。

本轮方案已获确认；用户已提供本地 API key，并授权五个指定页的官方 API 验证。需求入口见 [AGENTS.md](AGENTS.md)，实际验证与限制见 [docs/round-1-validation.md](docs/round-1-validation.md) 和 [本次接入记录](docs/batch-1-live-validation.md)。历史原型和原材料保持原位。

## 当前电脑启动（已实际运行）

在项目根目录打开 PowerShell：

```powershell
& .\.venv\Scripts\python.exe .\scripts\local.py start
```

访问 **http://127.0.0.1:5173**，点击 **Open local workspace**。程序检查 API 就绪后才打印地址。重复执行会复用已确认身份的本项目进程，补起已停止的服务。

- `5173`：Vite 前端；`8000`：Django API；`54329`：项目 PostgreSQL。
- worker、outbox dispatcher、API 和前端均在后台运行；日志在 `var/logs/`。
- 数据库在 `var/postgres/`；文件/解析/页图在 `var/data/`；离线解析权重在 `var/models/`。
- 项目进程信息在 `var/services.json`；本地随机密钥和数据库密码在被忽略的 `var/local.json`。不要分享这些文件。
- 当前是绑定回环地址的单人开发工作区，通过显式按钮建立受控本地 Session；所有材料端点有归属校验及 CSRF。它不提供正式邀请/密码登录功能，不应对外暴露。

停止全部项目服务及数据库：

```powershell
& .\.venv\Scripts\python.exe .\scripts\local.py stop
```

修改数据库结构时先停止 worker/dispatcher，避免新源码在旧结构上执行：

```powershell
& .\.venv\Scripts\python.exe .\scripts\local.py stop
& .\.venv\Scripts\python.exe .\scripts\local.py setup
& .\.venv\Scripts\python.exe .\backend\manage.py migrate
& .\.venv\Scripts\python.exe .\scripts\local.py start
```

`setup` 会复用已有私有配置和数据库，不清空数据。仅更新 API 代码时可用 `scripts/local.py restart-api`。机器休眠/意外停止后重新执行 `start`；任务租约过期 90 秒后重排队，旧执行不能写回。

## 可以操作什么

1. Materials 已导入首轮 11 个唯一真实 PDF、237 页；相同字节的原始路径独立保留。
2. 点击文件名或 **View source**：查看固定版本、SHA-256、物理页、原始 PDF、文本抽取和答案关联。来源参数保存在 URL，刷新可恢复。
3. 点击类型按钮修改分类；保存有反馈，旧 revision 返回冲突。分类建议不是官方考试范围判断。
4. **Answer associations** 可登记这份答案对应的题卷和页/题范围，可解除关联。
5. 未完成/失败材料可点 **View task**；已完成材料的来源面板有 **Processing task**。任务详情保留真实阶段、时间、诊断和此前尝试。

`Parsed` 只表示本地解析结束。Docling 当前关闭 OCR 和公式增强；数学页可能漏抽公式、丢失根号或读序错误，所有页面保持 `needs_review`。应查看原页图。后续 AI 分析必须选择相关页图或经验证的公式解析路径，不能把当前文本作为完整数学内容。

上传范围暂为每文件 20 MiB、每课程 20 个唯一 PDF / 300 个唯一页 / 30 个路径 / 100 MiB。超限和损坏文件单独报错，不撤销其他成功上传。解析进程有 15 分钟保护限额；排队时间与解析时间在记录中可区分。这些不是正式产品永久上限。

## 安装与重建环境

本机已完成安装，无需重复安装。当前实测：Windows、Python 3.12.14、Node 24.19.0、pnpm 11.25.0、PostgreSQL 17.11、Django 5.2.18、Docling 2.140.0、Procrastinate 3.10.0。Python 完整锁定在 `backend/requirements.lock`，前端锁定在 `frontend/pnpm-lock.yaml`。

以下为在具备 Python 3.12、pip、Node 24、pnpm 的 Windows 电脑上重建的步骤；各组件在当前电脑验证过，**尚未在第二台干净电脑完整复现**：

```powershell
python -m venv .venv
python -m pip --python .venv/Scripts/python.exe install -r backend/requirements.lock
pnpm --dir frontend install --frozen-lockfile
& .\.venv\Scripts\python.exe scripts/fetch_postgres.py
& .\.venv\Scripts\python.exe scripts/local.py setup
& .\.venv\Scripts\python.exe backend/manage.py migrate
& .\.venv\Scripts\python.exe backend/manage.py seed_local_course
& .\.venv\Scripts\python.exe scripts/setup_models.py
& .\.venv\Scripts\python.exe -m playwright install chromium
& .\.venv\Scripts\python.exe backend/manage.py import_qm
& .\.venv\Scripts\python.exe scripts/local.py start
```

`fetch_postgres.py` 从官方 EDB 页面取得 PostgreSQL 17 Windows 发行版，保存下载地址与 SHA-256；将来下载的补丁版本可能变化。`setup_models.py` 下载 Docling 本地权重，不读取或上传课程材料。启动脚本设置 Hugging Face 离线模式；缺少权重时解析会报可诊断错误。

本机没有 Docker/WSL，采用项目内 PostgreSQL 二进制与 Python/Node 进程实现已确认架构；没有安装系统数据库服务，没有声称 Linux 容器方案已验证。本批未创建未验证的 Compose 启动入口。

`.env.local` 是可选覆盖项，可从 `.env.example` 复制。留空 `APP_DATABASE_URL` 会使用本地私有配置。原有 LiteLLM `.env` 和虚拟环境不参与本应用。`OPENAI_API_KEY` 只保存在本地，不应发送到聊天或提交 Git。网页课程分析仍未启用；填入 key 不会自动触发调用。

## 第一批 API 接入验证

Materials 顶部的 **View saved call records** 可找回真实调用任务。任务页显示模型、阶段、耗时、用量或未知状态、错误、结构化输出（仅成功时）及精确来源链接。最新成功任务为 `32726231-997a-4c00-825d-60fbafc282d0`，总耗时 102.16 秒、18,215 tokens；成功的是小范围接入及页图检查，不能替代六次真实出卷验收。

2026-10-22 用户明确授权五个指定页面及官方目的地，并在额度不足后充值；随后验证成功。范围见接入记录；不重复请求同范围许可。以下提交命令会产生真实 API 请求，只有需要新的验收时才执行。日常查看已有结果和启动网页无需再次调用模型：

```powershell
# 只发送合成的 x^2 求导题，最多一次请求，不含课程材料
& .\.venv\Scripts\python.exe backend/manage.py ai_validate --submit --smoke-only --key <new-run-key>
# 一次合成检查成功后，逐页检查已授权的五页；该任务最多六次请求
& .\.venv\Scripts\python.exe backend/manage.py ai_validate --submit --allow-course-data-upload --key <new-run-key>
# 本地导出指定任务的记录；不调用 API
& .\.venv\Scripts\python.exe backend/manage.py ai_validate --report <task-id>
# 对已有成功结果执行固定样本数学断言及页面检查；两者均不调用模型
& .\.venv\Scripts\python.exe scripts/check_batch1_live_result.py 32726231-997a-4c00-825d-60fbafc282d0
& .\.venv\Scripts\python.exe scripts/test_ai_validation_view.py 32726231-997a-4c00-825d-60fbafc282d0
```

相同 key 和输入返回同一任务，不重复调用。需要人工审阅后的新尝试可传 `--parent <failed-task-id>` 保留尝试链。没有自动付费重试；远端结果不明的调用不能在恢复时自动重发。取消不能承诺撤销服务端已收到的请求或费用，但旧执行不能发布结果。

命令行授权仅覆盖本次固定清单，`APP_MODEL_MODE=disabled` / `ALLOW_COURSE_DATA_UPLOAD=false` 可继续保留；它们不是这条显式验收命令的开启条件。普通应用调用边界仍返回 `not_executed`，不把命令行授权扩大为网页全部课程数据的长期外发权限。请求固定使用官方 Responses API、`store:false`、SDK 重试次数 0；`store:false` 不代表零保留。

## 检查命令

项目根目录 PowerShell：

```powershell
& .\.venv\Scripts\python.exe backend/manage.py check
& .\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests -q
& .\.venv\Scripts\python.exe backend/manage.py spectacular --file contracts/openapi.yaml --validate
pnpm --dir frontend api:types
pnpm --dir frontend typecheck
pnpm --dir frontend build
& .\.venv\Scripts\python.exe scripts/test_workspace.py
& .\.venv\Scripts\python.exe backend/manage.py audit_batch1
```

后端测试使用独立 PostgreSQL 测试库与临时文件目录。浏览器检查使用正在运行的真实本地应用，会重复上传一个已导入 PDF、提交一个无效 PDF，并将截图保存到 `var/screenshots/`；不会调用模型。审计核对 65 个原始路径的 hash，报告保存在 `var/batch1-audit.json`，不改写原件。

`scripts/test_live_recovery.py` 是本批特定失败样本的故障注入检查：取消重试任务、终止本项目 worker 并重启，保留尝试链。它需要特定失败前置状态，不是日常启动命令；结果记录在 `var/recovery-check.json`。

当前浏览器检查由 Python Playwright 执行；尚未建立 Vitest 单元测试集或 Node Playwright 测试集，不将包中的未来测试脚本作为已运行检查。
