from typing import Optional

from pydantic import BaseModel


class ToolCall(BaseModel):
    id: Optional[str]
    type: str
    name: str
    arguments: str
    index: Optional[int] = None
