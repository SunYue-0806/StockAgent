"""HelloAgents LLM 运行示例"""

from dotenv import load_dotenv

from seek_agent.agents.react_agent import ReActAgent
from seek_agent.core.llm import LLMClient
from seek_agent.tools import weather_tool

load_dotenv()



def main():

    llm_client = LLMClient()

    question = "北京的天气今天如何？"

    react_agent = ReActAgent(llm_client)

    react_agent.run(question)


if __name__ == "__main__":
    main()
