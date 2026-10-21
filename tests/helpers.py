import json
from types import SimpleNamespace as NS


def text(content: str):
    """A plain text reply from the 'LLM'."""
    return NS(choices=[NS(message=NS(content=content, tool_calls=None))])

def tool(name: str, args: dict, call_id: str = "call_1"):
    """A tool-call request from the 'LLM'."""
    tc = NS(id=call_id, function=NS(name=name, arguments=json.dumps(args)))
    return NS(choices=[NS(message=NS(content=None, tool_calls=[tc]))])


class ScriptedLLM:
    """Returns pre-written responses in order. Records what it was sent."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, messages, tools):
        self.calls.append((messages, tools))
        return self.responses.pop(0)  # IndexError if called more often than scripted

class FailingLLM:
    """Simulates a provider error (rate limit, bad request, network)."""

    def __init__(self, error: Exception):
        self.error = error

    def __call__(self, messages, tools):
        raise self.error
