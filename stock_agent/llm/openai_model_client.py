"""HelloAgents统一LLM接口 - 基于OpenAI原生API"""

import os
import sys
from typing import Literal, Optional, Iterator, List, Dict, Any, AsyncGenerator
from openai import AsyncOpenAI

from stock_agent.core.exceptions import SocketAgentsException


class OpenAIModelClient:

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None, timeout: int = None):
        self.model = model or os.getenv("LLM_MODEL_ID")
        api_key = api_key or os.getenv("LLM_API_KEY")
        base_url = base_url or os.getenv("LLM_BASE_URL")
        timeout = timeout or int(os.getenv("LLM_TIMEOUT", 60))

        if not all([self.model, api_key, base_url]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在.env文件中定义。")

        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    async def _build_request_params(self, messages: List[Dict[str, str]],
                                    tools: Optional[List[Dict[str, str]]] = None) -> Dict:

        params = {
            "model": self.model,
            "messages": messages,
            "stream": True,
        }

        if tools:
            params["tools"] = tools
            params["tool_choice"] = 'auto'

        return params

    async def invoke(
            self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, str]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        print(f"🧠 正在调用 {self.model} 模型...")

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
                        tool_name = self._parse_tool_call_stream(tool_call_delta, tool_call_dict)

                        if tool_name:
                            yield {"type": "tool_decide", "name": tool_name}

            result_message = {"role": "assistant"}
            if full_content:
                result_message["content"] = full_content
            if tool_call_dict:
                result_message["tool_calls"] = [tool_call_dict[i] for i in sorted(tool_call_dict.keys())]

            if not full_content and not tool_call_dict:
                raise SocketAgentsException("LLM 流异常结束，未生成任何有效内容或工具调用")

            yield {"type": "final_result", "message": result_message}


        except Exception as e:
            print(f"❌ 调用LLM API时发生错误: {e}")
            raise SocketAgentsException(f"LLM调用失败: {str(e)}")

    @staticmethod
    def _parse_tool_call_stream(tool_call_delta: Any, tool_call_dict: Dict[int, Dict[str, Any]]):
        index = tool_call_delta.index

        if index not in tool_call_dict:
            tool_call_dict[index] = {
                "id": tool_call_delta.id or "",
                "type": "function",
                "function": {"name": "", "arguments": ""}
            }

        target_tool = tool_call_dict[index]

        tool_name = None

        if tool_call_delta.function.name:
            target_tool["function"]["name"] += tool_call_delta.function.name
            tool_name = target_tool["function"]["name"]

        if tool_call_delta.function.arguments:
            target_tool["function"]["arguments"] += tool_call_delta.function.arguments

        return tool_name

    @staticmethod
    def _format_messages(messages: List[Dict[str, Any]]) -> str:
        """将消息列表格式化为可读字符串，供调试/日志使用。"""
        lines = []
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = str(msg.get("content", ""))
            if role == "system":
                lines.append(f"[{i}] system: {content}")
            elif role == "user":
                lines.append(f"[{i}] user: {content}")
            elif role == "assistant":
                suffix = ""
                if "tool_calls" in msg:
                    suffix = f" | tool_calls: {len(msg['tool_calls'])}个"
                lines.append(f"[{i}] assistant: {content[:200]}{suffix}")
            elif role == "tool":
                lines.append(f"[{i}] tool ({msg.get('name', '?')}): {content[:200]}")
        return "\n".join(lines)
