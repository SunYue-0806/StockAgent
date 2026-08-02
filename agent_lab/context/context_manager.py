import logging
from typing import List, Optional, Tuple, Dict, Any
from agent_lab.core.token_counter import TokenCounter
from agent_lab.llm.schema.message import (
    BaseMessage, SystemMessage, UserMessage, AssistantMessage, ToolMessage
)

logger = logging.getLogger(__name__)


class ContextManager:
    """
    统一管理 Agent 的上下文窗口、Token 预算与消息组切片
    """

    def __init__(
            self,
            token_counter: TokenCounter,
            system_prompt: str,
            max_context_tokens: int = 32000,
            max_response_tokens: int = 4000,
    ):
        self.token_counter = token_counter
        self.system_prompt = system_prompt
        self.max_context_tokens = max_context_tokens
        self.max_response_tokens = max_response_tokens

    def build_sliding_window_messages(
            self, current_step_messages: List[BaseMessage], tools_schema: List[Dict[str, Any]]
    ) -> List[BaseMessage]:
        if not current_step_messages:
            return []

        # 1. 提取置顶消息 (pinned_messages)
        pinned_messages, remaining_history = self._extract_pinned_and_remaining_messages(current_step_messages)

        # 2. 计算 Token 预算
        budget = self._calculate_history_token_budget(pinned_messages, tools_schema)

        # 3. 按完整 Turn 轮次打包消息
        grouped_messages = self._group_messages_by_user_turns(remaining_history)

        # 4. 根据预算筛选最新的 Turn
        selected_groups = self._filter_message_groups_by_budget(grouped_messages, budget)

        # 5. 平铺拼接
        flattened_history = [msg for group in selected_groups for msg in group]
        return pinned_messages + flattened_history

    def _extract_pinned_and_remaining_messages(
            self, current_step_messages: List[BaseMessage]
    ) -> Tuple[List[BaseMessage], List[BaseMessage]]:
        pinned_messages: List[BaseMessage] = []
        if isinstance(current_step_messages[0], SystemMessage):
            system_msg = current_step_messages[0]
            rest_messages = current_step_messages[1:]
        else:
            system_msg = SystemMessage(content=self.system_prompt)
            rest_messages = current_step_messages

        pinned_messages.append(system_msg)

        first_user_msg: Optional[UserMessage] = None
        remaining_history: List[BaseMessage] = []

        for msg in rest_messages:
            if first_user_msg is None and isinstance(msg, UserMessage):
                first_user_msg = msg
            else:
                remaining_history.append(msg)

        if first_user_msg:
            pinned_messages.append(first_user_msg)

        return pinned_messages, remaining_history

    def _calculate_history_token_budget(
            self, pinned_messages: List[BaseMessage], tools_schema: List[Dict[str, Any]]
    ) -> int:
        pinned_tokens = sum(self.token_counter.count_message(m) for m in pinned_messages)
        tools_tokens = self.token_counter.count_tools_schema_tokens(tools_schema)
        budget = self.max_context_tokens - pinned_tokens - tools_tokens - self.max_response_tokens
        return budget if budget > 0 else 1000

    def _group_messages_by_user_turns(
            self, history_messages: List[BaseMessage]
    ) -> List[List[BaseMessage]]:
        grouped_messages: List[List[BaseMessage]] = []
        i, n = 0, len(history_messages)
        while i < n:
            msg = history_messages[i]
            if isinstance(msg, UserMessage):
                turn_group = [msg]
                i += 1
                while i < n and not isinstance(history_messages[i], UserMessage):
                    turn_group.append(history_messages[i])
                    i += 1
                grouped_messages.append(turn_group)
            else:
                grouped_messages.append([msg])
                i += 1
        return grouped_messages

    def _filter_message_groups_by_budget(
            self, grouped_messages: List[List[BaseMessage]], budget: int
    ) -> List[List[BaseMessage]]:
        selected_groups: List[List[BaseMessage]] = []
        current_tokens = 0
        for group in reversed(grouped_messages):
            group_tokens = sum(self.token_counter.count_message(m) for m in group)
            if current_tokens + group_tokens <= budget:
                selected_groups.insert(0, group)
                current_tokens += group_tokens
            else:
                break
        return selected_groups
