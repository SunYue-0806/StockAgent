"""agent_lab.tools.builtin — 内置工具集

导入此包即自动注册所有内置工具到全局工具池。
"""

# 导入各工具模块，触发 @tool 装饰器注册
from agent_lab.tools.builtin import file_tool  # noqa: F401
from agent_lab.tools.builtin import memory_tool  # noqa: F401
