from abc import abstractmethod, ABC
from typing import Any, Dict, Type
from pydantic import BaseModel


class Tool(ABC):
    name: str = ""
    description: str = ""
    args_schema: Type[BaseModel] | Dict[str, Any] = None

    def get_tool_info(self) -> Dict[str, Any]:
        """直接生成大模型需要的 Schema 说明书"""
        params = {}
        if self.args_schema and issubclass(self.args_schema, BaseModel):
            params = self.args_schema.model_json_schema()

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": params
            }
        }

    @abstractmethod
    async def invoke(self, inputs: Any, **kwargs) -> Any:
        pass
