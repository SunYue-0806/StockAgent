"""agent_lab.tools — 工具注册与执行"""

from agent_lab.tools.tool_manager import execute_tool, get_all_tools_schema, tool
from agent_lab.llm.schema.tool_call import ToolCall

# 导入内置工具模块，触发 @tool 装饰器注册
from agent_lab.tools import weather_tool  # noqa: F401
from agent_lab.tools.builtin import file_tool  # noqa: F401

__all__ = [
    "tool",
    "execute_tool",
    "get_all_tools_schema",
    "ToolCall",
]
