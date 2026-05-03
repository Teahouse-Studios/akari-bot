from . import ai


@ai.config()
class AiConfig:
    ai_default_llm: str = ""
    llm_max_tokens: int = 4096
    llm_temperature: float = 1.0
    llm_top_p: float = 1.0
    llm_frequency_penalty: float = 0.0
    llm_presence_penalty: float = 0.0
