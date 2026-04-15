import json, sys
import logging
from datetime import datetime, timezone
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

# ===========================================================================
# ✏️  CONFIGURE HERE
# ===========================================================================

ROOT_DIR = Path(__file__).parent.parent.parent

LOG_DIR: Path = Path(ROOT_DIR, "logs")        # Directory where log files are written
DEFAULT_LOG_LEVEL: str = "INFO"         # Global fallback: DEBUG | INFO | WARNING | ERROR

AGENT_LOG_LEVELS: dict[str, str] = {
    # "orchestrator": "DEBUG",
    # "retriever":    "WARNING",
}

# ===========================================================================

# Per-agent overrides: "orchestrator=DEBUG,retriever=WARNING"
_AGENT_LEVEL_OVERRIDES: dict[str, int] = {}
_LOGGER_CACHE: dict[str, logging.Logger] = {}

# Shared console handler (one across all agents to avoid duplicate stderr lines)
_CONSOLE_HANDLER: Optional[logging.Handler] = None


# ---------------------------------------------------------------------------
# ANSI colour palette (disabled automatically when not a TTY)
# ---------------------------------------------------------------------------

import sys as _sys

_USE_COLOUR = _sys.stdout.isatty()

class _C:
    RESET   = "\033[0m"    if _USE_COLOUR else ""
    BOLD    = "\033[1m"    if _USE_COLOUR else ""
    DIM     = "\033[2m"    if _USE_COLOUR else ""
    # event-type accent colours
    AGENT   = "\033[38;5;75m"   if _USE_COLOUR else ""   # sky blue
    MODEL   = "\033[38;5;141m"  if _USE_COLOUR else ""   # soft purple
    TOOL    = "\033[38;5;114m"  if _USE_COLOUR else ""   # sage green
    # level colours
    DEBUG   = "\033[38;5;244m"  if _USE_COLOUR else ""   # grey
    INFO    = "\033[38;5;255m"  if _USE_COLOUR else ""   # white
    WARNING = "\033[38;5;214m"  if _USE_COLOUR else ""   # amber
    ERROR   = "\033[38;5;203m"  if _USE_COLOUR else ""   # red
    # muted
    MUTED   = "\033[38;5;240m"  if _USE_COLOUR else ""   # dark grey

_EVENT_COLOUR = {
    "BEFORE_AGENT": _C.AGENT,  "AFTER_AGENT":  _C.AGENT,
    "BEFORE_MODEL": _C.MODEL,  "AFTER_MODEL":  _C.MODEL,
    "BEFORE_TOOL":  _C.TOOL,   "AFTER_TOOL":   _C.TOOL,
}

_LEVEL_COLOUR = {
    "DEBUG": _C.DEBUG, "INFO": _C.INFO,
    "WARNING": _C.WARNING, "ERROR": _C.ERROR,
}

# Fields shown inline in the detail line (order matters)
_DETAIL_KEYS = [
    "agent_name", "invocation_id", "session_id",
    "tool_name", "tool_args", "tool_response",
    "prompt", "llm_response",
    "user_state",
]

# Internal LogRecord attributes to skip
_SKIP = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message", "asctime", "event", "agent_name",
    "invocation_id", "session_id",
}

_MAX_INLINE = 120   # chars before a value is pretty-printed on its own line


