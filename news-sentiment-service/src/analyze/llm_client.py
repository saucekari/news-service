from typing import Dict


class LLMClient:
    def __init__(self, model_name: str = "local-llm") -> None:
        self.model_name = model_name

    async def parse(self, text: str) -> Dict[str, str]:
        """Placeholder for local LLM calls and markdown cleanup."""
        return {"sentiment": "neutral", "text": text}
