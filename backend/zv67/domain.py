"""Normalized domain contracts shared by the API and upstream providers."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Role = Literal["system", "developer", "user", "assistant", "tool"]


class MockContentError(ValueError):
    """Raised when a message contains content ZV67 cannot accept yet."""


class ChatMessage(BaseModel):
    """One inbound chat message in OpenAI wire format."""

    model_config = ConfigDict(extra="ignore")

    role: Role
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None
    tool_call_id: str | None = None


class GenerationParams(BaseModel):
    """Generation parameters forwarded to a provider."""

    model_config = ConfigDict(extra="forbid")

    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, ge=1)
    stop: str | list[str] | None = None


class ChatCompletionRequest(BaseModel):
    """Client request for POST /v1/chat/completions."""

    model_config = ConfigDict(extra="ignore")

    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    stream_options: dict[str, Any] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    max_tokens: int | None = Field(default=None, ge=1)
    max_completion_tokens: int | None = Field(default=None, ge=1)
    n: int = Field(default=1, ge=1, le=8)
    stop: str | list[str] | None = None
    user: str | None = None
    session_id: str | None = None
    account_id: str | None = None

    @model_validator(mode="after")
    def _reject_conflicting_token_limits(self) -> "ChatCompletionRequest":
        if self.max_tokens is not None and self.max_completion_tokens is not None:
            raise ValueError("use max_tokens or max_completion_tokens, not both")
        return self


class NormalizedMessage(BaseModel):
    """Message preserved in its original role order."""

    model_config = ConfigDict(frozen=True)

    role: Role
    text: str
    name: str | None = None
    tool_call_id: str | None = None


class NormalizedRequest(BaseModel):
    """Provider-independent request representation."""

    model_config = ConfigDict(frozen=True)

    request_id: str
    session_id: str | None
    model_id: str
    messages: tuple[NormalizedMessage, ...]
    instructions: tuple[str, ...]
    generation: GenerationParams
    stream: bool = False
    account_id: str | None = None
    tools: tuple[dict[str, Any], ...] = ()

    @property
    def last_user_text(self) -> str | None:
        for message in reversed(self.messages):
            if message.role == "user":
                return message.text
        return None


class CapabilityStatus(str, Enum):
    """Honest support status for a model capability."""

    VERIFIED = "VERIFIED"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_TESTED = "NOT TESTED"


class ModelDescriptor(BaseModel):
    """Internal model registry entry."""

    model_config = ConfigDict(frozen=True)

    id: str
    display_name: str
    provider: str
    upstream: str
    capabilities: dict[str, CapabilityStatus]


class PublicModel(BaseModel):
    """OpenAI-compatible model object with a zv67 extension block."""

    model_config = ConfigDict(extra="allow")

    id: str
    object: Literal["model"] = "model"
    created: int
    owned_by: str
    zv67: dict[str, Any]


class ModelList(BaseModel):
    """OpenAI-compatible model list."""

    object: Literal["list"] = "list"
    data: list[PublicModel]


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str


class Choice(BaseModel):
    index: int = 0
    message: AssistantMessage
    finish_reason: Literal["stop"] = "stop"
    logprobs: None = None


class ChatCompletionResponse(BaseModel):
    """Non-streaming chat completion. Usage stays null: mock data is not invented."""

    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: None = None
    system_fingerprint: None = None
    zv67: dict[str, Any] = Field(default_factory=dict)


def extract_text(message: ChatMessage, max_chars: int) -> str:
    """Flatten text content. Reject images and other unsupported parts."""

    parts = message.content
    if parts is None:
        text = ""
    elif isinstance(parts, str):
        text = parts
    else:
        chunks: list[str] = []
        for part in parts:
            if part.get("type") != "text":
                raise MockContentError(
                    f"content part type '{part.get('type')}' is not supported"
                )
            value = part.get("text")
            if not isinstance(value, str):
                raise MockContentError("text content part requires a string 'text'")
            chunks.append(value)
        text = "\n".join(chunks)
    if len(text) > max_chars:
        raise MockContentError(
            f"message exceeds the {max_chars} character limit"
        )
    return text


def normalize_chat_request(
    request: ChatCompletionRequest,
    *,
    request_id: str | None = None,
    max_message_chars: int = 200_000,
) -> NormalizedRequest:
    """Convert a wire request without dropping roles or instructions."""

    messages = tuple(
        NormalizedMessage(
            role=message.role,
            text=extract_text(message, max_message_chars),
            name=message.name,
            tool_call_id=message.tool_call_id,
        )
        for message in request.messages
    )
    instructions = tuple(
        message.text for message in messages if message.role in ("system", "developer")
    )
    return NormalizedRequest(
        request_id=request_id or f"req_{uuid.uuid4().hex}",
        session_id=request.session_id,
        model_id=request.model,
        messages=messages,
        instructions=instructions,
        generation=GenerationParams(
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_tokens or request.max_completion_tokens,
            stop=request.stop,
        ),
        stream=request.stream,
        account_id=request.account_id,
        tools=tuple(request.tools or ()),
    )


class ResponseRequest(BaseModel):
    """Subset of the OpenAI Responses API accepted by ZV67."""

    model_config = ConfigDict(extra="ignore")

    model: str
    input: str | list[dict[str, Any]]
    instructions: str | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    max_output_tokens: int | None = Field(default=None, ge=1)
    previous_response_id: str | None = None
    parallel_tool_calls: bool | None = None
    store: bool = False
    metadata: dict[str, Any] | None = None
    session_id: str | None = None
    account_id: str | None = None


class ResponseTextPart(BaseModel):
    type: Literal["output_text"] = "output_text"
    text: str
    annotations: list[dict[str, Any]] = Field(default_factory=list)


class ResponseOutputMessage(BaseModel):
    type: Literal["message"] = "message"
    id: str
    status: Literal["completed"] = "completed"
    role: Literal["assistant"] = "assistant"
    content: list[ResponseTextPart]


class ResponseObject(BaseModel):
    id: str
    object: Literal["response"] = "response"
    created_at: int
    status: Literal["completed"] = "completed"
    model: str
    output: list[ResponseOutputMessage]
    usage: None = None
    error: None = None
    incomplete_details: None = None
    instructions: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    parallel_tool_calls: bool = False
    temperature: float | None = None
    tool_choice: str | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)
    zv67: dict[str, Any] = Field(default_factory=dict)


def _response_content_text(content: Any, *, max_chars: int) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        chunks: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                raise MockContentError("response input parts must be objects")
            if part.get("type") not in ("input_text", "output_text", "text"):
                raise MockContentError(
                    f"response input part '{part.get('type')}' is not supported"
                )
            value = part.get("text")
            if not isinstance(value, str):
                raise MockContentError("text part requires a string 'text'")
            chunks.append(value)
        text = "\n".join(chunks)
    else:
        raise MockContentError("response content must be a string or a list")
    if len(text) > max_chars:
        raise MockContentError(f"message exceeds the {max_chars} character limit")
    return text


def normalize_response_request(
    request: ResponseRequest,
    *,
    request_id: str | None = None,
    max_message_chars: int = 200_000,
) -> NormalizedRequest:
    """Convert Responses input into the shared normalized request."""

    messages: list[NormalizedMessage] = []
    instructions: list[str] = []
    if request.instructions:
        instructions.append(request.instructions)
        messages.append(NormalizedMessage(role="system", text=request.instructions))

    if isinstance(request.input, str):
        messages.append(NormalizedMessage(role="user", text=request.input))
    else:
        for item in request.input:
            item_type = item.get("type")
            if item_type in ("function_call", "function_call_output"):
                raise MockContentError(
                    f"response input item '{item_type}' requires tool support"
                )
            if item_type not in (None, "message"):
                raise MockContentError(
                    f"response input item '{item_type}' is not supported"
                )
            role = item.get("role")
            if role not in ("system", "developer", "user", "assistant", "tool"):
                raise MockContentError("response input item has an invalid role")
            text = _response_content_text(
                item.get("content"), max_chars=max_message_chars
            )
            messages.append(NormalizedMessage(role=role, text=text))
            if role in ("system", "developer"):
                instructions.append(text)

    if not messages:
        raise MockContentError("response input must contain at least one message")

    return NormalizedRequest(
        request_id=request_id or f"req_{uuid.uuid4().hex}",
        session_id=request.session_id,
        model_id=request.model,
        messages=tuple(messages),
        instructions=tuple(instructions),
        generation=GenerationParams(
            temperature=request.temperature,
            top_p=request.top_p,
            max_tokens=request.max_output_tokens,
        ),
        stream=request.stream,
        account_id=request.account_id,
    )

