from dataclasses import dataclass, field
from decimal import Decimal

from ..image_prompt import ImagePromptEngineer


@dataclass
class ToolContext:
    api_url: str = ""
    api_key: str = ""
    superuser: bool = False
    images: list[str] = field(default_factory=list)
    prompt_engineer: ImagePromptEngineer | None = None
    cost: Decimal = field(default_factory=lambda: Decimal("0"))

    def prompt_usage(self) -> tuple[int, int, int, int]:
        if self.prompt_engineer is None:
            return (0, 0, 0, 0)
        return (
            self.prompt_engineer.input_tokens,
            self.prompt_engineer.output_tokens,
            self.prompt_engineer.cache_read_tokens,
            self.prompt_engineer.cache_write_tokens,
        )


def create_tool_context(client, api_url: str, api_key: str, superuser: bool = False) -> ToolContext:
    return ToolContext(
        api_url=api_url,
        api_key=api_key,
        superuser=superuser,
        prompt_engineer=ImagePromptEngineer(client),
    )
