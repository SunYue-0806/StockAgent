class MessageBuffer:
    def __init__(self, history_messages: list | None = None):
        self._messages: list = list(history_messages or [])
        self._history_size = len(self._messages)

    def add(self, message) -> None:
        if isinstance(message, list):
            self._messages.extend(message)
        else:
            self._messages.append(message)

    def get_all(self) -> list:
        return self._messages

    def get_recent(self, n: int) -> list:
        """获取最近 n 条消息。"""
        return self._messages[-n:] if n > 0 else []

    def get_current_turn(self) -> list:
        """只获取本轮新增的消息（不含历史）。"""
        return self._messages[self._history_size:]

    def __len__(self) -> int:
        return len(self._messages)
