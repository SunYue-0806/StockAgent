import logging
from typing import AsyncGenerator, Dict, Any, List, Optional, TYPE_CHECKING

from agent_lab.context.context_manager import ContextManager
from agent_lab.core.token_counter import TokenCounter
from agent_lab.llm.openai_model_client import OpenAIModelClient
from agent_lab.llm.schema.message import UserMessage, BaseMessage, SystemMessage, ToolMessage, AssistantMessage
from agent_lab.prompt.prompt_utils import load_system_prompt
from agent_lab.tools.tool_manager import get_all_tools_schema, execute_tool

if TYPE_CHECKING:
    from agent_lab.session.store import SessionStore

logger = logging.getLogger(__name__)


class ReActAgent:
    def __init__(
            self,
            client: OpenAIModelClient,
            session_id: Optional[str] = None,
            session_store: Optional["SessionStore"] = None,
            max_context_tokens: int = 32000,
            max_response_tokens: int = 4000,
    ):
        self.client = client
        self.max_steps = 500
        self.system_prompt = load_system_prompt()
        self.session_id = session_id
        self.session_store = session_store
        self.max_context_tokens = max_context_tokens
        self.max_response_tokens = max_response_tokens
        self.messages: List[BaseMessage] = [SystemMessage(content=self.system_prompt)]
        self.token_counter = TokenCounter(model_name=client.model)
        self.context_manager = ContextManager(
            token_counter=self.token_counter,
            system_prompt=self.system_prompt,
            max_context_tokens=max_context_tokens,
            max_response_tokens=max_response_tokens
        )

        self._saved_count: int = 0

        if session_id and session_store:
            loaded = session_store.load(session_id)
            if loaded:
                self.messages = loaded
                self._saved_count = len(loaded)
                logger.info(f"从会话 {session_id[:8]}... 恢复了 {len(loaded)} 条消息")
            else:
                logger.info(f"会话 {session_id[:8]}... 无历史消息，创建新会话")

    async def run(self, user_message: str) -> AsyncGenerator[Dict[str, Any], None]:

        self.messages.append(UserMessage(content=user_message))
        step_messages = list(self.messages)
        current_step = 0

        while current_step < self.max_steps:
            current_step += 1
            logger.info(f"--- 第 {current_step} 步 ---")

            tools_schema = get_all_tools_schema()

            assistant_message: Optional[AssistantMessage] = None

            llm_input_messages = self.context_manager.build_sliding_window_messages(step_messages, tools_schema)

            async for event in self.client.invoke(llm_input_messages, tools=tools_schema):
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

            if not getattr(assistant_message, "tool_calls", None):
                yield {
                    "type": "agent_finish",
                    "content": "智能体执行完毕",
                    "final_message": assistant_message
                }
                break

            yield {"type": "status_update",
                   "content": f"Detected {len(assistant_message.tool_calls)} tool request(s). Executing..."}

            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.name
                tool_args = tool_call.arguments
                tool_id = tool_call.id

                try:
                    tool_result = execute_tool(tool_name, tool_args)
                except Exception as e:
                    tool_result = f"工具执行异常: {str(e)}"

                logger.info(f"工具执行返回: {tool_result}")

                tool_message = ToolMessage(tool_call_id=tool_id, tool_name=tool_name, content=str(tool_result))

                step_messages.append(tool_message)

        self.messages = step_messages

        if self.session_id and self.session_store:
            new_msgs = self.messages[self._saved_count:]
            if new_msgs:
                self.session_store.append(self.session_id, new_msgs)
                self._saved_count = len(self.messages)
                logger.debug(f"增量追加 {len(new_msgs)} 条消息 (总计 {self._saved_count})")
