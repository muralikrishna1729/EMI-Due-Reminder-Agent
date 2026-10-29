"""Groq-backed evaluation judge for DeepEval.

Allows DeepEval metrics to run against Groq-supported LLM models without
requiring an OpenAI API key or modifying the production EMI agent configuration.
"""
from __future__ import annotations

import os
import json
import logging
from typing import Any, Optional, Type, Union

from pydantic import BaseModel
from deepeval.models.base_model import DeepEvalBaseLLM

from app import config

logger = logging.getLogger("evals.judge")

# Ensure DeepEval does not attempt third-party telemetry in sandboxed/restricted environments
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")


class GroqJudge(DeepEvalBaseLLM):
    """DeepEval-compatible judge model powered by Groq.
    
    Inherits from DeepEvalBaseLLM and integrates with Groq's official API
    using Groq-hosted open-weights models (e.g. Llama-3.3-70B-Versatile).
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> None:
        selected_model = (
            model_name
            or os.getenv("GROQ_JUDGE_MODEL")
            or config.GROQ_MODEL
            or os.getenv("GROQ_MODEL")
            or "openai/gpt-oss-120b"
        )
        self.api_key = api_key or os.getenv("GROQ_API_KEY") or config.GROQ_API_KEY
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._sync_client = None
        self._async_client = None
        super().__init__(model=selected_model)

    def load_model(self) -> Any:
        """Initialize and return the underlying Groq client."""
        from groq import AsyncGroq, Groq

        if not self.api_key:
            logger.warning(
                "GROQ_API_KEY is not set. Real LLM evaluations will fail unless mock or API key is provided."
            )
        self._sync_client = Groq(api_key=self.api_key or "missing_key")
        self._async_client = AsyncGroq(api_key=self.api_key or "missing_key")
        return self._sync_client

    def get_model_name(self) -> str:
        return self.name

    def _prepare_messages(self, prompt: str, schema: Optional[Type[BaseModel]] = None) -> list[dict[str, str]]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict, objective evaluation judge for conversational AI agents. "
                    "Follow all schema, scoring, and output format requirements exactly."
                ),
            }
        ]
        
        # Groq requires the word 'json' somewhere in messages if json_object mode is requested
        if schema is not None and "json" not in prompt.lower():
            prompt = f"{prompt}\n\nPlease respond in valid JSON format."

        messages.append({"role": "user", "content": prompt})
        return messages

    def generate(
        self,
        prompt: str,
        schema: Optional[Type[BaseModel]] = None,
        **kwargs: Any,
    ) -> Union[str, BaseModel]:
        """Synchronously generate an evaluation response."""
        if self._sync_client is None:
            self.load_model()

        messages = self._prepare_messages(prompt, schema)
        request_kwargs: dict[str, Any] = {
            "model": self.name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Enable JSON mode when a structured schema is requested or JSON is explicitly asked
        if schema is not None or "json" in prompt.lower():
            request_kwargs["response_format"] = {"type": "json_object"}

        response = self._sync_client.chat.completions.create(**request_kwargs)
        content = (response.choices[0].message.content or "").strip()

        if schema is not None and issubclass(schema, BaseModel):
            try:
                return schema.model_validate_json(content)
            except Exception:
                # Let DeepEval's fallback extraction handle raw json string
                return content

        return content

    async def a_generate(
        self,
        prompt: str,
        schema: Optional[Type[BaseModel]] = None,
        **kwargs: Any,
    ) -> Union[str, BaseModel]:
        """Asynchronously generate an evaluation response."""
        if self._async_client is None:
            self.load_model()

        messages = self._prepare_messages(prompt, schema)
        request_kwargs: dict[str, Any] = {
            "model": self.name,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if schema is not None or "json" in prompt.lower():
            request_kwargs["response_format"] = {"type": "json_object"}

        response = await self._async_client.chat.completions.create(**request_kwargs)
        content = (response.choices[0].message.content or "").strip()

        if schema is not None and issubclass(schema, BaseModel):
            try:
                return schema.model_validate_json(content)
            except Exception:
                return content

        return content

    def generate_with_schema(self, *args: Any, schema: Optional[Type[BaseModel]] = None, **kwargs: Any) -> Any:
        return self.generate(*args, schema=schema, **kwargs)

    async def a_generate_with_schema(self, *args: Any, schema: Optional[Type[BaseModel]] = None, **kwargs: Any) -> Any:
        return await self.a_generate(*args, schema=schema, **kwargs)


_cached_judge: Optional[GroqJudge] = None


def get_eval_judge(model_name: Optional[str] = None) -> GroqJudge:
    """Return a configured evaluation judge powered by Groq."""
    global _cached_judge
    if _cached_judge is None or (model_name and _cached_judge.name != model_name):
        _cached_judge = GroqJudge(model_name=model_name)
    return _cached_judge

