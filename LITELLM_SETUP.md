# LiteLLM 本地代理

LiteLLM 1.105.1（含 Proxy 和 Python SDK）安装在本项目的 `.venv-litellm` 独立环境中，使用现有的 Python 3.12.14。

已在本机 `.env` 中生成代理访问密钥 `LITELLM_MASTER_KEY`，LiteLLM 启动时会自动读取。客户端连接本地代理时使用这把密钥；服务商的 API Key 另行配置。

在当前项目目录打开 PowerShell，无需激活虚拟环境：

```powershell
.\litellm.cmd --version
.\litellm.cmd --help
```

## 启动模型代理

将下面的 `YOUR_MODEL_NAME` 替换为你有权限使用的模型名称，并在本机终端设置 API Key：

```powershell
$env:OPENAI_API_KEY = '你的 API Key'
.\litellm.cmd --model openai/YOUR_MODEL_NAME --host 127.0.0.1 --port 4000
```

如果使用兼容 OpenAI 的服务商，在命令末尾添加其 API 地址：

```powershell
.\litellm.cmd --model openai/YOUR_MODEL_NAME --api_base https://your-provider.example/v1 --host 127.0.0.1 --port 4000
```

启动后，本地 API 地址为 `http://127.0.0.1:4000/v1`。客户端的 API Key 填写 `.env` 中的 `LITELLM_MASTER_KEY` 值。终端中按 `Ctrl+C` 停止。

也可以编辑 `litellm-config.example.yaml` 中的模型及 API 地址后，通过配置文件启动；客户端使用该文件中的模型别名 `default`：

```powershell
.\litellm.cmd --config .\litellm-config.example.yaml --host 127.0.0.1 --port 4000
```

## 使用 Python SDK

用 `.venv-litellm\Scripts\python.exe` 运行你的 Python 程序即可导入 `litellm`。

已通过依赖检查、CLI 检查、本地健康检查、带访问密钥的模型列表及模拟聊天接口验证。测试服务已停止。

服务商 API Key 尚未配置；安装验证使用模拟回复，没有调用付费模型。

环境复用本机已有的 Python 运行时：`C:\Users\Yijia\.cache\codex-runtimes\codex-primary-runtime\dependencies\python`。若该运行时被移除，需用新的 Python 重建虚拟环境，并安装 `requirements-litellm.txt`。

官方文档：https://docs.litellm.ai/docs/proxy/quick_start
