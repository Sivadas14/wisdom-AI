"""
llm_shim.py — Replaces tuneapi (tt / ta / tu namespaces) entirely.

Uses only:
  - anthropic  (official SDK, direct API calls)
  - pydantic   (already a project dependency)
  - stdlib     (logging, json, uuid, time)

Drop-in: every file that did `from src.llm_shim import tt, ta, tu`
can now do `from src.llm_shim import tt, ta, tu` with zero other changes.
"""
from __future__ import annotations

import datetime
import json
import logging
import time
import uuid
from typing import Any, List, Optional, Union

import anthropic
from pydantic import BaseModel, Field

# ── Model to use ──────────────────────────────────────────────────────────────
_DEFAULT_MODEL = "claude-3-5-haiku-20241022"


# ─────────────────────────────────────────────────────────────────────────────
# tu — utilities
# ─────────────────────────────────────────────────────────────────────────────

class _Logger:
    """Drop-in for tu.logger — delegates to stdlib logging."""
    def __init__(self, name: str = "app"):
        self._l = logging.getLogger(name)

    def info(self, msg, *a, **kw):      self._l.info(msg, *a, **kw)
    def warning(self, msg, *a, **kw):   self._l.warning(msg, *a, **kw)
    def error(self, msg, *a, **kw):     self._l.error(msg, *a, **kw)
    def debug(self, msg, *a, **kw):     self._l.debug(msg, *a, **kw)
    def exception(self, msg, *a, **kw): self._l.exception(msg, *a, **kw)


def _to_json(obj: Any, tight: bool = False) -> str:
    """tu.to_json replacement."""
    sep = (",", ":") if tight else (", ", ": ")
    return json.dumps(obj, separators=sep, ensure_ascii=False)


class _SimplerTimes:
    """Drop-in for tu.SimplerTimes — datetime utilities used throughout chat.py."""

    @staticmethod
    def get_now_human() -> str:
        """Human-readable current datetime, e.g. 'Thursday, 13 August 2026, 10:30 AM'."""
        return datetime.datetime.now().strftime("%A, %d %B %Y, %I:%M %p")

    @staticmethod
    def get_now_fp64() -> float:
        """Current time as a float (seconds since epoch) — used for timing."""
        return time.time()

    @staticmethod
    def get_now_datetime() -> datetime.datetime:
        """Current UTC datetime — used for DB timestamp columns."""
        return datetime.datetime.utcnow()


class _TU:
    logger = _Logger()
    SimplerTimes = _SimplerTimes

    @staticmethod
    def to_json(obj: Any, tight: bool = False) -> str:
        return _to_json(obj, tight)

    @staticmethod
    def folder(path: str) -> str:
        """tu.folder replacement — parent directory of a path (resolved)."""
        import os
        return os.path.dirname(os.path.abspath(path))

    @staticmethod
    def get_snowflake() -> str:
        """tu.get_snowflake replacement — a unique hex ID."""
        return uuid.uuid4().hex


# ─────────────────────────────────────────────────────────────────────────────
# tt — message/thread types + pydantic re-exports
# ─────────────────────────────────────────────────────────────────────────────

class Message:
    """Drop-in for tt.Message."""

    SYSTEM    = "system"
    HUMAN     = "user"
    GPT       = "assistant"

    # TuneAPI used "gpt"/"human" internally; normalise on construction.
    _ROLE_MAP = {
        "gpt": "assistant", "machine": "assistant", "assistant": "assistant",
        "human": "user",    "user": "user",
        "system": "system",
    }

    def __init__(self, value: str, role: str = "user"):
        self.role  = self._ROLE_MAP.get(role, role)
        self.value = value

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.value}

    def __repr__(self) -> str:
        return f"<{self.role}: {self.value[:60]}>"


def assistant(content: str) -> Message:
    return Message(content, "assistant")

def human(content: str) -> Message:
    return Message(content, "user")

def system(content: str) -> Message:
    return Message(content, "system")


