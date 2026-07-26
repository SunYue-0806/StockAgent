import asyncio

from agent_lab.agents.react_agent import ReActAgent
from agent_lab.core.logger import logger
from agent_lab.llm.openai_model_client import OpenAIModelClient
from agent_lab.tools import weather_tool
from agent_lab.tools.builtin import file_tool


async def main():
    client = OpenAIModelClient()

    agent = ReActAgent(client=client)

    logger.info("ReAct 智能体已就绪！输入 'exit' 或 'quit' 退出。")

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


if __name__ == "__main__":
    asyncio.run(main())
