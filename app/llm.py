from groq import Groq
from app import config 

_client: Groq | None = None
def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client

def chat(messages: list[dict], tools: list[dict]):
    kwargs = dict(
        model = config.GROQ_MODEL,
        messages = messages,
        temperature = 0.1,
        max_tokens = 300,
    )
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return _get_client().chat.completions.create(**kwargs)