class Thread:
    """Drop-in for tt.Thread — an ordered list of Messages."""

    def __init__(self, *messages: Message):
        self.chats: List[Message] = list(messages)

    def append(self, msg: Message) -> None:
        self.chats.append(msg)

    def __len__(self)         -> int:           return len(self.chats)
    def __iter__(self):                          return iter(self.chats)
    def __getitem__(self, idx):                  return self.chats[idx]

    def to_anthropic(self) -> tuple[str, List[dict]]:
        """Convert to (system_prompt, messages_list) for the Anthropic API."""
        system_parts: List[str] = []
        messages: List[dict]   = []

        for m in self.chats:
            if m.role == "system":
                system_parts.append(m.value)
                continue
            # Anthropic requires strictly alternating user/assistant turns.
            # Merge consecutive messages with the same role.
            if messages and messages[-1]["role"] == m.role:
                messages[-1]["content"] += "\n" + m.value
            else:
                messages.append({"role": m.role, "content": m.value})

        return "\n".join(system_parts), messages


class ModelInterface:
    """Drop-in for tt.ModelInterface."""
    async def chat_async(self, thread: Thread) -> "LLMResponse":
        raise NotImplementedError


class _TT:
    # Pydantic re-exports (wire.py uses tt.BM and tt.F)
    BM    = BaseModel
    F     = staticmethod(Field)
    Field = staticmethod(Field)

    # Message types
    Message       = Message
    Thread        = Thread
    ModelInterface = ModelInterface

    # Message builders
    assistant = staticmethod(assistant)
    human     = staticmethod(human)
    system    = staticmethod(system)


# ─────────────────────────────────────────────────────────────────────────────
# ta — LLM callers + SSE formatting
# ─────────────────────────────────────────────────────────────────────────────

class LLMResponse:
    """Returned by AnthropicModel.chat_async()."""
    def __init__(self, content: str):
        self.content = content


def _to_openai_chunk(msg: Union[Message, dict, str]) -> str:
    """Format a message as an OpenAI-compatible SSE data: line."""
    if isinstance(msg, Message):
        content = msg.value
    elif isinstance(msg, dict):
        content = msg.get("content", "")
    else:
        content = str(msg)

    chunk = {
        "id":      f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object":  "chat.completion.chunk",
        "created": int(time.time()),
        "model":   _DEFAULT_MODEL,
        "choices": [{
            "index":         0,
            "delta":         {"role": "assistant", "content": content},
            "finish_reason": None,
        }],
    }
    return f"data: {json.dumps(chunk)}\n\n"


# chat.py calls ta.Openai(id="gpt-4o") because the old TuneAPI silently routed
# OpenAI model IDs to Anthropic.  Map them here so nothing breaks.
_OPENAI_TO_ANTHROPIC: dict[str, str] = {
    "gpt-4o":            _DEFAULT_MODEL,
    "gpt-4o-mini":       _DEFAULT_MODEL,
    "gpt-4":             _DEFAULT_MODEL,
    "gpt-4-turbo":       _DEFAULT_MODEL,
    "gpt-3.5-turbo":     _DEFAULT_MODEL,
    "gpt-4.1":           _DEFAULT_MODEL,
    "gpt-5.1-chat-latest": _DEFAULT_MODEL,
}


class AnthropicModel(ModelInterface):
    """
    Direct Anthropic SDK wrapper.  Replaces ta.Anthropic and ta.Openai.
    OpenAI model IDs (gpt-4o etc.) are silently remapped to the Anthropic default.
    """

    def __init__(
        self,
        id: str = _DEFAULT_MODEL,
        api_token: Optional[str] = None,
        **_kwargs,          # absorb unused params (base_url, extra_headers, …)
    ):
        self.model_id = _OPENAI_TO_ANTHROPIC.get(id, id)   # remap if needed
        self._client  = anthropic.AsyncAnthropic(api_key=api_token or "")

    async def chat_async(
        self,
        thread: Thread,
        max_tokens: int = 1500,
    ) -> LLMResponse:
        system_prompt, messages = thread.to_anthropic()

        kwargs: dict = dict(
            model      = self.model_id,
            max_tokens = max_tokens,
            messages   = messages,
        )
        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self._client.messages.create(**kwargs)
        return LLMResponse(content=response.content[0].text)


class _TA:
    Anthropic       = AnthropicModel
    Openai          = AnthropicModel   # legacy alias — routes to Anthropic
    to_openai_chunk = staticmethod(_to_openai_chunk)


# ─────────────────────────────────────────────────────────────────────────────
# Public namespace singletons — imported just like tuneapi sub-modules
# ─────────────────────────────────────────────────────────────────────────────

tu = _TU()
tt = _TT()
ta = _TA()
