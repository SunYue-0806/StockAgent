"""会话持久化存储 — 基于 JSONL 文件的轻量实现。

每个会话一个 ``.jsonl`` 文件，一行一条消息。
会话元数据从文件系统推导（文件名 = ID，mtime = 更新时间，首条用户消息 = 会话名）。

写入策略：
- ``append``: 增量追加新消息（O(K)，K 为新增消息数），**高频调用**。
- ``save``  : 全量覆写（O(N)，N 为总消息数），仅用于初始化或压缩。
- ``compact``: 将旧消息替换为摘要后全量覆写（低频调用），为 W3 记忆模块预留。

零新依赖，纯 Python 标准库。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

import logging

from agent_lab.llm.schema.message import (
    AssistantMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)

logger = logging.getLogger(__name__)

# ── role → 消息子类映射 ───────────────────────────────────────────

_ROLE_MODEL_MAP: dict[str, type[BaseMessage]] = {
    "user": UserMessage,
    "system": SystemMessage,
    "tool": ToolMessage,
    "assistant": AssistantMessage,
}


class SessionMeta(BaseModel):
    """会话元数据，供列表展示使用。"""

    id: str
    name: str
    message_count: int
    created_at: str
    updated_at: str


class SessionStore:
    """基于 JSONL 的会话持久化存储。

    目录结构::

        data/sessions/
        ├── a1b2c3d4....jsonl
        ├── e5f6a7b8....jsonl
        └── ...

    用法::

        store = SessionStore()
        session_id = store.create()
        store.append(session_id, new_messages)   # ← 推荐：增量追加
        store.save(session_id, all_messages)      #   全量覆写（初始化/压缩时使用）
        messages = store.load(session_id)
        sessions = store.list_all()
        store.delete(session_id)
    """

    def __init__(self, data_dir: str = "data/sessions") -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self._dir / f"{session_id}.jsonl"

    @staticmethod
    def _serialize(messages: list[BaseMessage]) -> str:
        """将消息列表序列化为 JSONL 字符串（一行一条消息）。"""
        lines = [
            json.dumps(msg.dict(exclude_none=True), ensure_ascii=False)
            for msg in messages
        ]
        return "\n".join(lines) + "\n"

    @staticmethod
    def _deserialize(raw: str) -> list[BaseMessage]:
        """将 JSONL 字符串反序列化为消息列表。"""
        messages: list[BaseMessage] = []
        for line in raw.strip().split("\n"):
            if not line.strip():
                continue
            try:
                item: dict = json.loads(line)
            except json.JSONDecodeError:
                logger.warning(f"跳过损坏的 JSON 行: {line[:80]}...")
                continue

            role = item.get("role", "")
            cls = _ROLE_MODEL_MAP.get(role, BaseMessage)
            try:
                messages.append(cls.model_validate(item))
            except Exception:
                logger.warning(f"跳过无法解析的消息: role={role}")
                continue

        return messages

    @staticmethod
    def _extract_name(messages: list[BaseMessage]) -> str:
        """从消息列表中提取会话名：首条用户消息的前 50 字符。"""
        for msg in messages:
            if msg.role == "user" and msg.content:
                return str(msg.content)[:50]
        return "(空会话)"

    def create(self, name: str = "") -> str:
        """创建新会话，返回 session_id。"""
        session_id = uuid.uuid4().hex
        self._path(session_id).write_text("", encoding="utf-8")
        logger.info(f"创建会话: {session_id[:8]}...")
        return session_id

    # ── 增量追加（高频，O(K)） ─────────────────────────────────────

    def append(self, session_id: str, new_messages: list[BaseMessage]) -> None:
        """增量追加新消息到 JSONL 文件末尾。

        仅写入新增的消息，不触碰已有内容，时间复杂度 O(K)。

        Args:
            session_id: 会话 ID。
            new_messages: 本轮新增的消息列表。
        """
        if not new_messages:
            return

        path = self._path(session_id)
        if not path.exists():
            path.write_text("", encoding="utf-8")

        lines = [
            json.dumps(msg.dict(exclude_none=True), ensure_ascii=False)
            for msg in new_messages
        ]

        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        logger.debug(
            f"追加会话 {session_id[:8]}... — +{len(new_messages)} 条消息"
        )

    # ── 全量覆写（低频，O(N)） ─────────────────────────────────────

    def save(self, session_id: str, messages: list[BaseMessage]) -> None:
        """保存会话消息历史（全量覆写 JSONL 文件）。

        适用于：初始化写入、压缩（compact）后覆写。
        常规对话持久化请使用 ``append``。
        """
        self._path(session_id).write_text(
            self._serialize(messages), encoding="utf-8"
        )
        logger.debug(f"保存会话 {session_id[:8]}... — {len(messages)} 条消息")

    def compact(self, session_id: str, messages: list[BaseMessage]) -> None:
        """压缩：用摘要替换旧消息后全量覆写。

        典型场景：对话超过 N 轮后，将早期消息替换为一条摘要，
        再调用此方法全量覆写，从而控制文件体积和 Token 消耗。

        Args:
            session_id: 会话 ID。
            messages: 压缩后的消息列表（通常包含摘要 + 近期消息）。
        """
        self.save(session_id, messages)
        logger.info(
            f"压缩会话 {session_id[:8]}... — {len(messages)} 条消息（含摘要）"
        )

    def load(self, session_id: str) -> list[BaseMessage]:
        """加载会话的消息历史。

        Returns:
            消息列表；会话文件不存在或为空时返回空列表。
        """
        path = self._path(session_id)
        if not path.exists():
            logger.warning(f"会话不存在: {session_id[:8]}...")
            return []

        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            return []

        messages = self._deserialize(raw)
        logger.info(f"加载会话 {session_id[:8]}... — {len(messages)} 条消息")
        return messages

    def list_all(self) -> list[SessionMeta]:
        """列出所有会话，按更新时间倒序。"""
        if not self._dir.exists():
            return []

        jsonl_files = sorted(
            self._dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        result: list[SessionMeta] = []
        for path in jsonl_files:
            session_id = path.stem
            stat = path.stat()

            name = ""
            msg_count = 0
            try:
                raw = path.read_text(encoding="utf-8")
                lines = [l for l in raw.strip().split("\n") if l.strip()]
                msg_count = len(lines)
                for line in lines:
                    try:
                        item = json.loads(line)
                        if item.get("role") == "user" and item.get("content"):
                            name = str(item["content"])[:50]
                            break
                    except json.JSONDecodeError:
                        continue
            except OSError:
                pass

            if not name:
                name = "(空会话)"

            result.append(
                SessionMeta(
                    id=session_id,
                    name=name,
                    message_count=msg_count,
                    created_at=datetime.fromtimestamp(
                        stat.st_ctime, tz=timezone.utc
                    ).isoformat(),
                    updated_at=datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                )
            )

        return result

    def delete(self, session_id: str) -> bool:
        """删除会话 JSONL 文件。"""
        path = self._path(session_id)
        if not path.exists():
            return False
        path.unlink()
        logger.info(f"删除会话: {session_id[:8]}...")
        return True
