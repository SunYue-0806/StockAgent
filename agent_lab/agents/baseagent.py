"""Agent基类"""
from abc import ABC, abstractmethod
from typing import Optional

from agent_lab.llm.openai_model_client import OpenAIModelClient
from agent_lab.core.message import Message


class BaseAgent(ABC):
    def __init__(
            self,
            llm_client: OpenAIModelClient,
            system_prompt: Optional[str] = None,
    ):
        self.llm = llm_client
        self.system_prompt = system_prompt
        self.messages: list[Message] = []

    @abstractmethod
    def run(self, input_text: str, **kwargs) -> str:
        pass

    def add_message(self, message: Message):
        self.messages.append(message)

    def clear_history(self):
        self.messages.clear()

    def get_history(self) -> list[Message]:
        return self.messages.copy()
