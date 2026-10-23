@AGENTS.md

# Claude Code 补充说明

项目规则和交接流程以 AGENTS.md 为准，本文件只记录 Claude Code 需要额外注意的事项。

- 本机 `.venv` 基于 Codex 自带的 Python（`C:\Users\Yijia\.cache\codex-runtimes\...`）。不要自行重建虚拟环境或安装依赖；需要时先问用户。
- 停止或重启本项目服务前，先确认 Codex 没有在运行任务。
- Claude Code 的会话记录和自动记忆 Codex 读不到；需要交接的信息按 AGENTS.md 第 6 节写入仓库。
