"""
llm_shim.py — Replaces tuneapi (tt / ta / tu namespaces) entirely.
Deployed: 2026-08-13 — includes SimplerTimes and OpenAI→Anthropic model ID map.

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
# Overridable without a redeploy: not every Anthropic account has access to
# every model, and a wrong ID fails with a 404 that the chat path would
# otherwise swallow into a generic "something went wrong" for the seeker.
import os as _os

_DEFAULT_MODEL = _os.getenv("ASAM_ANTHROPIC_MODEL", "claude-3-5-haiku-20241022")


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
    def joinp(*parts) -> str:
        """tu.joinp replacement — os.path.join."""
        import os
        return os.path.join(*parts)

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


def _compat_field(*args, **kwargs):
    """
    Compatibility wrapper for the old TuneAPI Field calling convention.

    TuneAPI called Field as:
      tt.F("description")               → required field
      tt.F("description", default)      → field with default

    Pydantic v2 Field() only accepts the default as the first positional arg.
    This shim detects the old signature (first arg is a str that looks like a
    description) and rewrites it to the correct pydantic v2 form.
    """
    if args and isinstance(args[0], str) and "description" not in kwargs:
        description = args[0]
        if len(args) > 1:
            # tt.F("description", default_value)
            return Field(args[1], description=description, **kwargs)
        else:
            # tt.F("description") — required field, no default
            return Field(description=description, **kwargs)
    # Normal pydantic v2 usage: Field(default, ...)
    return Field(*args, **kwargs)


class _TT:
    # Pydantic re-exports (wire.py uses tt.BM and tt.F)
    BM    = BaseModel
    F     = staticmethod(_compat_field)
    Field = staticmethod(_compat_field)

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


class EmbeddingResponse:
    """Returned by AnthropicModel.embedding_async() — mirrors the TuneAPI shape.

    Callers do `resp.embedding[0]` to get the vector, so `embedding` is a
    list-of-vectors even for a single input.
    """
    def __init__(self, embedding: List[List[float]]):
        self.embedding = embedding


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
        import os

        self.model_id = _OPENAI_TO_ANTHROPIC.get(id, id)   # remap if needed

        # The chat key must be an Anthropic key. ASAM_OPENAI_TOKEN is the
        # historical name (it fed the TuneAPI proxy) and now holds sk-ant-…,
        # but allow an explicit ASAM_ANTHROPIC_TOKEN to take precedence.
        chat_key = os.getenv("ASAM_ANTHROPIC_TOKEN", "") or (api_token or "")
        self._client = anthropic.AsyncAnthropic(api_key=chat_key)

        # Embeddings need a genuine OpenAI key — kept separate on purpose.
        self._embedding_token = os.getenv("ASAM_EMBEDDING_TOKEN", "")
        if not self._embedding_token and (api_token or "").startswith("sk-") \
                and not (api_token or "").startswith("sk-ant-"):
            # The configured token is actually an OpenAI key — reuse it.
            self._embedding_token = api_token

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

        # Anthropic returns a list of content blocks; concatenate every text
        # block rather than assuming block 0 exists and is text. A response
        # with no text block would otherwise raise IndexError and surface to
        # the seeker as "Something unexpected interrupted the response".
        parts = [
            b.text for b in (response.content or [])
            if getattr(b, "type", None) == "text" and getattr(b, "text", None)
        ]
        return LLMResponse(content="".join(parts))

    async def embedding_async(
        self,
        text: Union[str, List[str]],
        model: str = "text-embedding-3-small",
        **_kwargs,
    ) -> EmbeddingResponse:
        """
        Embeddings for vector search.  Anthropic does not serve an embeddings
        API, and the stored pgvector column was built with OpenAI's
        text-embedding-3-small, so we must call OpenAI directly to stay in the
        same vector space.

        Requires a real OpenAI key in ASAM_EMBEDDING_TOKEN (or an
        ASAM_OPENAI_TOKEN that is actually an OpenAI key).  If none is
        configured we raise, and the caller falls back to full-text search.
        """
        import os

        key = self._embedding_token or os.getenv("ASAM_EMBEDDING_TOKEN", "")
        if not key or not key.startswith("sk-") or key.startswith("sk-ant-"):
            raise RuntimeError(
                "No OpenAI embedding key configured (ASAM_EMBEDDING_TOKEN). "
                "Vector search unavailable; falling back to full-text search."
            )

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=key)
        inputs = [text] if isinstance(text, str) else list(text)
        resp = await client.embeddings.create(model=model, input=inputs)
        return EmbeddingResponse(embedding=[d.embedding for d in resp.data])


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
