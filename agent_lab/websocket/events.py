# agent_lab/protocol/events.py
from enum import Enum
from typing import Dict, Any, Union


class WebSocketEventType(Enum):
    """
    智能体 WebSocket 实时事件类型枚举
    """
    # 全局与状态控制事件
    AGENT_STATUS = "agent_status"  # 轮次步骤状态变更（第几步思考）
    AGENT_SUCCESS = "agent_success"  # 任务圆满良性结束
    AGENT_ERROR = "agent_error"  # 运行时灾难性崩溃异常

    # 模型文本与思考流事件
    TEXT_REASONING = "text_reasoning"  # 深度思考/思维链实时蹦字
    TEXT_CONTENT = "text_content"  # 标准答复正文实时蹦字

    # 本地工具执行生命周期事件
    TOOL_START = "tool_start"  # 模型流中首次检测到工具调用意图
    TOOL_BATCH_EXECUTE = "tool_batch_execute"  # 这一轮共有多少个工具要批量执行
    TOOL_EXECUTING = "tool_executing"  # 某个具体的本地 Python 函数开始在线跑数
    TOOL_RESPONSE = "tool_response"  # 工具执行完毕，返回了具体的观察结果


def create_ws_event(event_type: Union[WebSocketEventType, str], payload: Any = None) -> Dict[str, Any]:
    if isinstance(event_type, str):
        try:
            resolved_type = WebSocketEventType(event_type)
        except ValueError:
            raise ValueError(f"❌ [EventProtocolError] 未知且不合法的 WebSocket 事件类型: '{event_type}'")
    else:
        resolved_type = event_type

    return {
        "event": resolved_type.value,
        "payload": payload if payload is not None else {}
    }
