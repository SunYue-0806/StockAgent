import json
from typing import AsyncGenerator, Dict, Any

from stock_agent.llm.openai_model_client import OpenAIModelClient
from stock_agent.prompt.prompt_utils import load_system_prompt
from stock_agent.tools.tools import get_all_tools_schema, execute_tool


class ReActAgent:
    def __init__(self, client: OpenAIModelClient):
        self.client = client
        self.messages = []
        self.max_steps = 5
        self.system_prompt = load_system_prompt()
        self.messages = [
            {"role": "system", "content": self.system_prompt}
        ]

    async def run(self, user_message: str) -> AsyncGenerator[Dict[str, Any], None]:
        self.messages.append({"role": "user", "content": user_message})
        step_messages = list(self.messages)
        current_step = 0

        while current_step < self.max_steps:
            current_step += 1
            print(f"\n--- 第 {current_step} 步 ---")

            tools_schema = get_all_tools_schema()

            assistant_message = None

            async for event in self.client.invoke(step_messages, tools=tools_schema):
                if event["type"] == "reasoning":
                    yield {"type": "reasoning", "content": event["content"]}
                elif event["type"] == "content":
                    yield {"type": "content", "content": event["content"]}
                elif event["type"] == "tool_decide":
                    yield {"type": "status_update", "content": f"🎯 智能体决策：准备激活本地工具 -> {event['name']}"}
                elif event["type"] == "final_result":
                    assistant_message = event["message"]

            if not assistant_message:
                break

            step_messages.append(assistant_message)

            if "tool_calls" not in assistant_message or not assistant_message["tool_calls"]:
                yield {
                    "type": "agent_finish",
                    "content": "智能体执行完毕",
                    "final_message": assistant_message
                }
                break

            yield {"type": "status_update",
                   "content": f"Detected {len(assistant_message['tool_calls'])} tool request(s). Executing..."}

            for tool_call in assistant_message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tool_args = tool_call["function"]["arguments"]
                tool_id = tool_call["id"]

                try:
                    tool_result = execute_tool(tool_name, tool_args)
                except Exception as e:
                    tool_result = f"工具执行异常: {str(e)}"

                print(f"全局工具执行返回: {tool_result}")

                observation_message = {
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": str(tool_result)
                }

                step_messages.append(observation_message)

        self.messages = step_messages

        yield {"type": "agent_finish", "status": "success"}
