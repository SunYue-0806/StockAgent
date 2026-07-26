import ast
import json
from typing import AsyncGenerator, Dict, Any

from agent_lab.core.logger import get_logger
from agent_lab.llm.openai_model_client import OpenAIModelClient
from agent_lab.prompt.prompt_utils import load_system_prompt
from agent_lab.tools.tool_manager import get_all_tools_schema, execute_tool

logger = get_logger("ReActAgent")


class ReActAgent:
    def __init__(self, client: OpenAIModelClient):
        self.client = client
        self.messages = []
        self.max_steps = 5
        self.system_prompt = load_system_prompt()
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]

    @staticmethod
    def _is_tool_failure(tool_result: str) -> bool:
        """判断工具执行结果是否为失败。

        优先解析为 Python dict 检查 success 字段，
        解析失败则降级为错误关键词匹配。
        """
        try:
            result = ast.literal_eval(tool_result)
            if isinstance(result, dict):
                return result.get("success") is False
        except (ValueError, SyntaxError):
            pass

        # 兜底：字符串关键词检测
        s = tool_result.lower()
        return any(kw in s for kw in [
            "error", "异常", "失败", "traceback", "nameerror",
            "not found", "permission denied",
        ])

    async def _force_text_response(
        self, step_messages: list, hint: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """注入提示消息，不带工具调用模型，强制其产出文字回答。"""
        logger.warning(hint)
        step_messages.append({"role": "user", "content": hint})
        yield {"type": "status_update", "content": f"⚠️ {hint}"}

        async for event in self.client.invoke(step_messages, tools=None):
            if event["type"] == "reasoning":
                yield {"type": "reasoning", "content": event["content"]}
            elif event["type"] == "content":
                yield {"type": "content", "content": event["content"]}
            elif event["type"] == "final_result":
                yield {
                    "type": "agent_finish",
                    "content": event["message"].get("content", ""),
                    "final_message": event["message"],
                }

    async def run(self, user_message: str) -> AsyncGenerator[Dict[str, Any], None]:
        self.messages.append({"role": "user", "content": user_message})
        step_messages = list(self.messages)
        current_step = 0
        consecutive_failures = 0

        while current_step < self.max_steps:
            current_step += 1
            logger.info(f"--- 第 {current_step} 步 ---")

            tools_schema = get_all_tools_schema()

            assistant_message = None

            async for event in self.client.invoke(step_messages, tools=tools_schema):
                if event["type"] == "reasoning":
                    yield {"type": "reasoning", "content": event["content"]}
                elif event["type"] == "content":
                    yield {"type": "content", "content": event["content"]}
                elif event["type"] == "tool_decide":
                    yield {"type": "status_update",
                           "content": f"🎯 智能体决策：准备激活本地工具 -> {event['name']}"}
                elif event["type"] == "final_result":
                    assistant_message = event["message"]

            if not assistant_message:
                break

            step_messages.append(assistant_message)

            # 模型主动给出文字回答（无 tool_calls）→ 正常结束
            if "tool_calls" not in assistant_message or not assistant_message["tool_calls"]:
                yield {
                    "type": "agent_finish",
                    "content": "智能体执行完毕",
                    "final_message": assistant_message
                }
                consecutive_failures = 0
                break

            yield {"type": "status_update",
                   "content": f"Detected {len(assistant_message['tool_calls'])} tool request(s). Executing..."}

            # 执行工具，统计本步失败数
            step_failures = 0
            for tool_call in assistant_message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tool_args = tool_call["function"]["arguments"]
                tool_id = tool_call["id"]

                try:
                    tool_result = execute_tool(tool_name, tool_args)
                except Exception as e:
                    tool_result = f"工具执行异常: {str(e)}"

                if self._is_tool_failure(str(tool_result)):
                    step_failures += 1
                    logger.warning(f"工具 {tool_name} 执行失败: {str(tool_result)[:200]}")

                logger.debug(f"工具执行返回: {tool_result}")

                observation_message = {
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": str(tool_result)
                }
                step_messages.append(observation_message)

            # 连续失败计数：本步全部失败则 +1，否则重置
            if step_failures == len(assistant_message["tool_calls"]):
                consecutive_failures += 1
                logger.warning(
                    f"本步全部 {step_failures} 个工具调用均失败 "
                    f"(连续 {consecutive_failures}/{self.max_steps})"
                )
            else:
                consecutive_failures = 0

            # 连续 3 轮全部失败 → 强制模型给出文字回答
            if consecutive_failures >= 3:
                async for event in self._force_text_response(
                    step_messages,
                    "你已连续多轮工具调用全部失败。请停止调用工具，"
                    "基于目前已获取的信息，直接给出你的最佳回答。"
                    "如果信息严重不足，请向用户说明哪些信息缺失以及原因。"
                ):
                    yield event
                self.messages = step_messages
                return

        # max_steps 耗尽 → 强制模型基于已有信息给出回答
        async for event in self._force_text_response(
            step_messages,
            "已达到最大操作步数限制。请基于目前已获取的信息，"
            "直接给出你的最佳回答，不要再调用工具。"
        ):
            yield event

        self.messages = step_messages
