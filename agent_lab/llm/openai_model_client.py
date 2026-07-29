"""HelloAgents统一LLM接口 - 基于OpenAI原生API"""

import os
from typing import Optional, List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI

from agent_lab.core.exceptions import SocketAgentsException
from agent_lab.core.logger import get_logger
from agent_lab.llm.schema.message import AssistantMessage, BaseMessage, ToolMessage
from agent_lab.llm.schema.tool_call import ToolCall

logger = get_logger("OpenAIClient")


class OpenAIModelClient():

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None, timeout: int = None):
        self.model = model or os.getenv("LLM_MODEL_ID")
        api_key = api_key or os.getenv("LLM_API_KEY")
        base_url = base_url or os.getenv("LLM_BASE_URL")
        timeout = timeout or int(os.getenv("LLM_TIMEOUT", 60))

        if not all([self.model, api_key, base_url]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在.env文件中定义。")

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    async def _build_request_params(self, messages: List[BaseMessage],
                                    tools: Optional[List[Dict[str, str]]] = None) -> Dict:

        message_list = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content}
            if isinstance(msg, AssistantMessage) and msg.tool_calls:
                tool_calls_list = []
                for tool_call in msg.tool_calls:
                    tool_calls_list.append({
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.name,
                            "arguments": tool_call.arguments
                        }
                    })
                msg_dict["tool_calls"] = tool_calls_list

                if msg.reasoning_content:
                    msg_dict["reasoning_content"] = msg.reasoning_content

            if isinstance(msg, ToolMessage):
                msg_dict["tool_call_id"] = msg.tool_call_id

            message_list.append(msg_dict)

        params = {
            "model": self.model,
            "messages": message_list,
            "stream": True,
        }

        if tools:
            params["tools"] = tools
            params["tool_choice"] = 'auto'

        return params

    async def invoke(
            self, messages: List[BaseMessage], tools: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        logger.info(f"正在调用 {self.model} 模型...")

        params = await self._build_request_params(messages, tools)
        try:
            full_content = ""
            tool_call_dict: dict = {}
            response_stream = await self.client.chat.completions.create(**params)

            async for chunk in response_stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
                if reasoning:
                    yield {"type": "reasoning", "content": reasoning}

                if delta.content:
                    full_content += delta.content
                    yield {"type": "content", "content": delta.content}

                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        index = tool_call_delta.index

                        if index not in tool_call_dict:
                            tool_call_dict[index] = ToolCall(id=tool_call_delta.id, type="function", name="",
                                                             arguments="")

                        target_tool = tool_call_dict[index]

                        if tool_call_delta.function.name:
                            target_tool.name += tool_call_delta.function.name

                        if tool_call_delta.function.arguments:
                            target_tool.arguments += tool_call_delta.function.arguments

            assistant_message = AssistantMessage()

            if full_content:
                assistant_message.content = full_content

            if tool_call_dict:
                assistant_message.tool_calls = [tool_call_dict[i] for i in sorted(tool_call_dict.keys())]

            if not full_content and not tool_call_dict:
                raise SocketAgentsException("LLM 流异常结束，未生成任何有效内容或工具调用")

            yield {"type": "final_result", "message": assistant_message}

        except Exception as e:
            logger.error(f"调用LLM API时发生错误: {e}")
            raise SocketAgentsException(f"LLM调用失败: {str(e)}")
