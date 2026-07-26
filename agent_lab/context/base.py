from dataclasses import field

from pydantic import BaseModel, Field


class ContextWindow(BaseModel):
    system_messages: list = field(default_factory=list)
    context_messages: list = field(default_factory=list)
    tools: list = field(default_factory=list)

    def to_llm_messages(self) -> list:
        """合并为 LLM API 所需的消息列表。"""
        return self.system_messages + self.context_messages
