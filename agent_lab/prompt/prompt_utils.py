def load_system_prompt() -> str:
    with open("agent_lab/prompt/SYSTEM_PROMPT.md", "r", encoding="utf-8") as f:
        return f.read().strip()
