from . import ai


@ai.config()
class AiConfig:
    ai_default_llm: str = ""
    llm_timeout: float = 60
    llm_max_tokens: int = 2048
    llm_temperature: float = 1.0
    llm_top_p: float = 1.0
    llm_frequency_penalty: float = 0.0
    llm_presence_penalty: float = 0.0


@ai.config(secret=True)
class AiConfigSecret:
    e2b_api_key: str = ""
