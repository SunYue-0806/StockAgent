"""异常体系"""


class SocketAgentsException(Exception):
    """HelloAgents基础异常类"""

    pass


class LLMException(SocketAgentsException):
    """LLM相关异常"""

    pass


class AgentException(SocketAgentsException):
    """Agent相关异常"""

    pass


class ConfigException(SocketAgentsException):
    """配置相关异常"""

    pass


class ToolException(SocketAgentsException):
    """工具相关异常"""

    pass