# ---------------------------------------------------------------------------
# JSON formatter  (file handler — one compact object per line)
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line."""

    RESERVED = {"message", "timestamp", "level", "logger", "exc_info"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level":     record.levelname,
            "logger":    record.name,
            "message":   record.getMessage(),
        }
        for key, val in record.__dict__.items():
            if key.startswith("_") or key in self.RESERVED:
                continue
            if key in logging.LogRecord.__init__.__code__.co_varnames:
                continue
            payload[key] = val
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        try:
            return json.dumps(payload, ensure_ascii=False, default=str)
        except Exception as e:
            return json.dumps({"level": "ERROR", "message": f"Log serialisation failed: {e}"})


# ---------------------------------------------------------------------------
# Pretty formatter  (console handler — human-readable blocks)
# ---------------------------------------------------------------------------

class PrettyFormatter(logging.Formatter):
    """
    Renders each log record as a compact visual block, e.g.:

    ┌─ TOOL ─────────────────────────── 14:03:22 ─ orchestrator ─ INFO
    │  Tool call started
    │  tool_name      retrieve_chunks
    │  tool_args      {"query": "what is RAG?", "top_k": 5}
    └─────────────────────────────────────────────────────────────────
    """

    _BOX_W = 72  # total inner width

    def format(self, record: logging.LogRecord) -> str:
        event      = getattr(record, "event", "")
        ec         = _EVENT_COLOUR.get(event, _C.MUTED)
        lc         = _LEVEL_COLOUR.get(record.levelname, _C.INFO)
        ts         = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        agent      = getattr(record, "agent_name", record.name.split(".")[-1])
        category   = self._category(event)

        # ── header ──────────────────────────────────────────────────
        tag   = f" {category} " if category else " LOG "
        right = f" {ts} ─ {agent} ─ {record.levelname} "
        fill  = "─" * max(2, self._BOX_W - len(tag) - len(right))
        header = (
            f"{ec}{_C.BOLD}┌─{tag}{'─' * (len(fill) - 0)}{right}─{_C.RESET}"
        )
        # Simpler, reliable header:
        header = (
            f"{ec}{_C.BOLD}┌─{tag}{fill}{right}{_C.RESET}"
        )

        lines = [header]

        # ── message ─────────────────────────────────────────────────
        lines.append(f"{ec}│{_C.RESET}  {lc}{_C.BOLD}{record.getMessage()}{_C.RESET}")

        # ── detail fields ────────────────────────────────────────────
        shown = set()
        for key in _DETAIL_KEYS:
            val = getattr(record, key, None)
            if val is None:
                continue
            shown.add(key)
            lines += self._field_lines(key, val, ec)

        # any extra fields not in the curated list
        for key, val in record.__dict__.items():
            if key in shown or key in _SKIP or key.startswith("_"):
                continue
            lines += self._field_lines(key, val, ec)

        # ── exception ───────────────────────────────────────────────
        if record.exc_info:
            lines.append(f"{ec}│{_C.RESET}")
            for eline in self.formatException(record.exc_info).splitlines():
                lines.append(f"{ec}│{_C.RESET}  {_C.ERROR}{eline}{_C.RESET}")

        # ── footer ───────────────────────────────────────────────────
        lines.append(f"{ec}└{'─' * (self._BOX_W + 1)}{_C.RESET}")

        return "\n".join(lines)

    # ----------------------------------------------------------------
    def _category(self, event: str) -> str:
        if "AGENT" in event:  return "AGENT"
        if "MODEL" in event:  return "MODEL"
        if "TOOL"  in event:  return "TOOL"
        return ""

    def _field_lines(self, key: str, val, ec: str) -> list[str]:
        label = f"{key:<16}"   # fixed-width label column
        if isinstance(val, (dict, list)):
            pretty = json.dumps(val, ensure_ascii=False, indent=2, default=str)
        else:
            pretty = str(val)

        if "\n" not in pretty and len(pretty) <= _MAX_INLINE:
            return [f"{ec}│{_C.RESET}  {_C.MUTED}{label}{_C.RESET} {pretty}"]

        # multi-line: first line carries the label, rest are indented
        result = []
        sub_lines = pretty.splitlines()
        result.append(f"{ec}│{_C.RESET}  {_C.MUTED}{label}{_C.RESET} {sub_lines[0]}")
        indent = " " * (2 + 16 + 1)
        for sl in sub_lines[1:]:
            result.append(f"{ec}│{_C.RESET}{indent}{sl}")
        return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def set_agent_log_level(agent_name: str, level: str | int) -> None:
    """
    Override the log level for a specific agent at runtime.

    Args:
        agent_name: Exact agent name (e.g. "orchestrator").
        level: A logging level string ("DEBUG", "WARNING") or int constant.

    Example:
        set_agent_log_level("orchestrator", "DEBUG")
        set_agent_log_level("retriever", logging.WARNING)
    """
    resolved = logging._nameToLevel.get(level.upper(), level) if isinstance(level, str) else level
    _AGENT_LEVEL_OVERRIDES[agent_name] = resolved

    # Apply immediately if logger already exists
    safe_name = _safe(agent_name)
    cached = _LOGGER_CACHE.get(f"adk.{safe_name}")
    if cached:
        cached.setLevel(resolved)
        for h in cached.handlers:
            h.setLevel(resolved)


def get_agent_logger(agent_name: str) -> logging.Logger:
    """
    Return a per-agent structured JSON logger.

    File: logs/{agent_name}_logger_{YYYYMMDD}.log
    Level: per-agent override → ADK_LOG_LEVEL env var → INFO
    """
    safe_name = _safe(agent_name)
    logger_name = f"adk.{safe_name}"

    if logger_name in _LOGGER_CACHE:
        return _LOGGER_CACHE[logger_name]

    level = _resolve_level(agent_name)

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False

    if not logger.handlers:
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        # --- File handler  (JSON — machine readable) ---
        date_str = datetime.now().strftime("%Y%m%d")
        file_path = LOG_DIR / f"{safe_name}_logger_{date_str}.log"
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=5_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)

        # --- Console handler  (Pretty — human readable) ---
        logger.addHandler(_get_console_handler(level))

    _LOGGER_CACHE[logger_name] = logger
    return logger


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)


def _resolve_level(agent_name: str) -> int:
    if agent_name in _AGENT_LEVEL_OVERRIDES:
        return _AGENT_LEVEL_OVERRIDES[agent_name]
    if agent_name in AGENT_LOG_LEVELS:
        return logging._nameToLevel.get(AGENT_LOG_LEVELS[agent_name].upper(), logging.INFO)
    return logging._nameToLevel.get(DEFAULT_LOG_LEVEL.upper(), logging.INFO)


def _get_console_handler(level: int) -> logging.Handler:
    global _CONSOLE_HANDLER
    if _CONSOLE_HANDLER is None:
        h = logging.StreamHandler(_sys.stdout)
        h.setLevel(level)
        h.setFormatter(PrettyFormatter())
        _CONSOLE_HANDLER = h
    return _CONSOLE_HANDLER