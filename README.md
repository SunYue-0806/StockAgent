# ZiMoMo

> 基于 ReAct 模式的 LLM Agent 框架，支持流式推理、工具调用、上下文管理与多层记忆。

## ✨ 特性

- **🧠 ReAct 循环** — 思考 → 决策 → 行动 → 观察，最多 500 步自愈推理
- **⚡ 流式输出** — 思维链（reasoning）与正文（content）双流实时推送
- **🔧 工具系统** — 装饰器一键注册，全局工具池自动生成 JSON Schema
- **📐 滑动窗口** — 按 Turn 轮次打包 + Token 预算裁剪，长对话不爆上下文
- **💾 会话持久化** — 基于 JSONL 的增量追加存储，支持会话恢复与摘要压缩
- **📡 WebSocket 事件协议** — 标准化实时事件流，开箱即用的前后端通信协议
- **🧩 多层记忆架构** — 工作记忆 / 感知记忆 / 语义记忆 / 情景记忆（开发中）

## 🏗️ 项目结构

```
agent_lab/
├── agents/                  # 智能体实现
│   └── react_agent.py       # ReAct Agent 核心
├── llm/                     # LLM 客户端
│   ├── openai_model_client.py   # OpenAI 兼容流式客户端
│   └── schema/              # 消息 & ToolCall 模型
├── context/                 # 上下文管理
│   ├── context_manager.py   # 滑动窗口 + Token 预算
│   ├── base.py              # ContextWindow 模型
│   └── message_buffer.py    # 消息缓冲区
├── tools/                   # 工具系统
│   ├── tool_manager.py      # @tool 装饰器 & 全局注册/执行
│   ├── weather_tool.py      # 天气查询工具
│   ├── builtin/
│   │   ├── file_tool.py     # 文件操作（read/write/edit/list/grep/glob）
│   │   ├── memory_tool.py   # 记忆工具（开发中）
│   │   └── rag_tool.py      # RAG 检索工具（开发中）
│   └── schema/              # 工具调用数据模型
├── memory/                  # 记忆系统（开发中）
│   ├── type/                # 四层记忆类型
│   │   ├── working_memory.py
│   │   ├── perceptual_memory.py
│   │   ├── semantic_memory.py
│   │   └── episodic_memory.py
│   ├── storage/             # 存储后端
│   │   ├── qdrant_store.py  # 向量检索
│   │   ├── neo4j_store.py   # 知识图谱
│   │   └── document_store.py
│   ├── embedding.py         # 向量嵌入
│   └── manager.py           # 记忆管理器
├── session/                 # 会话持久化
│   └── store.py             # JSONL 增量存储
├── websocket/               # WebSocket 事件协议
│   └── events.py            # 事件类型枚举 & 工厂函数
├── prompt/                  # 提示词模板
│   └── prompt_utils.py
├── core/                    # 核心基础设施
│   ├── token_counter.py     # Token 计数器（tiktoken）
│   ├── llm_config.py        # LLM 配置模型
│   ├── context_engine_config.py
│   ├── exceptions.py        # 异常体系
│   └── logger.py            # 日志配置
└── __init__.py              # 统一导出
```

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

### 运行 Agent

```python
import asyncio
from agent_lab import ReActAgent, OpenAIModelClient

async def main():
    client = OpenAIModelClient()
    agent = ReActAgent(client=client)

    async for event in agent.run("帮我查一下北京今天的天气"):
        if event["type"] == "reasoning":
            print(f"💭 思考: {event['content']}")
        elif event["type"] == "content":
            print(f"📝 回复: {event['content']}", end="")
        elif event["type"] == "status_update":
            print(f"⚡ 状态: {event['content']}")
        elif event["type"] == "agent_finish":
            print("\n✅ 执行完毕")

asyncio.run(main())
```

### 自定义工具

```python
from agent_lab.tools.tool_manager import tool

@tool
def search_database(query: str, limit: int = 10) -> str:
    """搜索数据库中的相关记录。"""
    # 你的业务逻辑
    return f"找到 {limit} 条关于 '{query}' 的记录"
```

装饰器会自动：
- 提取函数签名和类型注解，生成 JSON Schema
- 注册到全局工具池，供 Agent 自动发现和调用

## 🔧 工具系统

### 内置工具

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文本文件（支持行范围、行号标注） |
| `write_file` | 原子写入文件（自动创建目录、临时文件替换） |
| `edit_file` | 安全编辑文件（mtime 乐观锁防并发覆盖） |
| `list_files` | 列出目录内容 |
| `grep` | 递归搜索文本模式 |
| `glob_files` | 通配符匹配搜索文件 |
| `get_current_weather` | 查询实时天气 |

### 安全机制

- **原子写入** — 先写临时文件再 `os.replace`，写入失败不破坏原文件
- **乐观锁** — 通过 `expected_mtime` 校验，防止并发修改覆盖
- **大文件保护** — 超过 1 GiB 的文件拒绝操作，超 5 MiB 的内容拒绝写入
- **Token 限制** — 读取内容超过 25K tokens 自动截断

## 📐 上下文管理

ContextManager 采用**滑动窗口 + Token 预算**策略：

1. **置顶** — System Message + 首条 User Message 始终保留
2. **按轮次打包** — 以 UserMessage 为边界，将历史消息按 Turn 分组
3. **Token 预算** — `可用预算 = 最大上下文 - 置顶消息 - 工具Schema - 预留回复`
4. **从新到旧填充** — 保留最新的完整 Turn，直到预算耗尽

## 💾 会话持久化

```python
from agent_lab import SessionStore

store = SessionStore()

# 创建会话
session_id = store.create()

# 增量追加（O(K)，高频调用）
store.append(session_id, new_messages)

# 加载历史
messages = store.load(session_id)

# 摘要压缩（开发中）
store.compact(session_id, summarized_messages)
```

## 📡 WebSocket 事件协议

```python
from agent_lab.websocket import create_ws_event, WebSocketEventType

# 创建事件
event = create_ws_event(WebSocketEventType.TEXT_CONTENT, {"text": "你好"})
# → {"event": "text_content", "payload": {"text": "你好"}}

# 支持的事件类型
# AGENT_STATUS / AGENT_SUCCESS / AGENT_ERROR
# TEXT_REASONING / TEXT_CONTENT
# TOOL_START / TOOL_BATCH_EXECUTE / TOOL_EXECUTING / TOOL_RESPONSE
```

## 🗺️ 开发路线

- [x] LLM 流式客户端（OpenAI 兼容）
- [x] ReAct Agent 核心循环
- [x] 工具注册与执行框架
- [x] 文件操作工具集
- [x] 滑动窗口上下文管理
- [x] Token 计数器
- [x] 会话 JSONL 持久化
- [x] WebSocket 事件协议定义
- [ ] 情景记忆 + Qdrant 向量检索
- [ ] 记忆工具（memory_tool / rag_tool）
- [ ] 会话摘要压缩（compact）
- [ ] WebSocket 服务端实现
- [ ] 语义记忆 + Neo4j 知识图谱
- [ ] 感知记忆 & 工作记忆

## 📄 许可证

MIT License
