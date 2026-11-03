from common import config as common_config
from common import guardrails
from common import llm
from common.embedding import embed_text, embed_texts, retry as _retry
from clarifier import config


def _guard_system(message: dict) -> dict:
    return {**message, "content": guardrails.ensure(message["content"])} if message.get("role") == "system" else message


def chat_with_tools(
    messages: list[dict],
    tools: list[dict],
    model: str | None = None,
    max_tokens: int | None = None,
    tool_choice: str | dict = "auto",
):
    """Satu giliran chat completion dengan tool calling. Balikkan message object OpenAI mentah
    (punya `.content` dan `.tool_calls`) supaya pemanggil bisa loop sampai model berhenti minta tool."""
    response = _retry(
        llm.client().chat.completions.create,
        model=model or config.CHAT_MODEL,
        max_completion_tokens=max_tokens or config.CHAT_MAX_TOKENS,
        reasoning_effort=common_config.REASONING_EFFORT,
        messages=[_guard_system(message) for message in messages],
        tools=tools,
        tool_choice=tool_choice,
    )
    return response.choices[0].message
