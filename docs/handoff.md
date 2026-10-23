# 交接：视觉证据路径第 5 步

更新：2026-10-24，Claude Code。

**目标**：完成[视觉证据路径计划](superpowers/plans/2026-10-24-visual-evidence-path.md)第 5 步：真实转写 18 页页图，在带转写的输入上重新运行课程分析，记录结果。完成标准见计划 §5。

**已完成**：第 1–4 步（提交 `ad36b71`、`0f5ce41`、`d0bf5fb`、`a3a496e`），验证情况见 [visual-evidence-validation.md](visual-evidence-validation.md)。开发库已迁移到 `materials.0005`。

**下一步**（每一步都要先取得用户在对话中的明确同意）：

1. 用户授权 18 页页图外发后，执行以下命令。它会写入授权，并立即排队真实转写；如果当前 scope hash 和下面的不一致，先去掉 `--authorize --scope-hash ...` 重新预览：

   ```powershell
   & .\.venv\Scripts\python.exe backend/manage.py visual_transcription --select 51c17aa6-4537-49fb-a30c-2e6cb7116f34:3,5 --select a15a6f71-a805-46de-a666-ee2532a2ab54:2,6 --select b3444a83-2f5f-49c9-b929-3838c367d4f4:28,31,32 --select fbfa843a-bd45-4745-b81a-623c767c4866:2-6,8,9,14,15 --select cd833878-a896-49e3-9bca-2f723b251315:3,4 --authorize --scope-hash fac78fac5a832a006919cd3d677c343daa4d971b37143a3386acee7c3b6de893
   ```

   版本 ID 分别对应 M05、M06、M34、M35、M46。完成后用 `--report <task-id>` 导出耗时、tokens 和失败情况。
2. 对照原页图抽查几页转写，记为“Claude 抽查”。
3. 在 Profile 的 **Analyse again** 中查看预检。如果准入估算超过 60,000，提交时会被拒绝，不会发送任何数据，这时需要用户先决定预算处理方式，见验证记录“待用户决定”第 2 条。之后再取得新的分析授权并提交。
4. 记录阻塞事项的变化，更新 README 和验证记录；全部完成后删除本文件。

**未验证事项**：
- 真实转写的质量、耗时和费用；
- 带转写输入时分析输入的实际大小；
- Python Playwright 回归脚本：本机当前用户没有 Chromium，安装前需要用户同意。

**服务**：本项目的 PostgreSQL、API、worker、dispatcher 和前端都在运行（`scripts/local.py start`）。没有排队或执行中的任务。
