# AI Past Paper Generator

当前实现：第一轮 **批次 1–2（Task 1–4）材料工作区、课程分析、编辑与确认**。可上传数字 PDF、复用解析、查看固定版本原页、跟踪任务，并从获准的材料片段形成课程草稿；支持直接编辑、澄清回答、保存冲突处理和不可变确认版本。组卷、答案生成和两个输出 PDF 属于后续批次，尚未实现。

2026-10-22 完成第一批 5 页真实模型核对；2026-10-23 在用户新授权的 36 页抽取文字和 5 页已有核对结果上运行课程分析，得到真实的 `needs_info` 草稿，未冒充课程已确认。需求入口见 [AGENTS.md](AGENTS.md)，记录见 [批次一](docs/batch-1-live-validation.md) 和 [批次二](docs/batch-2-validation.md)。历史原型和原材料保持原位。

## 当前电脑启动（已实际运行）

在项目根目录打开 PowerShell：

```powershell
& .\.venv\Scripts\python.exe .\scripts\local.py start
```

访问 **http://127.0.0.1:5173**，点击 **Open local workspace**。程序检查 API 就绪后才打印地址。重复执行会复用已确认身份的本项目进程，补起已停止的服务。

- `5173`：Vite 前端；`8000`：Django API；本机当前 `54330`：项目 PostgreSQL（新环境默认 `54329`，实际以 `var/local.json` 为准）。
- worker、outbox dispatcher、API 和前端均在后台运行；日志在 `var/logs/`。
- 本机活动数据库在 `var/postgres-20261023/`；原 `var/postgres/` 是本次恢复前的保留副本，不是活动库。文件/解析/页图在 `var/data/`；离线解析权重在 `var/models/`。恢复原因和核对见批次二记录；不要把旧副本当作新数据备份。
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
6. **Course profile** 查看真实 Topic 2 草稿：Knowledge、Scope & methods、Exam reference。来源按钮在同页打开原材料版本和物理页，刷新可恢复。
7. 修改字段后 800ms 串行自动保存，也可点 **Save changes**。失败保留输入；冲突必须比较后选择服务器版本或保留本地修改。浏览器当前标签的未提交编辑用 sessionStorage 恢复；服务器已保存草稿可跨会话找回。
8. 必要问题的 **Save answer** 会记录 UserStatement，需解释的新回答由新分析任务处理，不自动付费调用。读取缺口显示现有页图入口；不是要求再次上传已存在的材料。
9. **Review & confirm** 只确认服务器已保存且无目标阻塞问题的 revision。确认后进入读取该冻结版本的 Generate 入口；结构规划仍待批次三实现。真实 QM 目前因解析与来源冲突未确认；浏览器测试确认只发生在显式标记的 `B2-TEST` 课程。

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

`.env.local` 是可选覆盖项，可从 `.env.example` 复制。留空 `APP_DATABASE_URL` 会使用本地私有配置。原有 LiteLLM `.env` 和虚拟环境不参与本应用。`OPENAI_API_KEY` 只保存在本地，不应发送到聊天或提交 Git。填入 key 不自动调用；网页分析必须显式提交，并对展示的输入范围授权。

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

命令行授权仅覆盖固定清单，`APP_MODEL_MODE=disabled` / `ALLOW_COURSE_DATA_UPLOAD=false` 可继续保留。批次二使用单独的、绑定 course 和 context hash 的 AnalysisGrant；它只允许显式提交这份分析输入，不授权整门课长期外发。请求固定使用官方 Responses API、`store:false`、SDK 重试次数 0；`store:false` 不代表零保留。

## 第二批课程分析

入口：`/courses/68caa35d-6e08-42d7-84bd-70a23e369b1f/profile`。最新真实任务：`cd0d0c32-50c2-4f42-a2b6-3e9d148dd702`。8 个知识组均有来源关联；5 组为 partial，3 组 supported。源页公式缺失和局部/全局极值定义冲突保留为两组待处理事项。当前缺口不能仅凭确认或文本断言清除。

查看已有结果不会调用模型。**Analyse again** 会先展示精确发送范围；提交会产生新的真实 API 调用。材料/声明/模型/提示词变化导致 hash 改变，需要明确授权新输入。同一提交 key 复用原任务，旧任务快照不变。原任务 `needs_info` 后的新分析有 parent 关联；取消或 lease 失效的执行不能发布草稿。

以下命令只读本地数据，不调用模型：

```powershell
& .\.venv\Scripts\python.exe backend/manage.py course_analysis
& .\.venv\Scripts\python.exe backend/manage.py course_analysis --report cd0d0c32-50c2-4f42-a2b6-3e9d148dd702
```

已授权的第二批 scope 是 36 页文字、5 页已有识别结果和已提供的范围声明，**没有包含新页图**。本轮尚未把页图补读自动接入课程分析。补读公式需扩大具体页图授权并实现该恢复分支；当前如实保留 `needs_info`，不静默删去不支持的知识组。

## 检查命令

项目根目录 PowerShell：

```powershell
& .\.venv\Scripts\python.exe backend/manage.py check
& .\.venv\Scripts\python.exe -m pytest -c backend/pytest.ini backend/tests -q
& .\.venv\Scripts\python.exe backend/manage.py spectacular --file contracts/openapi.yaml --validate
pnpm --dir frontend api:types
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend test --run
& .\.venv\Scripts\python.exe scripts/test_workspace.py
& .\.venv\Scripts\python.exe backend/manage.py audit_batch1
```

后端测试使用独立 PostgreSQL 测试库与临时文件目录。浏览器检查使用正在运行的真实本地应用，会重复上传一个已导入 PDF、提交一个无效 PDF，并将截图保存到 `var/screenshots/`；不会调用模型。审计核对 65 个原始路径的 hash，报告保存在 `var/batch1-audit.json`，不改写原件。

`scripts/test_live_recovery.py` 是本批特定失败样本的故障注入检查：取消重试任务、终止本项目 worker 并重启，保留尝试链。它需要特定失败前置状态，不是日常启动命令；结果记录在 `var/recovery-check.json`。

课程页面浏览器测试使用独立的 fixture 课程（会新建 `B2-TEST`，不改真实 QM 草稿），其中一个本地保存请求被故意中断以模拟网络故障：

```powershell
& .\.venv\Scripts\python.exe scripts/prepare_profile_browser_fixture.py
& .\.venv\Scripts\python.exe scripts/test_course_profile.py
```

Vitest 覆盖串行保存、迟到响应、未知保存结果的同 key 重试、冲突和标签刷新恢复。Python Playwright 覆盖实际浏览器；仍未建立 Node Playwright 测试集，不把 `test:e2e` 脚本视为已验收入口。
