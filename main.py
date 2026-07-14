"""HelloAgents LLM 运行示例"""

from dotenv import load_dotenv

from seek_agent.agents.react_agent import ReActAgent
from seek_agent.core.llm import LLMClient

load_dotenv()



def main():

    llm_client = LLMClient()

    question = "北京今天天气怎么样？"

    react_agent = ReActAgent(llm_client)

    react_agent.run(question)


if __name__ == "__main__":
    main()
