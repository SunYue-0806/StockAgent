import asyncio

from stock_agent.agents.react_agent import ReActAgent
from stock_agent.llm.openai_model_client import OpenAIModelClient
from stock_agent.tools import weather_tool


async def main():
    client = OpenAIModelClient()

    agent = ReActAgent(client=client)

    print("🤖 ReAct 智能体已就绪！输入 'exit' 或 'quit' 退出。")

    while True:
        user_input = input("\n👤 用户: ")
        if user_input.strip().lower() in ["exit", "quit"]:
            print("再见！")
            break

        if not user_input.strip():
            continue

        print("🤖 智能体正在思考...", flush=True)

        async for event in agent.run(user_input):
            event_type = event.get("type")

            if event_type == "reasoning":
                print(event["content"], end="", flush=True)

            elif event_type == "content":
                print(event["content"], end="", flush=True)

            elif event_type == "status_update":
                print(f"\n⚙️ [状态] {event['content']}")

            elif event_type == "agent_finish":
                print(f"\n✅ [结束] 本轮对话执行完毕。")


if __name__ == "__main__":
    asyncio.run(main())
