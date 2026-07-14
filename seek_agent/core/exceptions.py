"""异常体系"""


class SeekAgentsException(Exception):
    """HelloAgents基础异常类"""

    pass


class LLMException(SeekAgentsException):
    """LLM相关异常"""

    pass


class AgentException(SeekAgentsException):
    """Agent相关异常"""

    pass


class ConfigException(SeekAgentsException):
    """配置相关异常"""

    pass


class ToolException(SeekAgentsException):
    """工具相关异常"""

    pass
