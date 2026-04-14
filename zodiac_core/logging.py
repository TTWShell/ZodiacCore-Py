import sys
from typing import Any, Dict, Optional

from loguru import logger
from pydantic import BaseModel, ConfigDict

from zodiac_core.context import get_request_id, get_service_name


class LogFileOptions(BaseModel):
    """
    Configuration options for file logging.

    Allows arbitrary extra arguments to be passed to loguru.add() via extra="allow".
    """

    rotation: str = "10 MB"
    retention: str = "1 week"
    compression: str = "zip"
    enqueue: bool = False
    encoding: str = "utf-8"

    model_config = ConfigDict(extra="allow")


def setup_loguru(
    level: str = "INFO",
    json_format: bool = True,
    service_name: str = "service",
    log_file: Optional[str] = None,
    console_options: Optional[Dict[str, Any]] = None,
    file_options: Optional[LogFileOptions] = None,
):
    """
    Configure Loguru with automatic Trace ID injection and multi-destination output.

    Args:
        level: Logging level (INFO, DEBUG, etc.)
        json_format: Whether to output JSON (True) or Text (False). When True, the
            serialized JSON has an empty "text" field to avoid duplicating the message
            (see record.message); pass a custom "format" in console_options/file_options
            if you need a non-empty "text".
        service_name: Name of the service (added to JSON logs).
        log_file: Optional file path to save logs.
        console_options: Extra kwargs to pass to the console sink (e.g. {"enqueue": True}).
        file_options: Configuration model (LogFileOptions) for file sink.
    """
    # 1. Remove default handlers
    logger.remove()

    default_service = service_name

    # 2. Configure Patcher (Trace ID injection)
    def patcher(record):
        request_id = get_request_id()
        if request_id:
            record["extra"]["request_id"] = request_id
        record["extra"]["service"] = get_service_name() or default_service

    logger.configure(patcher=patcher)

    # 3. Define Formatters
    def _dev_formatter(record):
        if "request_id" not in record["extra"]:
            record["extra"]["request_id"] = "-"
        return (
            "<green>{time:YYYYMMDD HH:mm:ss}</green> "
            "| {extra[service]} "
            "| {extra[request_id]} "
            "| {process.name} "
            "| {thread.name} "
            "| <cyan>{module}</cyan>.<cyan>{function}</cyan> "
            "| <level>{level}</level>: "
            "<level>{message}</level> "
            "| {file.path}:{line}\n"
        )

    # 4. Sink defaults shared by console and file (level, enqueue, format/serialize)
    # Empty format avoids duplicating message in "text" and "record.message" (see loguru#594)
    if json_format:
        _format_defaults: Dict[str, Any] = {"serialize": True, "format": lambda _: ""}
    else:
        _format_defaults = {"format": _dev_formatter}
    # enqueue=True for thread-safe sink
    _sink_defaults: Dict[str, Any] = {"level": level, "enqueue": True, **_format_defaults}

    def _apply_sink_defaults(config: Dict[str, Any], sink: Any) -> None:
        for key, value in _sink_defaults.items():
            config.setdefault(key, value)
        config.setdefault("sink", sink)

    # 5. Console sink
    c_config = console_options or {}
    _apply_sink_defaults(c_config, sys.stderr)
    logger.add(**c_config)

    # 6. File sink (if enabled)
    if log_file:
        if file_options is None:
            file_options = LogFileOptions()
        f_config = file_options.model_dump()
        _apply_sink_defaults(f_config, log_file)
        logger.add(**f_config)
