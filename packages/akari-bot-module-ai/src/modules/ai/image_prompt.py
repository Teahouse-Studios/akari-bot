IMAGE_GENERATION_PROMPT_SYSTEM = (
    "You are an expert prompt engineer for text-to-image models. Rewrite the user's image request into one "
    "detailed English prompt that will produce a higher-quality result. Preserve the user's intent and explicit "
    "constraints. Describe the subject, composition, camera or viewpoint, lighting, color palette, materials, "
    "and rendering style. Add concrete visual detail instead of vague quality words. Do not add text, watermarks, "
    "signatures, or real brand logos unless the user requests them. Do not mention that you are rewriting a prompt. "
    "Output only the final prompt in a single paragraph."
)

IMAGE_EDIT_PROMPT_SYSTEM = (
    "You are an expert prompt engineer for image-editing models. Rewrite the user's edit request into one precise "
    "English instruction. Describe only the changes to make and, when necessary, the areas they affect. State that "
    "all other parts of the input image must remain unchanged. Preserve the user's intent and explicit constraints. "
    "Do not add text, watermarks, or signatures unless the user requests them. Do not mention that you are rewriting "
    "a prompt. Output only the final instruction in a single paragraph."
)


class ImagePromptEngineer:
    def __init__(self, client):
        self.client = client
        self.input_tokens = 0
        self.output_tokens = 0
        self.cache_read_tokens = 0
        self.cache_write_tokens = 0

    async def enhance(self, prompt: str, mode: str) -> str:
        system = IMAGE_EDIT_PROMPT_SYSTEM if mode == "edit" else IMAGE_GENERATION_PROMPT_SYSTEM
        result = await self.client.create(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            tool_choice="none",
        )
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens
        self.cache_read_tokens += result.cache_read_tokens
        self.cache_write_tokens += result.cache_write_tokens
        text = (result.text or "").strip()
        if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
            text = text[1:-1].strip()
        return text or prompt
