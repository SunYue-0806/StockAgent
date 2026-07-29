from pathlib import Path

_PROMPT_DIR = Path(__file__).resolve().parent


def load_system_prompt() -> str:
    prompt_path = _PROMPT_DIR / "SYSTEM_PROMPT.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()