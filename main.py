import asyncio

from agent_lab.agents.react_agent import ReActAgent
import logging

logger = logging.getLogger(__name__)
from agent_lab.llm.openai_model_client import OpenAIModelClient
from agent_lab.session import SessionStore
from agent_lab.tools import weather_tool  # noqa: F401
from agent_lab.tools.builtin import file_tool  # noqa: F401


def _print_session_list(store: SessionStore) -> None:
    """打印历史会话列表。"""
    sessions = store.list_all()
    if not sessions:
        print("(无历史会话)")
        return

    for i, s in enumerate(sessions):
        print(f"  [{i}] {s.id[:8]}...  {s.name}  ({s.message_count} 条消息 | {s.updated_at[:19]})")


async def main():
    store = SessionStore()
    client = OpenAIModelClient()

    sessions = store.list_all()
    session_id = None

    if sessions:
        print(f"\n📂 历史会话 ({len(sessions)} 个):")
        _print_session_list(store)
        print()

        choice = input(
            "输入编号恢复会话，输入 n 创建新会话，输入 q 退出: "
        ).strip()

        if choice.lower() == "q":
            return
        elif choice.lower() == "n":
            session_id = store.create()
        else:
            try:
                idx = int(choice)
                if 0 <= idx < len(sessions):
                    session_id = sessions[idx].id
                else:
                    print("编号无效，创建新会话。")
                    session_id = store.create()
            except ValueError:
                print("输入无效，创建新会话。")
                session_id = store.create()
    else:
        session_id = store.create()

    agent = ReActAgent(client=client, session_id=session_id, session_store=store)

    msg_count = len(agent.messages) - 1
    print(f"\n🤖 ReAct 智能体已就绪！")
    if msg_count > 0:
        print(f"   📌 已恢复 {msg_count} 条历史消息")
    print(f"   🔑 会话 ID: {session_id[:8]}...")
    print("   输入 'exit' 或 'quit' 退出。")

    try:
        while True:
            user_input = input("\n👤 用户: ")
            if user_input.strip().lower() in ["exit", "quit"]:
                logger.info("再见！")
                break

            if not user_input.strip():
                continue

            logger.info("智能体正在思考...")

            async for event in agent.run(user_input):
                event_type = event.get("type")

                if event_type == "reasoning":
                    print(event["content"], end="", flush=True)

                elif event_type == "content":
                    print(event["content"], end="", flush=True)

                elif event_type == "status_update":
                    logger.info(f"[状态] {event['content']}")

                elif event_type == "agent_finish":
                    logger.info("[结束] 本轮对话执行完毕。")

            print()

    except KeyboardInterrupt:
        print("\n👋 已中断。会话已自动保存。")


if __name__ == "__main__":
    asyncio.run(main())
