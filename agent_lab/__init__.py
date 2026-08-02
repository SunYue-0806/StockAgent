"""SeekAgent — LLM Agent 框架

基于 ReAct 模式的智能体，支持流式推理、工具调用与自愈循环。

快速开始::

    from agent_lab import ReActAgent, OpenAIModelClient

    client = OpenAIModelClient()
    agent = ReActAgent(client=client)

    async for event in agent.run("你好"):
        print(event)
"""

# ── 智能体 ──
from agent_lab.agents.react_agent import ReActAgent

# ── LLM 客户端 ──
from agent_lab.llm.openai_model_client import OpenAIModelClient

# ── 消息模型 ──
from agent_lab.llm.schema.message import (
    AssistantMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
    UsageMetadata,
    UserMessage,
)

# ── 工具系统 ──
from agent_lab.tools.tool_manager import execute_tool, get_all_tools_schema, tool
from agent_lab.llm.schema.tool_call import ToolCall

# ── 上下文管理 ──
from agent_lab.context.base import ContextWindow
from agent_lab.context.message_buffer import MessageBuffer

# ── 提示词 ──
from agent_lab.prompt.prompt_utils import load_system_prompt

# ── WebSocket 事件协议 ──
from agent_lab.websocket.events import WebSocketEventType, create_ws_event

# ── 基础设施 ──
from agent_lab.core.exceptions import (
    AgentException,
    ConfigException,
    LLMException,
    SocketAgentsException,
    ToolException,
)
from agent_lab.core.llm_config import LLMConfig
from agent_lab.core.logger import configure, get_logger, logger

__all__ = [
    # Agent
    "ReActAgent",
    # LLM
    "OpenAIModelClient",
    # 消息
    "BaseMessage",
    "UserMessage",
    "SystemMessage",
    "AssistantMessage",
    "ToolMessage",
    "UsageMetadata",
    # 工具
    "tool",
    "execute_tool",
    "get_all_tools_schema",
    "ToolCall",
    # 上下文
    "ContextWindow",
    "MessageBuffer",
    # 提示词
    "load_system_prompt",
    # WebSocket
    "WebSocketEventType",
    "create_ws_event",
    # 异常
    "SocketAgentsException",
    "LLMException",
    "AgentException",
    "ConfigException",
    "ToolException",
    # 配置
    "LLMConfig",
    # 日志
    "logger",
    "get_logger",
    "configure",
]
