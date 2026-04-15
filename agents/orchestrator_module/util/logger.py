import json
import sys
from typing import Any, Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

from .logger_config import get_agent_logger

_MAX_PAYLOAD_CHARS = 1_500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _logger(ctx: CallbackContext):
    return get_agent_logger(getattr(ctx, "agent_name", "unknown_agent"))


def _base_ctx(ctx: CallbackContext) -> dict:
    """Common fields attached to every log entry."""
    return {
        "agent_name":    getattr(ctx, "agent_name", None),
        "invocation_id": getattr(ctx, "invocation_id", None),
        "session_id":    getattr(ctx, "session_id", None),
    }


def _serialise(value: Any, label: str = "payload") -> Any:
    """
    Convert an ADK model object to a JSON-safe structure.
    Truncates the final string representation if it exceeds _MAX_PAYLOAD_CHARS.
    """
    try:
        if hasattr(value, "model_dump"):
            raw = value.model_dump()
        elif hasattr(value, "dict"):
            raw = value.dict()
        elif isinstance(value, (dict, list, str, int, float, bool)) or value is None:
            raw = value
        else:
            raw = str(value)

        serialised = json.dumps(raw, ensure_ascii=False, default=str)
        if len(serialised) > _MAX_PAYLOAD_CHARS:
            serialised = serialised[:_MAX_PAYLOAD_CHARS] + f"… [truncated {label}]"
        return json.loads(serialised) if not serialised.endswith("]") else serialised

    except Exception as exc:
        return f"<serialisation error: {exc}>"


def _state(ctx: CallbackContext) -> Any:
    try:
        return _serialise(getattr(ctx, "state", None), "state")
    except Exception:
        return None


def _extract_prompt(llm_request: LlmRequest) -> dict:
    """
    Pull the human-readable prompt out of an LlmRequest.

    Returns a dict with:
      system_instruction  - the system prompt string, if present
      turns               - list of {role, text} for each content turn;
                            function calls and tool responses are labelled inline
    """
    result: dict = {}

    # ── System instruction ───────────────────────────────────────────
    try:
        config = getattr(llm_request, "config", None)
        sys_instr = getattr(config, "system_instruction", None) if config else None
        if sys_instr:
            if hasattr(sys_instr, "parts"):
                text = " ".join(
                    p.text for p in (sys_instr.parts or []) if getattr(p, "text", None)
                )
            else:
                text = str(sys_instr)
            if text.strip():
                result["system_instruction"] = text.strip()
    except Exception:
        pass

    # ── Conversation turns ───────────────────────────────────────────
    try:
        turns = []
        for content in (llm_request.contents or []):
            role = getattr(content, "role", "unknown")
            parts = getattr(content, "parts", []) or []
            segments = []
            for part in parts:
                if getattr(part, "text", None):
                    segments.append(part.text)
                elif getattr(part, "function_call", None):
                    fc = part.function_call
                    segments.append(
                        f"[function_call] {getattr(fc, 'name', '?')} "
                        f"args={json.dumps(getattr(fc, 'args', {}), default=str)}"
                    )
                elif getattr(part, "function_response", None):
                    fr = part.function_response
                    segments.append(
                        f"[function_response] {getattr(fr, 'name', '?')} "
                        f"response={json.dumps(getattr(fr, 'response', {}), default=str)}"
                    )
            if segments:
                turns.append({"role": role, "text": "\n".join(segments)})
        if turns:
            result["turns"] = turns
    except Exception:
        pass

    # Fall back to raw dump if extraction yielded nothing
    return result if result else {"raw": _serialise(llm_request, "llm_request")}


# ---------------------------------------------------------------------------
# Agent lifecycle callbacks
# ---------------------------------------------------------------------------

def before_agent_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    try:
        logger = _logger(callback_context)
        logger.info(
            "Agent invocation started",
            extra={
                **_base_ctx(callback_context),
                "event":      "BEFORE_AGENT",
                "user_state": _state(callback_context),
            },
        )
    except Exception as exc:
        _fallback_log("before_agent_callback", exc)
    return None


def after_agent_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    try:
        logger = _logger(callback_context)
        logger.info(
            "Agent invocation completed",
            extra={
                **_base_ctx(callback_context),
                "event": "AFTER_AGENT",
            },
        )
    except Exception as exc:
        _fallback_log("after_agent_callback", exc)
    return None


# ---------------------------------------------------------------------------
# Model callbacks
# ---------------------------------------------------------------------------

def before_model_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    try:
        logger = _logger(callback_context)
        logger.info(
            "LLM request dispatched",
            extra={
                **_base_ctx(callback_context),
                "event":  "BEFORE_MODEL",
                "prompt": _extract_prompt(llm_request),
            },
        )
    except Exception as exc:
        _fallback_log("before_model_callback", exc)
    return None


def after_model_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> Optional[LlmResponse]:
    try:
        logger = _logger(callback_context)
        logger.info(
            "LLM response received",
            extra={
                **_base_ctx(callback_context),
                "event":        "AFTER_MODEL",
                "llm_response": _serialise(llm_response, "llm_response"),
            },
        )
    except Exception as exc:
        _fallback_log("after_model_callback", exc)
    return None


# ---------------------------------------------------------------------------
# Tool callbacks
# ---------------------------------------------------------------------------

def before_tool_callback(tool, args, tool_context) -> Optional[dict]:
    try:
        agent_name = getattr(tool_context, "agent_name", "unknown_agent")
        logger = get_agent_logger(agent_name)
        logger.info(
            "Tool call started",
            extra={
                "event":         "BEFORE_TOOL",
                "agent_name":    agent_name,
                "invocation_id": getattr(tool_context, "invocation_id", None),
                "session_id":    getattr(tool_context, "session_id", None),
                "tool_name":     getattr(tool, "name", str(tool)),
                "tool_args":     _serialise(args, "tool_args"),
            },
        )
    except Exception as exc:
        _fallback_log("before_tool_callback", exc)
    return None


def after_tool_callback(tool, args, tool_context, tool_response) -> Optional[dict]:
    try:
        agent_name = getattr(tool_context, "agent_name", "unknown_agent")
        logger = get_agent_logger(agent_name)
        logger.info(
            "Tool call completed",
            extra={
                "event":         "AFTER_TOOL",
                "agent_name":    agent_name,
                "invocation_id": getattr(tool_context, "invocation_id", None),
                "session_id":    getattr(tool_context, "session_id", None),
                "tool_name":     getattr(tool, "name", str(tool)),
                "tool_response": _serialise(tool_response, "tool_response"),
            },
        )
    except Exception as exc:
        _fallback_log("after_tool_callback", exc)
    return None


# ---------------------------------------------------------------------------
# Fallback — last resort so a logging bug never crashes the agent
# ---------------------------------------------------------------------------

def _fallback_log(callback_name: str, exc: Exception) -> None:
    print(
        json.dumps({
            "level":    "ERROR",
            "event":    "CALLBACK_ERROR",
            "callback": callback_name,
            "error":    str(exc),
        }),
        file=sys.stderr,
    )