# Trae Bridge 开发任务

## 目标

参考 antigravity-bridge 的实现方式，创建一个将 Trae AI IDE 模型转换为 RESTful API 的 bridge。

## 关键参考

- antigravity-bridge 使用 CDP (Chrome DevTools Protocol) 连接到 Electron 应用
- 通过 WebSocket 与 Antigravity 的 chat UI 通信
- 使用 DOM 操作注入消息并轮询响应

## Trae 技术调研

1. Trae 是 Electron 应用，支持 `--remote-debugging-port` 参数
2. 需要研究 Trae 的 chat UI 结构：
   - 消息输入框的 DOM 结构
   - 发送按钮的选择器
   - AI 响应的 DOM 结构和完成标记
   - 模型切换的 UI 元素

3. CDP 端口: 9230

## 需要实现的 API 端点

```
POST   /chat           - 同步聊天 (默认 180s timeout)
POST   /async          - 异步聊天，返回 task_id
GET    /task/{id}      - 轮询异步结果
POST   /new            - 新建对话（清除上下文）
GET    /health         - 健康检查
GET    /models         - 列出可用模型
POST   /model          - 切换模型
GET    /history        - 获取当前对话内容
```

## 项目结构

```
trae-bridge/
├── README.md
├── LICENSE
├── SKILL.md              # OpenClaw Skill 集成文档
├── requirements.txt      # Python 依赖
├── scripts/
│   ├── start_trae.sh    # 启动 Trae 带 CDP
│   └── bridge.py        # REST API 服务器
└── src/
    ├── __init__.py
    ├── cdp_client.py    # CDP 连接和通信
    ├── dom_helper.py    # DOM 操作工具
    └── api_server.py    # FastAPI/Flask REST 服务器
```

## 开发步骤

1. **调研阶段**
   - 启动 Trae 并连接 CDP
   - 使用 Chrome DevTools 检查 Trae 的 DOM 结构
   - 找到 chat 输入框、发送按钮、消息列表的选择器

2. **核心实现**
   - 实现 CDP WebSocket 连接
   - 实现消息注入（类似 antigravity-bridge 使用 execCommand）
   - 实现响应轮询
   - 处理 Trae 的异步响应机制

3. **REST API**
   - 使用 FastAPI 创建 API 服务器
   - 实现所有端点
   - 添加错误处理和超时控制

4. **测试与优化**
   - 测试各种模型
   - 处理边界情况（网络错误、超时等）
   - 优化性能和稳定性

5. **OpenClaw Skill 集成**
   - 编写 SKILL.md
   - 添加配置示例

## 技术细节

### CDP 连接

```python
import asyncio
import websockets
import json

async def connect_cdp():
    # 获取 WebSocket debugger URL
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:9230/json/list') as resp:
            pages = await resp.json()
            ws_url = pages[0]['webSocketDebuggerUrl']
    
    # 连接 WebSocket
    ws = await websockets.connect(ws_url)
    return ws
```

### 消息注入

参考 antigravity-bridge，使用 CDP 的 Runtime.evaluate 执行 JS：

```javascript
// 聚焦输入框并插入文本
document.querySelector('[contenteditable="true"]').focus();
document.execCommand('insertText', false, '你的消息');

// 点击发送按钮
document.querySelector('发送按钮选择器').click();
```

### 响应轮询

监听 DOM 变化，检测 AI 响应完成标记：

```javascript
// 获取最新消息
const messages = document.querySelectorAll('消息选择器');
const lastMessage = messages[messages.length - 1];

// 检查是否完成（根据 Trae 的具体实现）
const isComplete = lastMessage.querySelector('完成标记选择器') !== null;
```

## 依赖

```
websockets>=11.0
aiohttp>=3.8
fastapi>=0.100
uvicorn>=0.23
```

## 注意事项

1. Trae 可能使用不同的消息传输机制（不一定是简单的 DOM 操作）
2. 需要处理 Trae 的登录状态和配额限制
3. 考虑添加请求队列避免并发问题
4. 实现适当的错误重试机制
